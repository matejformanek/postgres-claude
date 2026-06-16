# src/include/replication/reorderbuffer.h

## Purpose

The **reorderbuffer** is logical decoding's transaction reassembly
engine. WAL is record-ordered but transaction-interleaved; the
reorderbuffer groups records by xid, holds them until commit, and then
replays the transaction's changes in commit order to the output plugin.
This header defines:

1. `ReorderBufferChange` — a single per-record decoded event.
2. `ReorderBufferTXN` — a per-xid container of changes, flags, and
   bookkeeping (commit time, base snapshot, subtxns, invalidations).
3. `ReorderBuffer` — the per-decoding-context engine with HTAB + LSN
   lists + callback table + memory accounting + spill statistics.
4. ~20 callback signatures the output plugin fills in.
5. The `ReorderBufferXxx` API used by the decode dispatchers (see
   `decode.h`).

## Role in PG

A logical decoding context owns one `ReorderBuffer`. As `decode.h`'s
`*_decode` functions produce changes, they call `ReorderBufferQueueChange`
keyed by xid. At xact commit, `ReorderBufferCommit` walks the changes
in LSN order, resolves catalog snapshots, calls the output plugin's
`change_cb` per change, then `commit_cb`. To bound memory,
transactions exceeding `logical_decoding_work_mem` are spilled to disk
files under `pg_replslot/<slot>/xid-*.spill` (streaming-capable
subscribers receive partial transactions inline; older clients get the
spill-then-replay path).

See `knowledge/subsystems/replication.md` (logical decoding).

## Key types/struct fields

- Disk paths (lines 22-24):
  - `PG_LOGICAL_DIR = "pg_logical"`
  - `PG_LOGICAL_MAPPINGS_DIR = "pg_logical/mappings"` (rewrite mappings
    from `VACUUM FULL`/`CLUSTER` on catalog tables, needed to decode
    pre-rewrite tuples).
  - `PG_LOGICAL_SNAPSHOTS_DIR = "pg_logical/snapshots"` (snapbuild
    serialized snapshots).
  [verified-by-code]
  
  NOTE: Spilled-xact files live under `pg_replslot/<slotname>/` not
  `pg_logical/`; not declared here. [verified-by-code via reorderbuffer.c]

- GUCs (lines 27-28):
  - `logical_decoding_work_mem` (default 64MB) — soft cap on in-memory
    reorderbuffer size before spilling/streaming the largest top-level
    xact.
  - `debug_logical_replication_streaming` — DEBUG: BUFFERED vs
    IMMEDIATE streaming mode for testing.
  [verified-by-code]

- `ReorderBufferChangeType` enum (lines 50-64) — what kind of change:
  INSERT/UPDATE/DELETE/TRUNCATE/MESSAGE are user-visible;
  INTERNAL_SNAPSHOT, INTERNAL_COMMAND_ID, INTERNAL_TUPLECID,
  INTERNAL_SPEC_INSERT/CONFIRM/ABORT (speculative insertions for INSERT
  ON CONFLICT), INVALIDATION are internal. Output plugin never sees
  INTERNAL_*. [from-comment, lines 39-48]

- `ReorderBufferChange` (lines 76-164) — per-event union keyed by
  `action`. Carries `lsn`, `txn` back-pointer, `origin_id` (for origin
  filtering), and a discriminated union of {tp (insert/update/delete
  with `rlocator`, oldtuple, newtuple, `clear_toast_afterwards`),
  truncate, msg (`pg_logical_emit_message`), snapshot, command_id,
  tuplecid, inval}. `dlist_node node` links it into the txn's
  `changes` list. [verified-by-code]

