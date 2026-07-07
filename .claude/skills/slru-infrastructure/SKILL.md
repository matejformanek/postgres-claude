---
name: slru-infrastructure
description: PostgreSQL's Simple LRU (SLRU) subsystem — `src/backend/access/transam/slru.c` — the fixed-file, fixed-page cache used by CLOG (`pg_xact/`), MultiXact (`pg_multixact/`), Subtrans (`pg_subtrans/`), CommitTs (`pg_commit_ts/`), and Notify (`pg_notify/`). Covers the bank-locked LRU + latest-page pin design, `SlruCtl` structure, page replacement policy, and the on-disk 32-page-per-segment file layout. Loads when the user asks about SLRU semantics, per-consumer sizing GUCs (PG 17+ per-SLRU `Buffers` GUCs), why SLRUs use their own cache instead of shared buffers, adding a new SLRU consumer, or debugging SLRU-related wraparound / pressure. Skip when the ask is about specific SLRU consumers' semantics — the multixact skill covers multixact (which USES SLRU); this covers the SLRU MACHINERY itself.
when_to_load: Add a new SLRU consumer; investigate SLRU pressure / performance; understand the bank-locked replacement policy; touch page-replacement code; work with PG 17+ per-SLRU sizing.
companion_skills:
  - locking
  - multixact
  - access-method-apis
---

# slru-infrastructure — the fixed-page cache under CLOG / MultiXact / others

PostgreSQL has FIVE places where it needs a small, contention-friendly cache for status data indexed by monotonically-increasing IDs:

- **CLOG** (`pg_xact/`) — 2 bits per XID (in-progress / committed / aborted / subcommitted). Under `access/transam/clog.c`.
- **MultiXact offsets + members** (`pg_multixact/{offsets,members}/`) — 2 separate SLRUs for the tuple-locking machinery. Under `access/transam/multixact.c`.
- **Subtrans** (`pg_subtrans/`) — subtransaction xid → parent xid mapping. Under `access/transam/subtrans.c`.
- **CommitTs** (`pg_commit_ts/`) — per-xid commit timestamp (if `track_commit_timestamp = on`). Under `access/transam/commit_ts.c`.
- **Notify** (`pg_notify/`) — LISTEN/NOTIFY queue. Under `commands/async.c`.

Each COULD have used the main shared-buffer pool, but SLRU is optimized for the specific "small, always-hot, indexed by ID" pattern with a much cheaper per-page lock design.

## The file

Single-file infrastructure:

- `src/backend/access/transam/slru.c` (~1400 lines) — the whole implementation.
- `src/include/access/slru.h` — the `SlruCtl` struct + public API.

## The design — bank-locked LRU

Each SLRU has:

- **N in-memory pages** (typically 8-128, configurable).
- **Banks** — groups of pages sharing a lock. PG 17+ increased banks + made per-SLRU sizing GUC-configurable.
- **LRU counters** per page.
- **Dirty flag** per page.
- **Latest-page pin** — the page for the highest ID is always pinned (the write frontier).

Reading a page:

1. Check if it's in cache. Take the bank lock (SHARED).
2. If cached: touch the LRU counter + return.
3. If not: promote lock to EXCLUSIVE, evict the LRU page (flush if dirty), read from disk.

The bank-lock structure means many concurrent readers hit different banks with no contention. Vs shared_buffers where every page has a header hot-lock, SLRU wins on this specific access pattern.

## The on-disk file layout

Each SLRU stores its data in `pg_<name>/` directory as fixed-size segment files:

- 32 pages per segment (default; some SLRUs override).
- Segment file names are hex — e.g. `pg_xact/0000` is segments 0-31.
- Individual pages are 8 KB.
- Truncation at boundaries — the oldest segment gets removed after ALL its IDs are no longer needed.

Truncation is what enables SLRU wraparound: as long as VACUUM keeps `oldestXid` (or `oldestMulti` etc.) moving forward, older segments get pruned.

## The SlruCtl struct

Each SLRU consumer registers with a `SlruCtl` (control) struct at startup:

- Directory name (`pg_xact` etc.).
- Number of buffers.
- Number of banks.
- Bank lock names.
- LWLock tranche ID.
- Reference to shmem area for the page arrays.
- `PagePrecedes` callback — the ID-ordering function (some SLRUs use forward XIDs, some use MultiXact IDs — they may have different wrap semantics).

## Reading and writing

```c
/* Read */
int slotno = SimpleLruReadPage(SlruCtl, pageno, ok_if_not_found, xid);
if (slotno == -1) ereport(...);
/* Access shared->page_buffer[slotno] with the bank lock held share. */

/* Write */
int slotno = SimpleLruReadPage_ReadOnly(SlruCtl, pageno, xid);
/* Modify shared->page_buffer[slotno]. */
SimpleLruWritePage(SlruCtl, slotno);
```

