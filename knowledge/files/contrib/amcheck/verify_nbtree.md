# verify_nbtree.c

Covers `source/contrib/amcheck/verify_nbtree.c` (3591 lines). Source pin:
`4b0bf0788b0`.

## One-line summary

`bt_index_check(idx, heapallindexed, checkunique)` and
`bt_index_parent_check(idx, heapallindexed, rootdescend, checkunique)` —
walk every B-tree page top-down/left-to-right starting from the *true*
root (not the fast root), verifying per-page header sanity, per-tuple
size/natts, item ordering against an insertion scankey
(backward=true), high-key invariants, optional cross-level
downlink/parent agreement (`ShareLock` only), optional heap-side
"every visible heap tuple is in the index" via a Bloom filter, optional
unique-constraint cross-check, and optional root-descend reverification
of every leaf tuple.

## Public API / entry points

- `PG_MODULE_MAGIC_EXT(.name="amcheck", .version=PG_VERSION)` —
  `verify_nbtree.c:46-49`. This is the loadable-module marker for the
  whole extension (one of the heaviest files defines it).
- `Datum bt_index_check(PG_FUNCTION_ARGS)` — `:251-272`. 1/2/3 args
  (`heapallindexed`, `checkunique`). `AccessShareLock` via
  `amcheck_lock_relation_and_check(..., BTREE_AM_OID,
  bt_index_check_callback, AccessShareLock, &args)`.
- `Datum bt_index_parent_check(PG_FUNCTION_ARGS)` — `:283-306`.
  1/2/3/4 args (`heapallindexed`, `rootdescend`, `checkunique`).
  `ShareLock`.
- `PG_FUNCTION_INFO_V1` markers at `:176-177`.

### Static workers (call graph)

- `bt_index_check_callback` — `:312-352`. Validates metapage version,
  rejects equalimage-on-non-heapkeyspace, fires
  `bt_check_every_level`.
- `bt_check_every_level` — `:377-603`. Initializes
  `BtreeCheckState`, optionally registers MVCC snapshot for
  `heapallindexed`/`checkunique`, walks levels via
  `bt_check_level_from_leftmost`, then (if heapallindexed) drives
  `table_index_build_scan` with `bt_tuple_present_callback`.
- `bt_check_level_from_leftmost` — `:623-848`. Walk one level
  rightward; per-page calls `bt_target_page_check`; threads `lowkey`
  across pages.
- `bt_leftmost_ignoring_half_dead` — `:1009-1061`. Readonly-only
  helper: walks btpo_prev chain through half-dead pages to find the
  true leftmost.
- `bt_recheck_sibling_links` — `:1098-1198`. **The one place
  amcheck couples buffer locks** (`:1091-1093` comment, `lbuf` +
  `newtargetbuf` both held briefly).
- `bt_target_page_check` — `:1238-1844`. The per-page core.
- `bt_right_page_check_scankey` — `:1864-2065`. Cross-page item
  ordering scankey; long comment block explains the `!readonly`
  race tolerance (`:1881-2021`).
- `bt_child_check` — `:2391-2541`. ShareLock-only downlink-lower-
  bound check.
- `bt_child_highkey_check` — `:2144-2376`. Highkey ↔ pivot chain.
- `bt_downlink_missing_check` — `:2556-2722`. Missing-downlink
  classification (incomplete split vs top-of-deletion-chain vs real
  corruption).
- `bt_tuple_present_callback` — `:2779-2813`. Heapallindexed Bloom
  probe; raises `ERRCODE_DATA_CORRUPTED` on miss.
- `bt_normalize_tuple` — `:2847-2959`. Defeats false positives
  from heap vs index TOAST compression mismatch.
- `bt_posting_plain_tuple` — `:2975-2982`. Decompose posting list
  into N "plain" tuples for individual fingerprinting.
- `bt_entry_unique_check` / `bt_report_duplicate` —
  `:910-1001,870-907`. Visibility-aware unique check.
