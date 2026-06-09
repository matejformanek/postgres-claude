# contrib/bloom/blvacuum.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 260
**Verification depth:** full read

## Role

Implements `blbulkdelete` (the per-pass tuple-killing pass) and
`blvacuumcleanup` (post-pass FSM update + statistics gather) for the
bloom AM. Bloom's vacuum is unusually simple because the index AM is
lossy and there's no internal tree structure to rebalance — we just
compact each page in place and rebuild the `notFullPage` cursor.
[verified-by-code] `source/contrib/bloom/blvacuum.c:1-12`

## Public API

- `blbulkdelete(info, stats, callback, callback_state) →
  IndexBulkDeleteResult*`
  [verified-by-code] `source/contrib/bloom/blvacuum.c:30-180`
- `blvacuumcleanup(info, stats) → IndexBulkDeleteResult*` — registers
  empty pages with FSM and recomputes per-page tuple counts.
  [verified-by-code] `source/contrib/bloom/blvacuum.c:187-259`

## Invariants

- INV-1: Pages emptied by deletion are flagged `BloomPageSetDeleted` —
  cleanup will then add them to the FSM.
  [verified-by-code] `source/contrib/bloom/blvacuum.c:141-143, 240-244`
- INV-2: `vacuum_delay_point(false)` called at the top of every page
  iteration in both passes — respects vacuum cost limits.
  [verified-by-code] `source/contrib/bloom/blvacuum.c:82, 234`
- INV-3: WAL-logging is conditional in `blbulkdelete` — `GenericXLogAbort`
  if no tuple was actually removed (no dirty change), `GenericXLogFinish`
  only after a real change.  Important: prevents spurious WAL when a
  vacuum pass touches every page but deletes nothing.
  [verified-by-code] `source/contrib/bloom/blvacuum.c:138-153`
- INV-4: `notFullPage` array is *rebuilt from scratch* by `blbulkdelete`
  — old entries are discarded; `nStart=0, nEnd=countPage` after the
  metapage update.
  [verified-by-code] `source/contrib/bloom/blvacuum.c:160-177`
- INV-5: `analyze_only` skips cleanup entirely (no FSM updates).
  [verified-by-code] `source/contrib/bloom/blvacuum.c:196-197`

## Notable internals

- **In-place compaction** via `memmove` of surviving tuples toward
  the page start. `itupPtr` tracks where to write next; `itup` walks
  through all tuples. When `itupPtr != itup`, something was deleted.
  [verified-by-code] `source/contrib/bloom/blvacuum.c:98-123`
- **Streaming reads** in both passes (`READ_STREAM_MAINTENANCE |
  READ_STREAM_FULL | READ_STREAM_USE_BATCHING`).
  [verified-by-code] `source/contrib/bloom/blvacuum.c:62-74, 215-227`
- **`pd_lower` is recomputed** after compaction to match the new tuple
  region end.
  [verified-by-code] `source/contrib/bloom/blvacuum.c:145`
- **`notFullPage` cap** = `BloomMetaBlockN` (number of BlockNumbers
  fitting in the metapage). If more pages than that have free space,
  only the first `BloomMetaBlockN` are tracked.
  [verified-by-code] `source/contrib/bloom/blvacuum.c:133-136`

## Trust-boundary / Phase-D surface

- **Vacuum runs under either operator (manual VACUUM) or autovacuum
  worker privileges** — typical PG vacuum surface, no bloom-specific
  attack vector.
- **Concurrent inserter / vacuum interaction**: blinsert acquires
  metaPage SHARE then EXCLUSIVE; blbulkdelete only takes metaPage
  EXCLUSIVE at the very end (line 165-166). Between concurrent
  blinsert and a still-running blbulkdelete the `notFullPage` view
  may be stale, but blinsert tolerates it (re-reads under exclusive
  lock).  Documented in blinsert's comment "Our info could already
  be out of date at this point, but blinsert() will cope if so" (line
  161-163).
  [verified-by-code] `source/contrib/bloom/blvacuum.c:160-163`
- **No CHECK_FOR_INTERRUPTS in the inner per-tuple loop** — relies on
  `vacuum_delay_point(false)` at the page boundary. For very wide
  pages with thousands of tuples this could in theory delay cancel
  responsiveness, but bloom page tuple count is bounded by
  `BLCKSZ/sizeOfBloomTuple` (so ~hundreds at most).
  [inferred] from `source/contrib/bloom/blvacuum.c:105-123`

## Cross-refs

- `source/src/backend/commands/vacuum.c`.
- `source/src/backend/storage/freespace/indexfsm.c`.
- Sibling: `blinsert.c` (compatibility comment chain).

## Issues raised

None of substance — bloom's vacuum is simple and well-disciplined.