Actual reads/writes are LWLock-protected but not WAL-logged in the hot path (except for MultiXact members, which have their own WAL discipline). The persistence guarantee comes from checkpointing.

## Per-SLRU GUC-tuning (PG 17+)

Before PG 17, SLRU sizes were compile-time constants. PG 17 made them runtime-configurable:

- `commit_timestamp_buffers`
- `multixact_offset_buffers` / `multixact_member_buffers`
- `notify_buffers`
- `serializable_buffers`
- `subtransaction_buffers`
- `transaction_buffers`

Each GUC controls the number of pages in that SLRU's cache. Default depends on the SLRU (typically 8-64). On high-transaction-rate systems, bumping these helps significantly.

## Common patch shapes

### Add a new SLRU consumer

- Define `SlruCtl <name>Ctl` at file scope.
- In shmem init: `SimpleLruInit(<name>Ctl, "NameForLog", num_buffers, num_banks, LWLockTrancheId, "pg_yourname", ...)`.
- Register directory `pg_yourname/` in initdb (via `RelationInitPhysicalAddr` or similar).
- Implement `PagePrecedes` for ID ordering.
- Set up read/write helpers using `SimpleLruReadPage` / `SimpleLruWritePage`.
- WAL / crash-recovery: consider whether this SLRU needs to be truncated at recovery.
- Regress + TAP tests for wraparound behavior.

### Add a new GUC for existing SLRU sizing

- New GUC constant in guc_tables.c.
- Pass to `SimpleLruInit` at shmem-init time.
- Add to per-cluster tuning docs.

### Debug SLRU pressure

- `pg_stat_slru` (in pgstat_slru.c) — per-SLRU counters: blks_zeroed, blks_hit, blks_read, blks_written, blks_exists, flushes, truncates.
- High read counter → cache thrash; increase buffers for that SLRU.
- High flushes counter → concurrent writes competing; increase banks or buffers.

### Add SLRU write coalescing

Uncommon. Would touch the individual write coalescer per SLRU consumer.

## Pitfalls

- **SLRU pages are 8 KB — same as main pages but NOT the same address space** — a bufmgr Buffer number won't work with SLRU. Different infrastructure.
- **Truncation moves the oldest boundary forward** — a code path that STILL needs an old page (e.g., logical replication needing an old CLOG entry for an old xmin) will error. This is why long-running logical slots pin catalog_xmin.
- **`PagePrecedes` must handle wraparound** — 32-bit ID wraparound means "smaller" changes meaning around the wrap point. Getting this wrong = disaster.
- **Read-only pages held across long operations block writes** — SLRU is designed for short-lived pins. Extension code that holds a page across long queries can starve the write side.
- **Per-SLRU GUCs aren't backported** — code assuming per-GUC configurable sizes doesn't compile on pre-PG-17.
- **`pg_stat_slru` bytes are pages, not disk bytes** — a common mistake in monitoring.
- **SLRU segments are 256 KB (32×8KB)** — very small compared to WAL segments. Manual pruning during recovery is rare.
- **`SimpleLruReadPage` under EXCLUSIVE holds an LWLock across I/O** — I/O time is included in the lock hold. A slow disk on the SLRU path hurts more than on shared buffers.
- **CLOG hot path bypass** — a common perf pattern is checking hint bits first + only calling into CLOG on miss. Because hint bits are per-tuple + lazy-updated, CLOG can be the perf floor.

## Related corpus

- **Idioms**: `slru-page-replacement` (the bank-locked LRU design), `clog-slru` (CLOG-specific semantics), `multixact-slru` (MultiXact-specific), `subxact-subtrans-slru` (Subtrans), `notify-listen-coordination` (Notify SLRU usage).
- **Subsystem**: `access-transam` (parent of most SLRU consumers).
- **Data structure**: `pgproc-fields` (per-backend xmin/xmax feed into oldestXid computation which drives SLRU truncation).
- **Skills**: `multixact` (specific SLRU consumer).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --idiom slru-page-replacement
python3 scripts/corpus-chain.py --file src/backend/access/transam/slru.c
```

## Boundary

**Use this skill** for `slru.c` infrastructure + new-SLRU-consumer patches + SLRU GUC tuning.

**Don't use** for:
- **Individual SLRU consumers' semantics** — `multixact` skill for MultiXact, `access-transam` subsystem for CLOG / Subtrans / CommitTs semantics.
- **`shared_buffers`** — different cache. See `buffer-manager`.
- **`pg_notify/` queue semantics** — LISTEN/NOTIFY has its own state machine; SLRU just provides the storage.
- **CLOG hint bits (`HEAP_XMIN_COMMITTED` etc.)** — those are tuple-level, not SLRU-cache-level.
