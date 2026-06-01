# `src/backend/replication/logical/reorderbuffer.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 5643 (largest file in the subsystem)
- **Source:** `source/src/backend/replication/logical/reorderbuffer.c`

## Purpose

Reassembles per-record decoded WAL into top-level transactions. Records
arrive in WAL (interleaved) order; subtransactions don't link to parents
until commit/abort/xact_assignment. ReorderBuffer keeps per-xid streams
of `ReorderBufferChange`, splices sub-into-top at link time, and emits
them in commit order via a k-way merge using a binary heap keyed by the
smallest LSN in each substream. [from-comment] (`reorderbuffer.c:13-31`)

## Big invariants

- **Spill to disk on memory pressure.** When total RB memory exceeds
  `logical_decoding_work_mem`, the largest transaction is serialized to
  disk and freed from RAM. Uses BufFiles. A max-heap keyed by per-txn
  size finds the victim in O(log n). Transactions of size 0 are not in
  the heap. (`:52-73`) [from-comment]
- **Two specialized contexts.** SlabContext for fixed-size structs
  (ReorderBufferChange, ReorderBufferTXN); GenerationContext for variable
  txn payload — chosen so freeing whole groups is O(1). (`:47-50`)
  [from-comment]
- **Reload still bounded by `max_changes_in_memory`.** When reading spilled
  changes back at replay time, can't use the global memory limit because
  sub-streams are loaded independently. (`:75-83`) [from-comment]
- **Toast reassembly.** Toast chunks for a row are guaranteed to immediately
  precede the row record in WAL within a single top-level txn, so we
  buffer them until the main row arrives. See `ReorderBufferToast*`
  functions. (`:39-45`)
- **Invalidation overflow.** Per-txn cap of 8MB of distributed invalidation
  messages; over that, mark `RBTXN_DISTR_INVAL_OVERFLOWED` and force full
  cache invalidation since we no longer know exactly what to invalidate.
  (`:118-127`)

## Spine API (called from `decode.c`, `logical.c`, `worker.c`)

- `ReorderBufferAllocate` (`:325`) / `Free` (`:418`) — lifecycle.
- `ReorderBufferQueueChange` (`:811`) — enqueue a `ReorderBufferChange`
  for an xid.
- `ReorderBufferQueueMessage` (`:874`) — generic logical message.
- `ReorderBufferAssignChild` (`:1100`) — link sub-xact to its top-level.
- `ReorderBufferCommitChild` (`:1220`) — finalize sub-on-top mapping at
  abort/commit time.
- `ReorderBufferCommit` (`:2882`) → `ReorderBufferReplay` (`:2821`) →
  `ReorderBufferProcessTXN` (`:2212`) — drive the iterator and call the
  output-plugin callbacks via `logical.c` wrappers.
- `ReorderBufferIterTXNInit/Next/Finish` (`:1285`, `:1413`, `:1505`) —
  the k-way merge iterator over (possibly disk-spilled) sub-streams.
- `ReorderBufferPrepare` / `FinishPrepared` / `Abort` / `Forget` /
  `Invalidate` (`:2958`, `:2999`, `:3085`, `:3178`, `:3220`) — 2PC and
  cleanup paths.
- `ReorderBufferChangeMemoryUpdate` (`:3383`) — central accounting; also
  updates the max-heap and triggers spill if over limit.
- `ReorderBufferStreamCommit` (`:1984`) — emit a streamed in-progress
  txn's COMMIT.

## Visibility helpers

- `ResolveCminCmaxDuringDecoding` (referenced by `snapbuild.c`) — uses
  the `(rlocator, ctid) → (cmin, cmax)` map populated from
  `XLOG_HEAP2_NEW_CID` records so a mixed-DDL/DML xact can see its own
  prior catalog changes. (`reorderbuffer.c:136-149`, `snapbuild.c:40-53`)

## State / on-disk structures

- `ReorderBufferTXNByIdEnt` (`:130`) — xid → txn lookup.
- `ReorderBufferDiskChange` (`:191`) — on-disk wire format for spilled
  changes; size-prefixed.
- `TXNEntryFile` (`:152`) — VFD + offset tracker for one subxact's spill
  file.

## Open questions

- The eviction policy is "largest only", but the top comment notes that
  age (LSN) might be a better heuristic, especially given the generation
  allocator's freeing pattern. (`:64-68`) [from-comment]