- `ReorderBufferTXN` (lines 293-468) — the BIG struct, one per
  in-flight xid (top-level or sub). Key fields:
  - `txn_flags` (line 296) — uint32 bitfield, all 13 documented flag
    constants at lines 167-181: `RBTXN_HAS_CATALOG_CHANGES`,
    `RBTXN_IS_SUBXACT`, `RBTXN_IS_SERIALIZED` (spilled to disk),
    `RBTXN_IS_SERIALIZED_CLEAR` (ever-spilled, even if now cleared),
    `RBTXN_IS_STREAMED`, `RBTXN_HAS_PARTIAL_CHANGE`, `RBTXN_IS_PREPARED`,
    `RBTXN_SKIPPED_PREPARE`, `RBTXN_HAS_STREAMABLE_CHANGE`,
    `RBTXN_SENT_PREPARE`, `RBTXN_IS_COMMITTED`, `RBTXN_IS_ABORTED`,
    `RBTXN_DISTR_INVAL_OVERFLOWED`. Tested via `rbtxn_is_*()` inline
    macros (lines 184-291). [verified-by-code]
  - `xid`, `toplevel_xid` (lines 299-302) — subxact tracking.
  - `gid` (line 308) — global xact id for prepared xacts.
  - `first_lsn` / `final_lsn` / `end_lsn` (lines 315, 332, 337) — LSN
    span. `final_lsn` is overloaded: normally the commit/abort/prepare
    record's LSN, but when an in-progress xact is spilled it's
    repointed to the latest spilled change. [from-comment, lines 317-330]
  - `toptxn` (line 340) — pointer back to parent; NULL ⇒ this is the
    top-level txn (tested by `rbtxn_is_toptxn`, line 276).
  - `restart_decoding_lsn` (line 347) — where snapshot info lives so
    decoding could be restarted from this LSN.
  - `base_snapshot` + `base_snapshot_lsn` (lines 369-370) — the
    historic-MVCC snapshot used to decode this txn's catalog reads.
  - `snapshot_now` + `command_id` (lines 377-378) — restored at
    streaming-resume time.
  - `nentries` / `nentries_mem` (lines 385-391) — total changes vs
    those still in memory (rest on disk). [verified-by-code]
  - `changes` dlist (line 397) — the change list (in-memory portion).
  - `tuplecids` dlist + `ntuplecids` (lines 404-405) + `tuplecid_hash`
    (line 410) — catalog-tuple cmin/cmax map, needed because the
    historic snapshot must see them.
  - `toast_hash` (line 416) — partial toast chunk reassembly.
  - `subtxns` dlist + `nsubtxns` (lines 422-423) — non-aborted subxacts
    only (in toplevel only).
  - `invalidations` (line 430) and `invalidations_distributed`
    (line 436) — cache-invalidation messages for catalog-changing
    txns; "distributed" ones come from other concurrent xacts.
  - `node` (line 444) — link in either `toplevel_by_lsn` or `subtxns`
    of parent.
  - `catchange_node` (line 449) — link in `catchange_txns` if this
    txn modified catalogs.
  - `txn_node` (pairingheap_node, line 454) — max-heap entry indexed by
    `total_size` for picking the biggest xact to spill/stream.
  - `size` / `total_size` (lines 459, 462) — bytes in memory, with
    `total_size` summing subxacts.
  - `output_plugin_private` (line 467) — per-txn opaque pointer for
    output plugins (e.g. pgoutput stashes its per-txn state here).
  [verified-by-code]

- Callback signatures (lines 471-572) — 17 callbacks the output plugin
  may install:
  - Non-streaming: begin, apply_change, apply_truncate, commit, message.
  - Two-phase: begin_prepare, prepare, commit_prepared, rollback_prepared.
  - Streaming: stream_start, stream_stop, stream_abort, stream_prepare,
    stream_commit, stream_change, stream_message, stream_truncate.
  - Progress: update_progress_txn.
  pgoutput (built-in, used by native logical replication) fills all of
  them; third-party output plugins (test_decoding, wal2json) often only
  fill the non-streaming subset. [verified-by-code]

- `ReorderBuffer` (lines 574-702) — the engine:
  - `by_txn` HTAB (line 579) — xid → ReorderBufferTXN lookup.
  - `toplevel_by_lsn` dlist (line 585) — LSN-ordered top-levels.
  - `txns_by_base_snapshot_lsn` dlist (line 594) — for snapshot
    advancement.
  - `catchange_txns` dclist (line 599) — catalog-modifying xacts (so
    other decoders can distribute invalidations).
  - `by_txn_last_xid` / `by_txn_last_txn` (lines 605-606) — 1-entry
    cache for the HTAB; common access pattern is the same xid in a row.
  - Callback function pointers (lines 611-641).
  - `private_data` (line 646) — opaque ptr to output plugin state.
  - `output_rewrites` (line 651) — `--include-rewrites` option.
  - Memory contexts (lines 656-663): `context` (the parent),
    `change_context`, `txn_context`, `tup_context` — pre-allocated
    so individual allocs are cheap.
  - `outbuf` / `outbufsize` (lines 668-669) — reusable serialization
    buffer for spill I/O.
  - `size` (line 672) — total in-memory bytes across all xacts.
  - `txn_heap` (pairingheap, line 675) — max-heap by `total_size`,
    used by `ReorderBufferCheckMemoryLimit` to find the biggest xact
    to evict (spill or stream).
  - Spill stats (lines 684-686): `spillTxns`, `spillCount`,
    `spillBytes`. Visible in `pg_stat_replication_slots`.
  - Stream stats (lines 689-691).
  - `memExceededCount` (line 694) — how many times
    `logical_decoding_work_mem` was hit.
  - Total stats (lines 700-701).
  [verified-by-code]

