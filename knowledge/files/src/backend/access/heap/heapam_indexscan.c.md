# `src/backend/access/heap/heapam_indexscan.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~298
- **Source:** `source/src/backend/access/heap/heapam_indexscan.c`

Implements the heap-AM side of the table-AM index-scan callbacks
(`IndexFetchTableData` lifecycle) plus the shared `heap_hot_search_buffer`
helper that walks a HOT chain and returns the first
snapshot-visible member. Called by index-scan and index-only-scan
executor nodes after the indexAM hands them a TID. [verified-by-code]

## API / entry points

- `heapam_index_fetch_begin(rel, flags)` — allocate
  `IndexFetchHeapData`, init `xs_cbuf`, `xs_blk`, `xs_vmbuffer` to
  invalid. [verified-by-code]
- `heapam_index_fetch_reset(scan)` — explicit no-op; comment (lines 44-50)
  says pin retention is deliberate to avoid pin/unpin churn across
  rescans in tight nested-loop joins. [from-comment]
- `heapam_index_fetch_end(scan)` — release `xs_cbuf` and `xs_vmbuffer`
  pins if held; pfree the descriptor. [verified-by-code]
- `heap_hot_search_buffer(tid, rel, buffer, snapshot, heapTuple,
  *all_dead, first_call)` — walks the HOT chain starting at `*tid`.
  Caller holds (at least) pin + share lock on the buffer; we keep both.
  Returns true and updates `*tid` to the visible member's offset on a
  hit; false on miss. Optionally tracks `*all_dead = true` iff every
  chain member is globally dead (a hint for index vacuuming).
  [verified-by-code]
- `heapam_index_fetch_tuple(scan, tid, snapshot, slot, *heap_continue,
  *all_dead)` — top-level callback: swap the pinned buffer if the TID's
  block changed, opportunistically `heap_page_prune_opt` on first pin,
  share-lock, call `heap_hot_search_buffer`, then store into the slot.
  Sets `*heap_continue = true` only for non-MVCC snapshots (where >1
  HOT chain member can be visible). [verified-by-code]

## Notable invariants / details

- `xs_blk` caches the last-fetched block number; identical-block TIDs
  reuse the same `xs_cbuf` pin without re-reading or re-pinning (line
  244-263). This is the index-scan equivalent of HOT's locality
  optimisation. [verified-by-code]
- First time a page is pinned in a scan, `heap_page_prune_opt` is called
  (lines 260-262), passing the scan's `SO_HINT_REL_READ_ONLY` flag
  through. The opt-prune is opportunistic — it only runs if a quick
  cost check passes inside the called routine. [verified-by-code]
- HOT-chain walk invariants in `heap_hot_search_buffer`:
  - Redirected line pointers are only valid at `at_chain_start`; if a
    redirect is seen mid-chain, the chain is treated as broken and the
    loop exits (lines 130-139). [verified-by-code]
  - `prev_xmax` of one chain member must equal `xmin` of the next; if
    not, the chain is considered broken (lines 160-166). This is the
    invariant that detects truncated chains after a crash before redo.
    [from-comment]
  - First member must not have `HEAP_ONLY_TUPLE` set (line 156); if it
    does, the chain root has been pruned but the line pointer hasn't
    been updated — also treated as end of chain. [verified-by-code]
- `PredicateLockTID` is called *after* visibility is confirmed (line
  185) — SSI sees only visible TIDs. [verified-by-code]
- `Assert(BufferGetBlockNumber(buffer) == blkno)` (line 114) — caller is
  responsible for having pinned the right buffer; this is an invariant,
  not a check that converts to runtime error. [verified-by-code]
- `Assert(TransactionIdIsValid(RecentXmin))` (line 113) is the
  "is a snapshot pushed or registered" check; the comment one line
  above marks it as a weaker substitute. [from-comment]
  [ISSUE-undocumented-invariant: "we should assert that a snapshot is
  pushed or registered" XXX at line 112 — using RecentXmin as a proxy
  (nit)]
- `all_dead` is set conservatively: on the first call it starts true
  (line 105), and is downgraded to false on any non-dead member or on
  any visible match (line 187-188). [verified-by-code]
- Non-MVCC snapshots may legitimately see multiple HOT-chain members
  (e.g. SnapshotAny used by index build / vacuum). The caller signals
  re-entry via `*heap_continue` (lines 282-286). [verified-by-code]

## Potential issues

- Line 112. `/* XXX: we should assert that a snapshot is pushed or
  registered */` is a long-standing XXX, only weakly substituted by the
  `RecentXmin` validity check. The proper invariant (snapshot is in
  ActiveSnapshotStack or RegisteredSnapshots) is not actually checked.
  [ISSUE-undocumented-invariant: stale XXX comment about missing
  assertion (nit)]
- Line 199-201. Comment "Note: if you change the criterion here for what
  is 'dead', fix the planner's `get_actual_variable_range()` function
  to match." — a cross-module invariant guarded only by a comment. Easy
  to violate when refactoring. [ISSUE-undocumented-invariant: dead-tuple
  criterion shared with optimizer/plan/analyzejoins.c
  get_actual_variable_range; no compile-time check (maybe)]
- Line 277. After `heap_hot_search_buffer`, `bslot->base.tupdata.t_self
  = *tid;` is written unconditionally — but `*tid` was just updated by
  the called function on a hit, so this is harmless (sets it to the
  current `tid`). On a miss, the caller will not use the slot. Cosmetic.
  [verified-by-code]
- Line 47. `heapam_index_fetch_reset` is genuinely a no-op; the comment
  is necessary because future maintainers might "fix" it by adding pin
  drops, which would regress nested-loop joins. The function is kept
  separate from `_end` only to preserve this contract. [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `access`](../../../../../issues/access.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-heap.md](../../../../../subsystems/access-heap.md)