- `heap_entry_is_visible` — `:851-864`. Uses
  `table_tuple_fetch_row_version` against the registered snapshot.
- `bt_rootdescend` — `:3008-3058`. Drive `_bt_search` from the
  true root for each leaf tuple, then `_bt_binsrch_insert` +
  `_bt_compare` to verify presence.
- `palloc_btree_page` — `:3287-3449`. Per-page copy-into-palloc
  pattern; calls `_bt_checkpage` and a battery of
  ERRCODE_INDEX_CORRUPTED checks (metapage magic/version, level
  rules, half-dead/deleted/garbage flag combinations).
- `bt_mkscankey_pivotsearch` — `:3465-3474`. Wraps
  `_bt_mkscankey` to set `skey->backward = true`.
- `PageGetItemIdCareful` — `:3489-3523`. Bounds + flag check.
- `BTreeTupleGetHeapTIDCareful` — `:3529-3564`. Pivot/non-pivot
  agreement + TID-presence enforcement.
- `BTreeTupleGetPointsToTID` — `:3577-3591`. Returns the
  appropriate TID for an error-message string (heap TID or
  downlink TID).
- Inline invariant helpers: `invariant_l_offset`,
  `invariant_leq_offset`, `invariant_g_offset`,
  `invariant_l_nontarget_offset` — `:3105-3271`.

## Key invariants

### Metapage

- `_bt_metaversion` extracts `heapkeyspace`, `allequalimage`
  (`:325`). `allequalimage && !heapkeyspace` is rejected
  (`:326-330`) — equalimage can only exist in v4+ indexes.
- `allequalimage` claim must be backed by `_bt_allequalimage(rel,
  false)` returning true (`:331-347`); falsified claim with at
  least one `interval` opclass gives a hint pointing to the
  "interval indexes built before 2023-11" known issue.
- `btm_magic == BTREE_MAGIC`, `BTREE_MIN_VERSION <= btm_version
  <= BTREE_VERSION` (`:3328-3343`).
- `btm_root == P_NONE` is legal — totally empty index, walk
  loop exits immediately (`:523`).

### Per-page (palloc_btree_page, ~150 LOC of checks)

- `_bt_checkpage(rel, buffer)` — same routine production nbtree
  uses (`:3309`).
- `P_ISMETA(opaque) && blkno != BTREE_METAPAGE` → corruption
  (`:3317-3321`).
- Leaf page must have `btpo_level == 0`, internal must have
  `btpo_level > 0` (`:3358-3370`). Exempted when page is fully
  deleted with the old 32-bit XID representation (`btpo_level`
  is type-punned in old layout) — gate at `:3354`.
- `maxoffset > MaxIndexTuplesPerPage` → corruption
  (`:3392-3398`).
- Non-leaf, non-deleted page must have at least
  `P_FIRSTDATAKEY` items (`:3400-3404`).
- Non-rightmost leaf, non-deleted must have a high key
  (`:3406-3410`).
- **Internal page can't be half-dead** (`:3419-3424`) — pre-9.4
  state, treated as corruption.
- Internal page can't have garbage items (`:3430-3434`).
- `P_HAS_FULLXID && !P_ISDELETED` → corruption (`:3436-3440`).
- `P_ISDELETED && P_ISHALFDEAD` → corruption (`:3442-3446`).
- Page is copied into local memory after `_bt_checkpage` and the
  buffer immediately unpinned (`:3312-3313`) — defends against
  "uninterruptible state when an underlying operator class
  misbehaves" (`:3284`).

### Per-tuple (`bt_target_page_check`)

- `IndexTupleSize(itup) == ItemIdGetLength(itemid)` —
  `:1310-1327`. Errhint mentions "could be a torn page problem".
- `_bt_check_natts(rel, heapkeyspace, target, offset)` —
  `:1329-1353`. Wraps the same check production uses.
- For posting-list tuples: TIDs strictly increasing in
  ItemPointerCompare order — `:1406-1433`.
