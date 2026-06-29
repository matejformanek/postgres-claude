# `src/backend/access/nbtree/nbtreadpage.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~3720
- **Source:** `source/src/backend/access/nbtree/nbtreadpage.c`

PG18 split-out of the btree leaf-page reading logic, formerly in
`nbtutils.c`. Owns the bulk of the per-tuple scan-key checking,
SAOP/skip-array advancement, and the "scan behind" / "opposite
direction" key checks used in primitive scans. This is one of the
hottest code paths in the entire backend on indexed read workloads.
[verified-by-code §nbtreadpage.c:1-26]

## API / entry points

- **`bool _bt_readpage(IndexScanDesc scan, ScanDirection dir,
  OffsetNumber offnum, bool firstpage)`** — the workhorse called
  from `_bt_first` / `_bt_next` after positioning to a leaf page.
  Returns true if any matching items were saved into
  `so->currPos.items`. Behavioural shape:
  - Captures `currPos.{currPage, prevPage, nextPage}` from the
    page's opaque (`btpo_prev` / `btpo_next`).
  - For parallel scans, `_bt_parallel_release` is called BEFORE
    reading the page contents — the comment is explicit ("allow
    next/prev page to be read by other worker without delay"). This
    means a parallel worker can be reading page N's contents while
    another worker is already reading page N+1.
  - `PredicateLockPage` on the current page block.
  - For SAOP (`arrayKeys`) forward scans, the right-page hikey is
    read up front (`pstate.finaltup`) so `_bt_scanbehind_checkkeys`
    can decide whether to advance to a new primitive index scan.
  - Walks tuples in `dir`, calling `_bt_checkkeys` per tuple.
  - Schedules a follow-on primitive scan via
    `_bt_parallel_primscan_schedule` when array advancement requires
    repositioning. [verified-by-code §nbtreadpage.c:118-535]
- **`void _bt_start_array_keys(IndexScanDesc, ScanDirection)`** —
  initialises array-key positions to low (or high, for backward) at
  the start of a primitive scan. [verified-by-code §nbtreadpage.c:537-591]
- **Helpers (all `static`):**
  - `_bt_set_startikey` — fast-skip the first N scan keys that are
    already known to be satisfied for all tuples on this page.
  - `_bt_saveitem`, `_bt_setuppostingitems`, `_bt_savepostingitem`
    — buffer matching index tuples into `so->currPos.items`,
    including expanding posting-list tuples into one entry per heap
    TID.
  - `_bt_checkkeys` — per-tuple key-check dispatch (the entry point
    that pulls in `_bt_check_compare` for plain keys and
    `_bt_check_rowcompare` for row comparisons).
  - `_bt_check_compare` / `_bt_check_rowcompare` /
    `_bt_rowcompare_cmpresult` — the actual qual evaluators.
  - `_bt_tuple_before_array_skeys` — used by SAOP forward scans to
    decide whether the current tuple is still ahead of where the
    array keys point.
  - `_bt_checkkeys_look_ahead` — look-ahead skip for SAOP scans.
  - `_bt_advance_array_keys{,_increment}`,
    `_bt_array_{increment,decrement,set_low_or_high}`,
    `_bt_skiparray_set_{element,isnull}` — array-key state machine.
  - `_bt_compare_array_skey`, `_bt_binsrch_array_skey`,
    `_bt_binsrch_skiparray_skey` — binary search inside array keys.
  - `_bt_verify_keys_with_arraykeys` — assert-mode sanity check.
  - `_bt_scanbehind_checkkeys` / `_bt_oppodir_checkkeys` — special
    checks at primitive-scan boundaries to decide whether the next
    primitive scan can simply continue or must reposition.

## Notable invariants / details

- **`BTReadPageState` is stack-allocated per call** and threaded
  through every `_bt_checkkeys` invocation. It carries both the
  inputs (`dir`, `minoff`, `maxoff`, `finaltup`, `firstpage`,
  `forcenonrequired`, `startikey`, `offnum`) and the outputs (`skip`,
  `continuescan`) plus private SAOP state (`rechecks`,
  `targetdistance`, `nskipadvances`). [verified-by-code §nbtreadpage.c:31-58]
- **Parallel-release happens before page work** — see comment
  "allow next/prev page to be read by other worker without delay".
  This is the parallel-scan throughput win and the source of much
  of the parallel SAOP complexity.
  [from-comment §nbtreadpage.c:188-196]
- **Buffer pin invariant:** `Assert(BTScanPosIsPinned(so->currPos))`
  — the page is held pinned (but not necessarily content-locked
  anymore — see `_bt_drop_lock_and_maybe_pin`) for the duration of
  `_bt_readpage`. The LSN of the page is saved later in
  `_bt_drop_lock_and_maybe_pin`, not here. [verified-by-code §nbtreadpage.c:163, comment 155-156]
- **`P_IGNORE(opaque)` asserted false** — the caller (`_bt_first` /
  `_bt_step`) has already skipped half-dead / deleted pages by the
  time we get here. [verified-by-code §nbtreadpage.c:162]
- **SAOP "scan behind" mechanism:** when the rightmost item visible
  on the current page wouldn't satisfy the array keys, we set
  `currPos.moreRight = false` and `needPrimScan = true`, then return.
  The parallel-scan version additionally schedules the next prim
  scan so workers don't race. [verified-by-code §nbtreadpage.c:211-227]
- **`forcenonrequired`** is a knob used in some `_bt_set_startikey`
  paths to ignore "required" status of keys when the tuple is from a
  posting list that's been pre-filtered. [from-comment §nbtreadpage.c:40]

## Potential issues

- **Huge file (3.7k lines)** that hosts both the hot path
  (`_bt_readpage`) and roughly fifteen helper static functions.
  Splitting array-key advancement into its own TU might improve
  build times and i-cache behaviour on the hot path. The pre-PG18
  layout had this scattered across `nbtutils.c`; the new split
  unified ALL the page-read logic but didn't separate "read" from
  "array-keys state machine". [ISSUE-question: further split array-keys vs page-read? (maybe)]
- **`_bt_readpage` is one ~400-line function** with the parallel +
  SAOP + non-SAOP forward + backward code interleaved. Worth a deep
  read by anyone touching btree scans. No actionable issue, just a
  complexity flag. [ISSUE-style: _bt_readpage length and conditional density (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `access`](../../../../../issues/access.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-nbtree.md](../../../../../subsystems/access-nbtree.md)