- Public functions (lines 705-784) — ~40 entry points. Highlights:
  - `ReorderBufferAllocate`/`Free` — engine lifecycle.
  - `ReorderBufferAllocChange`/`FreeChange`,
    `ReorderBufferAllocTupleBuf`/`FreeTupleBuf`,
    `ReorderBufferAllocRelids`/`FreeRelids` — allocator wrappers (use
    the pre-built contexts).
  - `ReorderBufferQueueChange(rb, xid, lsn, change, toast_insert)` —
    main entry from decoders.
  - `ReorderBufferQueueMessage(...)` — for `pg_logical_emit_message`.
  - `ReorderBufferCommit(rb, xid, commit_lsn, end_lsn, commit_time,
    origin_id, origin_lsn)` — replay on commit.
  - `ReorderBufferFinishPrepared(...)` — two-phase commit/abort of a
    previously-prepared xact.
  - `ReorderBufferAssignChild`, `ReorderBufferCommitChild` — subxact
    linking.
  - `ReorderBufferAbort(rb, xid, lsn, abort_time)`,
    `ReorderBufferAbortOld(rb, oldestRunningXid)`,
    `ReorderBufferForget(rb, xid, lsn)`,
    `ReorderBufferInvalidate(rb, xid, lsn)` — discard paths.
  - `ReorderBufferSetBaseSnapshot`, `ReorderBufferAddSnapshot`,
    `ReorderBufferAddNewCommandId`, `ReorderBufferAddNewTupleCids`,
    `ReorderBufferAddInvalidations`,
    `ReorderBufferAddDistributedInvalidations`,
    `ReorderBufferImmediateInvalidation` — catalog-time-travel
    plumbing.
  - `ReorderBufferProcessXid(rb, xid, lsn)` — touch-only "this xid
    exists" used during decoding.
  - `ReorderBufferXidSetCatalogChanges`,
    `ReorderBufferXidHasCatalogChanges`,
    `ReorderBufferXidHasBaseSnapshot` — flag accessors.
  - `ReorderBufferRememberPrepareInfo`, `ReorderBufferSkipPrepare`,
    `ReorderBufferPrepare` — two-phase support.
  - `ReorderBufferGetOldestTXN`, `ReorderBufferGetOldestXmin` —
    horizon queries used by snapshot retention.
  - `ReorderBufferGetCatalogChangesXacts` — for distributing
    invalidations across in-flight xacts.
  - `ReorderBufferSetRestartPoint(rb, ptr)` — slot restart_lsn
    advancement input.
  - `ReorderBufferGetInvalidations` — fetch a txn's invalidations.
  - `StartupReorderBuffer` — startup-time cleanup of stale spill
    files. [from-comment-and-code]

## Phase D notes

**Spill discipline & disk-bomb DoS.** `logical_decoding_work_mem`
(line 27) is the ONLY in-memory cap. There is **no documented per-txn
spill-to-disk cap or per-slot disk quota** in this header — bounded
only by:
1. `logical_decoding_work_mem` (memory; default 64MB). Beyond this,
   the biggest xact is picked from `txn_heap` and spilled to
   `pg_replslot/<slot>/xid-*.spill`.
2. Available disk space under `pg_replslot/`.
3. `max_slot_wal_keep_size` indirectly caps how long a slow consumer
   can hold WAL, but that's WAL retention, not spill files.

A pathological pattern: a publisher running a 100GB transaction (one
giant DELETE / COPY / catalog-touching xact) WILL spill ~100GB to
`pg_replslot/<slot>/`. A misbehaving subscriber that never consumes
makes the spill stick around until the xact's WAL is processed. This
is a known operational reality, not a CVE — but the header doesn't say
"watch disk", and `spillBytes` is the only built-in signal (line 686).
[verified-by-code in the spill path; the header carries no cap]