- Tuple size `<= BTMaxItemSize` (for leaf or pivot-with-heap-TID),
  `<= BTMaxItemSizeNoHeapTid` for pivot-without-heap-TID on heapkeyspace
  index — `:1438-1484`. Comment at `:1438-1461` explains the
  "reserved space for suffix truncation's heap TID" subtlety.
- Item < high key (`<= ` on leaf, strict `<` on internal) —
  `:1565-1591`. For posting-list tuples, scantid is set to the
  MAX heap TID in the list before comparison (`:1566-1567`),
  restored after.
- Item < next item on same page (strict, posting-aware) —
  `:1601-1640`.
- Last item on page < first item on right sibling (cross-page
  ordering) — `:1711-1816`. `!readonly` race tolerance:
  re-read target page; if `P_IGNORE(topaque)` now, just return
  (don't error) — `:1731-1743`. This is the
  "canary condition" that the long comment at
  `:1933-2021` rationalizes.
- Negative-infinity item handling: skip strict-less item-order
  comparison; still recurse into `bt_child_highkey_check`
  (`:1359-1374`).

### Per-page (readonly-only / `bt_child_check` /
   `bt_child_highkey_check` / `bt_downlink_missing_check`)

- For each downlink: `invariant_l_nontarget_offset` against
  child page — every child item strictly greater than the
  parent's pivot for that downlink (`:2498-2538`).
- `P_ISDELETED(copaque)` on a downlink target → ERROR
  ("downlink to deleted page found") — `:2489-2496`.
- Highkey of every child must match the corresponding pivot in
  parent via `bt_pivot_tuple_identical` (binary identical except
  block number); `:2348-2357`. Heapkeyspace and !heapkeyspace
  use different memcmp ranges (`:2076-2103`).
- For each leftmost-of-level page seen via rightlinks
  (`bt_child_highkey_check`), it must be leftmost
  ignoring half-dead — `:2219-2228`.
- Block level must match `target_level - 1` for any rightlink-
  reached non-deleted child — `:2230-2238`.
- Circular sibling-link detection: `blkno == prevrightlink ||
  blkno == opaque->btpo_prev` → ERROR — `:2241-2245`. Also at
  level boundary (`:787-791`).
- Missing downlink classification:
  - On root page: no parent exists, so missing-downlink is
    silent (`:2573-2574`).
  - With `previncompletesplit` flag: harmless interrupted
    page split, DEBUG1 (`:2599-2610`).
  - Leaf page without downlink that's also not incomplete-split:
    "leaf index block lacks downlink" → ERROR (`:2622-2629`).
  - Internal page without downlink: descend to leaf, check
    if leaf is half-dead and `BTreeTupleGetTopParent ==
    blkno`. If so, harmless ("interrupted multi-level deletion") and
    return (`:2697-2713`). Otherwise → ERROR (`:2715-2721`).
  - Half-dead leaf with `BTreeGetTopParent != blkno` → ERROR
    (dangling downlink — `:2688-2695`).

### Sibling-link mutual agreement

- `opaque->btpo_prev == leftcurrent` (the left-sibling we
  arrived from) unless `leftcurrent == P_NONE` and we're
  ignoring half-dead — `:769-770`. On disagreement, fall into
  `bt_recheck_sibling_links` which re-couples locks under
  `!readonly` to confirm it's not a concurrent split
  (`:1106-1189`).

### Uniqueness (`checkunique`)

- Posting list with multiple visible TIDs → duplicate within a
  single tuple → ERROR `index uniqueness is violated`
  (`:924-953`).
- Adjacent tuples with equal keys, both visible → duplicate.
  `_bt_compare` is called with `scantid=NULL` so heap-TID isn't
  a tiebreaker (`:1664-1667`).
- Visibility uses `table_tuple_fetch_row_version` against the
  registered snapshot (`:851-863`).
- Cross-page case: last tuple of left page equal-keyed to first
  tuple of right page, both visible → ERROR (`:1755-1815`).
  Comment notes that on a non-leaf right block we ERROR with
  `"right block of leaf block is non-leaf"` (`:1797-1804`).
