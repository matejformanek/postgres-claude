# `src/include/access/rewriteheap.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**58 lines.**

## Role

The narrow API for **heap rewriting** — the mechanism used by
`CLUSTER`, `VACUUM FULL`, and some forms of `ALTER TABLE` /
`REFRESH MATERIALIZED VIEW` to rebuild a heap into a new
relfilenode. Also defines the on-disk format for "logical rewrite
mappings" emitted during rewrites so that logical decoding on
in-flight transactions can re-find their tuples after the rewrite.
[verified-by-code] `source/src/include/access/rewriteheap.h:1-12`

## Public API

`typedef struct RewriteStateData *RewriteState;` — opaque handle
(line 22).

Four control functions (lines 24-30):
- `begin_heap_rewrite(old_heap, new_heap, oldest_xmin, freeze_xid,
  cutoff_multi)` → `RewriteState`. Picks the freeze/cutoff thresholds
  applied to surviving tuples.
- `end_heap_rewrite(state)` — flush, fsync, finalize.
- `rewrite_heap_tuple(state, old_tuple, new_tuple)` — emit one
  surviving tuple into the new heap, recording the `(old_tid →
  new_tid)` mapping if needed for logical decoding.
- `rewrite_heap_dead_tuple(state, old_tuple)` → bool — record that
  `old_tuple` was discarded; returns whether the rewrite needs to
  preserve its mapping (for in-progress logical decoders).

Logical rewrite mapping on-disk format (lines 35-54):
```c
typedef struct LogicalRewriteMappingData {
    RelFileLocator old_locator;
    RelFileLocator new_locator;
    ItemPointerData old_tid;
    ItemPointerData new_tid;
} LogicalRewriteMappingData;
```

Filename format string `LOGICAL_REWRITE_FORMAT "map-%x-%x-%X_%X-%x-%x"`
(line 54), with six fields documented in lines 43-52:
1. database OID (or InvalidOid for shared rels)
2. relation OID
3. upper 32 bits of LSN at rewrite start
4. lower 32 bits of LSN at rewrite start
5. xid we are mapping for
6. xid of the xact doing the mapping

Plus `CheckPointLogicalRewriteHeap()` (line 55) — checkpoint-time
flushing/recycling of mapping files.

## Invariants

- **INV-rewrite-cutoff-discipline:** `oldest_xmin`, `freeze_xid`,
  `cutoff_multi` come from the same source as VACUUM's cutoffs.
  Picking them wrong creates tuples that look "frozen" but aren't,
  or vice versa.
- **INV-rewrite-logical-decoded-xids:** tuples produced/modified by
  xids that are still in the logical-decoding "needs catalog
  snapshot" set MUST have their `old_tid → new_tid` mapping
  preserved on disk under `pg_logical/mappings/` until the slot
  advances past them. This is what `rewrite_heap_dead_tuple`'s
  return value controls. [verified-by-code] line 30.
- **INV-rewrite-newheap-fresh:** `new_heap` is a freshly-created
  relfilenode (no concurrent activity). The rewriter assumes
  exclusive access.
- **INV-rewrite-filename:** lowercase-x = hex without leading zeros,
  uppercase-X = hex with leading zeros for LSN halves. The
  `%X_%X` form is the canonical pg_walinspect-style LSN.

## Notable internals

The rewriter walks the old heap in physical order, decides per-tuple
whether to copy / freeze / discard, and appends to the new heap. WAL
is emitted in the usual heap_insert form (no special "rewrite"
record), so crash recovery just sees a normally-built new heap.

Logical rewrite mappings live in `pg_logical/mappings/<filename>`
where `<filename>` is `sprintf(LOGICAL_REWRITE_FORMAT, ...)`. They are
read by `ReorderBufferQueueChange` (logical decoding) to translate
old TIDs in WAL into the new TIDs after the rewrite — without these,
a decoder following a rewrite would lose track of its uncommitted
transactions.

`CheckPointLogicalRewriteHeap` runs at every checkpoint to fsync new
mapping files and to remove ones that are now older than every
logical slot's `catalog_xmin` — bounded retention.

## Trust-boundary / Phase D surface

**A8 cross-link.** The mapping files in `pg_logical/mappings/` are
written by every CLUSTER/VACUUM FULL/etc. on any relation, as long
as a logical slot is active. They are NOT user-readable by default
(filesystem permissions on the data dir), but a process with read
access to `$PGDATA/pg_logical/mappings/` can observe:
- Which databases have been CLUSTER'd/rewritten and when (LSN in
  filename).
- Which xids did rewrites — a covert side channel into transaction
  activity on otherwise-private databases.

For Phase D, this is a **disk-side-channel surface**: the filenames
themselves leak metadata (db oid + xid + LSN) without needing to read
the contents.

**Logical slot retention pressure:** if a logical replication
subscriber falls behind, every rewrite during the lag period adds a
mapping file. Disk-fill DoS vector: an attacker who can hold open a
logical slot and stall it can force unbounded mapping file growth
during heavy maintenance.

## Cross-refs

- `access/heapam.h` — `heap_insert` used internally.
- `storage/relfilelocator.h` — `RelFileLocator`.
- `replication/snapbuild.h`, `replication/reorderbuffer.h` — logical
  decoding consumers of the mapping files.
- `commands/cluster.c` — primary caller.
- `commands/vacuum.c` — VACUUM FULL caller.
- `subsystems/replication-overview.md` — logical-decoding narrative.

## Issues

- **ISSUE-leak (Phase D, A8 echo)**: filenames in
  `pg_logical/mappings/` leak metadata about rewrite activity and
  xids even if contents are not readable. Worth a register entry.
- **ISSUE-DoS**: stalled logical slot + heavy CLUSTER load fills
  disk with mapping files. No accounting/limit on mapping-file
  count.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-heap.md](../../../../subsystems/access-heap.md)