**`pg_logical/snapshots` and `pg_logical/mappings` lifecycle.** Both
directories accumulate files (`pg_logical/snapshots/X-Y.snap`,
`pg_logical/mappings/map-NNN`). Cleanup happens at restart and during
operation, but a crash mid-write can leave stragglers.
`StartupReorderBuffer` (line 784) cleans up stale files on startup.
[from-comment, line 21]

**ReorderBufferTXN size invariants.** `nentries_mem ≤ nentries`.
`total_size ≥ size`. The `txn_heap` max-heap is keyed by `total_size`.
If size accounting drifts (subxact assign/commit races), the heap is
ordered wrong and the wrong txn gets spilled. Lots of historical bugs
in this area; the inline macros at the top (rbtxn_is_*) document the
flag transitions but not the size invariants. [from-comment, lines
381-462]

**Catalog-change invalidations.** `RBTXN_DISTR_INVAL_OVERFLOWED`
(line 179) — when an xact's distributed invalidations exceed an
internal cap, the flag is set and decoding falls back to a
broader-but-correct invalidation. Cap value lives in reorderbuffer.c,
not here. [from-comment]

**Speculative insert internals.** `INTERNAL_SPEC_INSERT/CONFIRM/ABORT`
(lines 60-62) — INSERT ON CONFLICT emits a speculative insert WAL
record, decoded but not delivered until confirm. If a logical decoder
bug delivers a speculative-but-aborted insert, the subscriber gets
phantom rows. The output plugin contract is documented in the comment
(lines 45-48): "Users of logical decoding don't have to care". But the
reorderbuffer MUST care. [from-comment]

**Two-phase decoding.** `RBTXN_IS_PREPARED` (line 173),
`RBTXN_SENT_PREPARE` (line 176), `RBTXN_SKIPPED_PREPARE` (line 174) —
PREPARE is decoded as a separate event from COMMIT PREPARED. The
`SKIPPED` flag handles the case where the prepare was earlier than the
slot start LSN; the slot saw the COMMIT PREPARED only and must
fast-path through. [from-comment]

**Subscriber attack surface (via this header).** Reorderbuffer runs on
the PUBLISHER side, decoding the publisher's own trusted WAL. The
output plugin (pgoutput) then serializes changes and ships them to the
subscriber. So bytes touched here are trusted; the wire-protocol
serializer is in `logicalproto.h` / `pgoutput.c`. [verified-by-code]

## Potential issues

- [ISSUE-dos: per-transaction spill-to-disk is bounded only by
  available disk space + `logical_decoding_work_mem` (memory side); no
  per-slot quota, no per-xact cap; a 1TB UPDATE in a long pg_dump xact
  fills `pg_replslot/<slot>/` (maybe — documented operational risk,
  but no header-level cap)]
- [ISSUE-undocumented-invariant: `nentries_mem ≤ nentries` and
  `total_size ≥ size` invariants implicit; bugs that violate them
  cause the txn_heap to mis-rank spill candidates (low)]
- [ISSUE-undocumented-invariant: spill file naming convention
  (`pg_replslot/<slot>/xid-*.spill`) is hard-coded in reorderbuffer.c
  but not surfaced here; external tools that introspect must read
  source (low)]
- [ISSUE-stale-todo: `change_useless_for_repack` cross-cited from
  `decode.h:36` — if repack_worker.c is conditional, decode.h coupling
  is brittle (low)]
- [ISSUE-state-transition: `RBTXN_*` flag set transitions are
  documented per-flag (lines 184-274) but the legal combinations
  (e.g. `IS_PREPARED | IS_COMMITTED` reachable? `IS_ABORTED |
  IS_STREAMED`?) are not — must read code (low)]
- [ISSUE-info-disclosure: `output_plugin_private` on `ReorderBufferTXN`
  (line 467) is opaque; if the output plugin stashes secret material
  (credentials, etc.) the spill code would not serialize it (because
  spill is per-change, not per-txn-plugin-state), so cleanup is the
  plugin's responsibility — undocumented contract (low)]
- [ISSUE-undocumented-invariant: `final_lsn` overloaded meaning
  (commit-record LSN vs latest-spilled-change LSN, comment lines 317-330)
  is a footgun for code that compares LSNs across in-flight vs
  committed states (maybe)]

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new replication / logical-decoding message](../../../../scenarios/add-new-replication-message.md)

<!-- scenarios:auto:end -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->