- If a key has equal entries but NONE are visible, DEBUG1 with
  hint `"VACUUM the table and repeat the check"` — `:990-999`.

### Heapallindexed (Bloom filter)

- Bloom filter sized as
  `max(total_pages * MaxTIDsPerBTreePage / 3, reltuples)`,
  capped at `maintenance_work_mem`. Seeded via
  `pg_prng_uint64(&pg_global_prng_state)` to avoid attacker
  pre-computing seed (`:427-433`).
- Each leaf tuple (or each posting-list element treated as a
  plain tuple) is normalized then added to the filter
  (`:1486-1517`).
- After level walk completes, `table_index_build_scan` runs the
  callback; every fingerprintable heap tuple must be in the
  filter (`:548-589`). False-positive rate is the Bloom
  filter's nominal rate, so missing index tuples are detected
  probabilistically but with high confidence at usual sizes.
- Snapshot registered via `RegisterSnapshot(GetTransactionSnapshot())`
  at `:443`. Comment at `:446-455` explains why we need a fresh
  MVCC snapshot, and why a higher-iso-level pre-existing xact
  snapshot is rejected via the `indcheckxmin` test at `:457-463`.
- TOAST-compression mismatch normalization
  (`bt_normalize_tuple`, `:2847-2959`) is the defense against a
  whole class of false-positives where heap tuples are TOAST-
  compressed but the corresponding index tuples were not
  (because `index_form_tuple` makes its own decision).

### Rootdescend

