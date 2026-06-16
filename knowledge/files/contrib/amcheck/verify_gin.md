# verify_gin.c

Covers `source/contrib/amcheck/verify_gin.c` (792 lines). Source pin:
`4b0bf0788b0`.

## One-line summary

`gin_index_check(index regclass)` — single-arg SQL entry point that, holding
only `AccessShareLock`, depth-first walks the GIN entry tree, each posting
tree it references, and the leaf posting lists, asserting per-page header
sanity, key ordering, parent-high-key consistency, and posting-list ItemPointer
validity. Tolerates concurrent splits by re-finding the parent on apparent
violation.

## Public API / entry points

- `Datum gin_index_check(PG_FUNCTION_ARGS)` — `verify_gin.c:78-90` —
  PG_FUNCTION_INFO_V1, declared `PARALLEL` not set (i.e. parallel-unsafe by
  default since amcheck--1.4--1.5.sql line 6-8 omits PARALLEL). Acquires
  `AccessShareLock` via `amcheck_lock_relation_and_check(..., GIN_AM_OID,
  gin_check_parent_keys_consistency, AccessShareLock, NULL)` at
  `verify_gin.c:83-87`.
- Static workers:
  - `gin_check_parent_keys_consistency` — `verify_gin.c:388-656` — entry-tree
    walker; the `IndexDoCheckCallback`.
  - `gin_check_posting_tree_parent_keys_consistency` — `verify_gin.c:133-381`
    — recurses into each posting tree referenced from a leaf.
  - `check_index_page` — `verify_gin.c:661-709` — per-page header / opaque /
    deleted / max-offset sanity.
  - `gin_refind_parent` — `verify_gin.c:717-756` — concurrent-split recovery:
    re-locate the downlink in the named parent block.
  - `PageGetItemIdCareful` — `verify_gin.c:758-792` — line-pointer bounds and
    flag validation.
  - `ginReadTupleWithoutState` — `verify_gin.c:98-125` — decode posting list
    from an entry tuple. Re-implements `ginPostingListDecode` invocation
    without needing a full GinScan state.

## Key invariants

- **Same height in all branches.** `leafdepth` starts at -1 (`:411`), is
  pinned the first time a leaf is seen, then any later leaf at a different
  depth raises `ERRCODE_INDEX_CORRUPTED` "internal pages traversal
  encountered leaf page unexpectedly" — `:486-494` (entry tree),
  `:193-199` (posting tree).
- **Entry-tree key order.** For each non-rightmost-inner offset, the tuple's
  key must be strictly greater than the previous tuple's key as compared by
  `ginCompareAttEntries` (which handles multi-attribute GIN columns) —
  `verify_gin.c:528-542`.
- **Parent high-key consistency.** Last tuple on a child page must have key
  `<=` the parent's stored downlink key — `:548-596`. On apparent violation,
  call `gin_refind_parent`; if the new parent tuple still violates, raise
  `"has inconsistent records on page %u offset %u"` (`:590-593`).
- **Posting-tree internal page layout.** `pd_lower` must encode exactly
  `maxoff` PostingItems plus one ItemPointerData high key —
  `:268-274`. The comment at `:263-267` notes "we didn't set pd_lower until
  PostgreSQL 9.4, so if this check fails, it could also be because the index
  was binary-upgraded from an earlier version" but the check is still hard
  ERROR.
- **Posting-tree rightmost item key.** The last posting item on the
  rightmost page at any level has key `(0,0)` (infinity sentinel) —
  `:317-332`.
- **Posting-tree internal key ordering.** Successive posting items strictly
  greater than previous — `:333-342`.
- **Leaf posting-list TIDs must have a valid offset number.** Each TID in a
  leaf entry's posting list must satisfy `OffsetNumberIsValid(offnum)` —
  `:629-636`.
- **Posting-tree leaf vs. parent.** Leaf's last TID must be `<=` parent's
  stored bound — `:225-231`.
- **Page must not be all-zero (PageIsNew)** — `:672-678`. Suggests
  `REINDEX`.
- **Special-area sizeof check.** `PageGetSpecialSize == MAXALIGN(sizeof(GinPageOpaqueData))`
  — `:683-689`. Reject any page where the GIN opaque footer is the wrong size.
- **Deleted internal page is corruption.** `GinPageIsDeleted && !GinPageIsLeaf`
  → ERROR — `:691-697`. Deleted leaf with tuples → ERROR — `:698-702`.
- **`maxoff > MaxIndexTuplesPerPage` → ERROR** — `:704-708`. Bounds the rest
  of the walker against any wild offset.