- Only valid with `readonly && heapkeyspace` (`:480-485`).
- For each non-pivot leaf tuple: `_bt_search` from root with
  `BT_READ`, then `_bt_binsrch_insert` + `_bt_compare` —
  `:3008-3058`. Missing → ERROR ("could not find tuple using
  search from root page") — `:1382-1400`.
- This is the defense against transitive cross-level
  inconsistencies that `bt_child_check` and the high-key check
  miss (mentioned in `:2992-3007`).

## Notable internals

- **Locking model.** Per-page: `LockBuffer(buffer, BT_READ)`
  (`:3303`), page copied into palloc'd memory, buffer
  released immediately (`:3312-3313`). The ONE exception is
  `bt_recheck_sibling_links` which couples `lbuf` +
  `newtargetbuf` for the cross-sibling recheck
  (`:1108-1166`); both released before returning.
- **Memory.** Per-page `targetcontext` (`AllocSetContext`,
  `ALLOCSET_DEFAULT_SIZES`, `:488-490`) reset per page
  (`:833`). `lowkey` allocated in `oldcontext` (parent of
  targetcontext) so it survives the per-page reset (`:828`).
- **Read strategy.** `BAS_BULKREAD` (`:491`).
- **CHECK_FOR_INTERRUPTS** in level loop (`:653`),
  bt_child_highkey_check (`:2641`), and per-tuple
  `bt_target_page_check` loop (`:1305`).
- **True root vs fast root.** Walk starts from `btm_root`
  not `btm_fastroot` — comment at `:497-503` explains the
  "skinny B-tree" deletion-pattern case where they differ.
- **Per-page scankey is built with `backward=true`** via
  `bt_mkscankey_pivotsearch` (`:3465-3474`). Comment at
  `:3451-3464` says this is required to make truncated/minus-
  infinity attribute comparisons strict.
- **Concurrent-split tolerance for `!readonly`**. Walker
  tolerates pages being split out from under it via the
  re-read-target-and-check-P_IGNORE escape (`:1731-1743`),
  the bt_recheck_sibling_links lock coupling, and
  bt_leftmost_ignoring_half_dead reasoning.
- **No special handling for parallel-query.** The functions
  are declared `PARALLEL RESTRICTED` in
  `amcheck--1.0.sql:12,20`,
  `amcheck--1.0--1.1.sql:14,22`,
  `amcheck--1.1--1.2.sql:14`,
  `amcheck--1.2--1.3.sql` (no PARALLEL marker on
  verify_heapam),
  `amcheck--1.3--1.4.sql:11,19`. So no parallel-leader/worker
  cooperation; single backend.
- **Snapshot for unique + heapallindexed shared if both
  active** — `:471-477`.

## Trust boundary / Phase D surface

- **Error-message content.** `errdetail_internal` strings
  include `tid=(blk,off)`, page LSN
  (`LSN_FORMAT_ARGS`), heap-TID coords, tuple natts,
  byte-counts. They do NOT include user-attribute datum
  contents. So with a non-superuser GRANT, the invoker learns
  physical layout but not user data — like verify_heapam.
  However, **page LSN is a side channel of write timing**:
  observing the LSN over many corruption-finding calls leaks
  per-page write activity to a low-priv invoker.
  [ISSUE-security: page LSN in errdetail leaks per-page write
  timing to non-superuser invokers (maybe)] —
  `verify_nbtree.c:1274-1278,1322-1327,1397-1399,1426-1428,
  1478-1483,1585-1590,1632-1639,2226-2228,2312-2314,
  2354-2356,2493-2496`. Endemic across the file.
- **`elog(ERROR, ...)` is exceptional.** Almost all corruption
  reports go through `ereport(..., ERRCODE_INDEX_CORRUPTED,
  ...)` with proper SQLSTATE; bare `elog` is only used in
  `bt_tuple_present_callback` for `ERRCODE_DATA_CORRUPTED`
  (the heap-tuple-not-in-index case at `:2797-2806`). Good.
- **No accumulation.** First corruption finding → ERROR →
  whole call aborts. Compare with `verify_heapam` (tuplestore
  + on_error_stop). Means a 1TB index check that finds a
  corruption near the start gives the user one finding then
  exits. Documented trade-off.
- **`ShareLock` cost.** `bt_index_parent_check` blocks INSERT
  / UPDATE / DELETE / VACUUM for the duration. On a hot
  index this can be many minutes. The function does NOT
  yield via vacuum_delay_point; only `CHECK_FOR_INTERRUPTS`.
  [ISSUE-defense-in-depth: bt_index_parent_check holds
  ShareLock for full walk with no cost-based yield (nit)] —
  `verify_nbtree.c:653,1305,2641` are the only interrupt
  polls.
- **Buffer-pinning DoS.** One pin at a time on target; up to
  3 simultaneous in `bt_recheck_sibling_links`
  (`lbuf` + `newtargetbuf` + possible target re-read), and
  up to 1 extra in `bt_child_check` for the child page. On
  very wide indexes, sustained pin churn but no exhaustion.
- **Heapallindexed snapshot churn.** Registers MVCC snapshot
  at start of walk (`:443`); held across level walk + heap
  scan. Comment at `:457-463` rejects pre-existing higher-iso
  snapshots whose xmin precedes `indcheckxmin`. Reasonable.
- **`rootdescend` cost.** O(N log N) where N = number of
  leaf tuples — each tuple drives a full root-down search.
  Multiplies the basic O(N) walk. Documented as expensive in
  user docs.
- **Bloom seed is `pg_prng_uint64(&pg_global_prng_state)`**.
  Not crypto-strong but mutates each call. An attacker who
  can deterministically corrupt heap tuples AND predict the
  global PRNG state could craft tuples that hit the same
  bits in the filter as some legitimate tuple. Required
  attacker capability is high.
  [ISSUE-defense-in-depth: heapallindexed bloom seed from
  global PRNG, not from cryptographic source (nit)] —
  `verify_nbtree.c:431`.
- **Concurrent VACUUM tolerance.** Lots of comment material
  explaining race tolerance. The key invariant: VACUUM page
  recycling does not happen until "no possible index scan
  could land on the page" (`:1890-1896`). Walker relies on
  this.
- **`_bt_unlink_halfdead_page` doesn't change sibling
  links.** Comment at `:1031-1039` says half-dead pages keep
  side-links pointing to siblings, so walking
  btpo_prev through half-dead chains is valid.
- **`_bt_search` from C** — `bt_rootdescend` directly calls
  `_bt_search(rel, NULL, key, &lbuf, BT_READ, false)` (`:3028`).
  `snapshot=NULL` and `access=BT_READ` means it doesn't
  contribute to snapshot visibility — purely structural
  probe.
- **Half-dead detection mid-walk** can cause walker to step
  through chains of harmless interrupted deletions
  (`:1009-1061`). On extreme corruption (looped chain), the
  circular-link check at `:1031-1039` saves us.
- **The `bt_pivot_tuple_identical` binary comparison**
  (`:2071-2104`) trusts that
  `IndexTupleSize(itup1) == IndexTupleSize(itup2)`. If both
  are corrupt with matching wrong sizes, memcmp passes
  spuriously. In practice the size mismatch with parent's
  cached pivot would already be caught elsewhere.
- **`bt_normalize_tuple` for heapallindexed false-positive
  avoidance** (`:2847-2959`) is the canonical defense
  against the TOAST-compression-mismatch class of false
  positives. It will `ereport(ERROR, ...)` if it finds an
  EXTERNAL varlena in an index tuple (`:2884-2890`) — those
  shouldn't exist (indexes don't store external toast
  pointers).
- **HOT-chain trap in `bt_tuple_present_callback`.** The
  callback gets the **root TID** of any heap-only tuple, not
  the heap-only tuple's TID itself (comment at `:2750-2777`
  describes the cooperation with `table_index_build_scan`).
  This means a corrupted "lying root TID" is detected
  because the values delivered to the callback won't match
  the index tuple's contents. This is the canonical defense
  against `HOT-safety-evaluation-was-wrong` bugs.
- **Negative-infinity comparison hard-coded in
  `_bt_compare`.** Comment at `:3064-3094` is the
  authoritative explanation for why the
  `offset_is_negative_infinity` check exists (negative-
  infinity items aren't comparable and would give wrong
  answers).
- **The `bt_index_check` SECURITY_RESTRICTED_OPERATION**
  switch (in verify_common.c, NOT here) protects against
  index expression code running as the invoker. The
  expression IS evaluated during `_bt_mkscankey`
  (`:1436,3015`).
- **`PG_MODULE_MAGIC_EXT` is defined here.** If amcheck is
  ever split into multiple compilation units that all need
  it, only verify_nbtree.c may declare it.

## Cross-references

- Backend nbtree: `access/nbtree/nbtsearch.c`
  (`_bt_search`, `_bt_binsrch_insert`, `_bt_compare`),
  `access/nbtree/nbtutils.c` (`_bt_mkscankey`,
  `_bt_check_natts`), `access/nbtree/nbtpage.c`
  (`_bt_checkpage`, `_bt_metaversion`,
  `_bt_allequalimage`, `_bt_relbuf`),
  `access/nbtree/nbtdedup.c` (`_bt_form_posting`),
  `access/nbtree/README` (the long file at
  `access/nbtree/README` is the prose backing of the
  invariants).
- Bloom filter: `lib/bloomfilter.h`/`.c` (`bloom_create`,
  `bloom_add_element`, `bloom_lacks_element`,
  `bloom_prop_bits_set`).
- Catalog/index: `catalog/index.c` (`BuildIndexInfo`,
  `IndexInfo`).
- Snapshot: `utils/time/snapmgr.c` (`RegisterSnapshot`,
  `UnregisterSnapshot`).
- TableAM: `access/table/tableam.c`
  (`table_index_build_scan`, `table_tuple_fetch_row_version`).
- amcheck siblings: `verify_common.c` (locking gate),
  `verify_heapam.c` (heap-side counterpart). A6 documented
  `pg_amcheck` (frontend wrapper).
- Phase A prior sweeps: A11 contrib top-4 (pg_amcheck is in
  A6 sweep), A10 contrib sixth-tier.