- **Tuple-size cross-check.** `MAXALIGN(ItemIdGetLength) ==
  MAXALIGN(IndexTupleSize)` — `:511-515`. Mirrors the nbtree
  `verify_nbtree.c:1318-1327` check.
- **Compressed vs uncompressed posting-list count match.** When the entry
  tuple's posting list is compressed, decoded TID count must equal
  `GinGetNPosting(itup)` — `verify_gin.c:111-113` (`elog(ERROR, ...)`, NOT
  `ereport` — diagnostic-style internal-only message).

## Notable internals

- **Locking model.** Per-page `LockBuffer(buffer, GIN_SHARE)` (`:435`,
  `:176`), released with `UnlockReleaseBuffer` at end of each iteration
  (`:371`, `:644`). Never holds more than one buffer lock at a time except
  during `gin_refind_parent` (which loads a different page after releasing
  the original) — concurrent inserters can still run.
- **Concurrent split recovery.** Two distinct recovery points: (1) at
  start-of-page, if `stack->parenttup` exists and the *last* key on the
  current page is less than the parent's stored bound and rightlink is
  valid, that's a split-since-we-recorded-parent → push rightlink as a new
  scan item (`verify_gin.c:451-483`). (2) Inside the per-tuple parent-consistency
  check, call `gin_refind_parent` (`:568-570`); if not found, log NOTICE and
  continue (`:573-575`).
- **Memory discipline.** Top-level: per-walk `AllocSetContext` named
  `"amcheck consistency check context"` at `:401`. Posting-tree walks each
  create their own `"posting tree check context"` at `:143`. Both are
  deleted at end (`:380, :655`). Stack items are individually
  `palloc`/`pfree`'d while walking; `parenttup` is `CopyIndexTuple`'d so
  the original page can be released.
- **Read strategy.** `GetAccessStrategy(BAS_BULKREAD)` (`:394`, `:136`) so
  the walk doesn't pollute shared_buffers.
- **CHECK_FOR_INTERRUPTS** in both main loop (`:431`) and posting tree
  loop (`:172`).
- **Error-reporting style.** Almost every check is `ereport(ERROR,
  ERRCODE_INDEX_CORRUPTED, ...)` → fail on first corruption. The only
  NOTICE / DEBUG paths are the concurrent-split case (`:574`,
  `:473-475`) and various `elog(DEBUG3, ...)` traces.
- **No `heapallindexed`-equivalent for GIN.** Unlike nbtree, there's no
  bloom-filter cross-check between heap and GIN, and the `heaprel` argument
  to the callback is unused (`:391, callback_state` is also unused). The
  heap relation is locked only because `amcheck_lock_relation_and_check`
  always locks both.
- **No `parentcheck`-equivalent.** Only one entry function; always
  `AccessShareLock`. The GIN walker is structurally a "parent-check" already
  in that it cross-checks parent ↔ child keys, but without the `ShareLock`
  promise it has to tolerate concurrent splits.

## Trust boundary / Phase D surface

- **Snapshot model.** No snapshot is taken or used; verification is purely
  physical-layout. Visible vs. invisible heap state is not considered.
  A GIN entry pointing at a since-deleted heap TID is not corruption.
- **No tuple-content leakage.** Error `errmsg` strings include block numbers,
  offsets, tid (block,offset) pairs of *index* posting items, and
  ItemPointer key tuples (`:217-218`, `:251-252`, `:293-299`,
  `:327-331`). They do NOT include key datum contents (which would require
  printing user data). That's a real defense-in-depth choice: the GIN walker
  refuses to render key datums.
  [ISSUE-defense-in-depth: GIN error messages omit key contents on purpose;
  contrast with verify_nbtree where heap TIDs and page LSNs are printed
  (nit)] — `verify_gin.c:228-231` vs `verify_nbtree.c:1397-1399`.
- **Concurrent-insert tolerance is incomplete.** The two recovery paths
  catch the common case of "page split between parent-load and child-load",
  but a *deletion* concurrent with the walk (GIN page deletion exists since
  PG 8.4 for posting-tree pages, see `access/gin/ginvacuum.c`) is not
  modeled. If we read a posting-tree leaf that VACUUM concurrently deletes
  and recycles, we may see all-zero or differently-typed page contents and
  raise a spurious "unexpected zero page" or "corrupted page" ERROR.
  [ISSUE-concurrency: GIN check under AccessShareLock doesn't account for
  concurrent posting-tree page recycling (maybe)] — `verify_gin.c:670-678`
  treats `PageIsNew` as definite corruption.