## Issues spotted

- [ISSUE-security: page LSN exposed in errdetail across
  ~12 sites — leaks per-page write timing to a non-
  superuser with EXECUTE grant (maybe)] —
  `verify_nbtree.c:1274,1322,1397,1426,1478,1585,1632,
  2226,2312,2354,2493,2693` (representative; the pattern is
  endemic).
- [ISSUE-correctness: heap-TID and downlink-block in
  errdetail leak physical layout to non-superuser invoker
  (maybe)] — `verify_nbtree.c:1397-1399,2491-2496`.
- [ISSUE-defense-in-depth: heapallindexed Bloom seed from
  `pg_global_prng_state`, not cryptographic source (nit)]
  — `verify_nbtree.c:431`.
- [ISSUE-defense-in-depth: bt_index_parent_check holds
  ShareLock for entire walk; no vacuum_delay_point /
  cost yield (nit)] — `verify_nbtree.c:653,1305,2641`
  (only interrupt polls).
- [ISSUE-concurrency: under !readonly the `lowkey`
  threading across pages "wasn't investigated yet" for
  concurrent splits (likely / from-comment)] —
  `verify_nbtree.c:815-818`. Documented gap.
- [ISSUE-concurrency: missing-P_NONE-validation in
  bt_recheck_sibling_links left-side traversal under
  !readonly (likely / from-comment)] —
  `verify_nbtree.c:762-768`. `bt_leftmost_ignoring_half_dead`
  is Assert'd readonly-only (`:1022`); the analogous race
  in !readonly mode is unimplemented.
- [ISSUE-correctness: `bt_pivot_tuple_identical` is a
  raw `memcmp` — if both pivot copies are corrupt with
  the same wrong size and contents, it returns true and
  amcheck misses the corruption (nit / unverified
  practical impact)] — `verify_nbtree.c:2071-2104`.
- [ISSUE-error-handling: first corruption finding aborts
  whole call (`ereport(ERROR, ...)`). On a 1TB index this
  means one finding then stop; no `on_error_stop`-style
  knob (api-shape)] — endemic; e.g.
  `verify_nbtree.c:1318-1327`.
- [ISSUE-defense-in-depth: `bt_rootdescend` re-uses the
  walking process's transaction snapshot indirectly via
  `_bt_search(NULL, ...)` — passes `NULL` snapshot. Means
  the descend ignores visibility, which is correct for
  structural probe but worth documenting (nit)] —
  `verify_nbtree.c:3028`.
- [ISSUE-audit-gap: `checkunique` reuses
  `state->snapshot` set up for heapallindexed when both
  are active (`:471-477`); independent registration paths
  could allow one to disable the other in future
  refactors (nit)].
- [ISSUE-concurrency: `bt_recheck_sibling_links` couples
  buffer locks under !readonly — the only place in
  amcheck that does so. Documented but increases deadlock
  surface vs production nbtree (`bt_search` doesn't
  couple) (nit / from-comment at `:1090-1097`)] —
  `verify_nbtree.c:1108-1166`.
- [ISSUE-defense-in-depth: `bt_normalize_tuple` raises
  `ereport(ERROR, ERRCODE_INDEX_CORRUPTED, ...)` if it
  encounters an EXTERNAL varlena in an index tuple — but
  this is reached via heapallindexed Bloom flow which
  already trusts that the index was loaded from a valid
  page. A poisoned heap tuple flowing in via
  `table_index_build_scan` callback would surface as a
  Bloom miss, not this error (api-shape)] —
  `verify_nbtree.c:2884-2890`.
- [ISSUE-documentation: rootdescend is "expensive" only
  in user docs, not in C-side function comment; should
  cite O(N log N) (nit)] — `verify_nbtree.c:283-306`.
- [ISSUE-correctness: pre-9.4 half-dead-internal-page
  ERRORs (`:3419-3424`) suggest REINDEX, but on a hot
  standby `REINDEX` is impossible. Hint message could be
  more nuanced. (nit)]