- **`GinPageIsData` Assert at `:179`** is a developer assertion, not a
  corruption check. If a `gin_check_posting_tree_parent_keys_consistency`
  is called against a non-data page (e.g., due to a corrupted entry tuple
  claiming `GinIsPostingTree`), the Assert fires in debug builds but in
  release builds the walker proceeds into undefined territory.
  [ISSUE-defense-in-depth: posting-tree-root pointer should be re-validated
  before recursing; only `Assert(GinPageIsData(page))` (likely)] —
  `verify_gin.c:179`. A malicious page that flips this bit upstream would
  bypass the check.
- **Buffer-pinning discipline.** One pin at a time except during
  `gin_refind_parent` (two simultaneously, briefly). Walker can hold a pin
  for the duration of one page's per-tuple loop, which on a dense entry-tree
  page may include thousands of posting-list decodings. No
  `vacuum_delay_point`-style yield. On very wide tables under
  concurrent autovacuum, this could starve VACUUM.
  [ISSUE-defense-in-depth: no vacuum_delay_point / cost-based yield in long
  GIN walks (nit)] — `verify_gin.c:431` is the only interrupt poll.
- **`palloc(0)` at `:116`** is legal but ugly — when an empty
  uncompressed-zero-items branch is hit, allocates a zero-byte object so the
  caller can pfree it uniformly. Not an issue per se; flagging because
  upstream has been removing `palloc(0)`s.
- **`elog(ERROR, ...)` at `:112`** (instead of `ereport`) — leaks the raw
  decoded-vs-encoded count to the client. Internal-only style — fine for
  superuser callers, but if the function is GRANTed to a non-superuser, the
  error includes diagnostic GIN internals.
  [ISSUE-error-handling: bare elog(ERROR,...) in user-callable code path
  leaks GIN internal counters in errmsg (nit)] — `verify_gin.c:112-113`.
- **No `RecoveryInProgress` special-case.** verify_common.c handles
  unlogged-on-standby; a permanent GIN index on a hot standby is walked
  fine.

## Cross-references

- Backend: `access/gin/ginbtree.c` (GIN tree primitives that this mirrors),
  `access/gin/ginpostinglist.c` (`ginPostingListDecode`),
  `access/gin/gindatapage.c` (the posting-tree page format),
  `access/gin/ginvacuum.c` (page recycling — see concurrency note),
  `access/gin/ginutil.c` (`initGinState`).
- amcheck siblings: `verify_common.c:62-150` (the locking gate),
  `verify_nbtree.c` (the heavier nbtree variant; contrast snapshot use and
  `heapallindexed`).
- Prior sweeps: A6 documented `pg_amcheck` (CLI wrapper) — gin support
  added via the 1.5 SQL upgrade script.

<!-- issues:auto:begin -->
- [Issue register — `amcheck`](../../../issues/amcheck.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-concurrency: GIN walker under AccessShareLock can race
  `access/gin/ginvacuum.c` page recycling and raise spurious "unexpected
  zero page" / "corrupted page" (maybe)] — `verify_gin.c:670-708`.
- [ISSUE-defense-in-depth: posting-tree root recursion guarded only by
  `Assert(GinPageIsData)` — debug-only; release builds proceed into a
  potentially mis-typed page (likely)] — `verify_gin.c:179`.
- [ISSUE-defense-in-depth: no `vacuum_delay_point` / cost yield; long GIN
  walks hold buffer pins continuously (nit)] — `verify_gin.c:431,172`.
- [ISSUE-error-handling: `elog(ERROR, ...)` at `:112-113` instead of
  `ereport` — leaks internal counter values to invoker; if GRANT extended,
  reveals GIN posting-list layout (nit)] — `verify_gin.c:112-113`.
- [ISSUE-defense-in-depth: GIN walker is `AccessShareLock`-only, no
  optional `ShareLock` mode like nbtree's `bt_index_parent_check` (likely)] —
  `verify_gin.c:83-87` + install script. There is no
  `gin_index_parent_check`, so heavyweight-locked cross-checks aren't
  available.
- [ISSUE-documentation: comment at `:263-267` notes pd_lower may legitimately
  be wrong for pre-9.4 binary upgrades but the code still raises hard ERROR
  (nit)] — `verify_gin.c:268-274`.
- [ISSUE-correctness: `ginReadTupleWithoutState` `palloc(0)` for
  uncompressed-with-nipd=0 — legal but inconsistent with caller's pfree
  pattern (nit)] — `verify_gin.c:115-117`.
