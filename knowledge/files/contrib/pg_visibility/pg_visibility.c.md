# `pg_visibility/pg_visibility.c` — visibility-map and page-level visibility introspection

**Verified against source pin `4b0bf0788b0`** (path: `source/contrib/pg_visibility/pg_visibility.c`)

## Role

Exposes the per-relation visibility map (VM) bits (`all_visible`,
`all_frozen`) and the page-level `PD_ALL_VISIBLE` flag to SQL, plus a
corruption-checker that walks heap pages looking for tuples that disagree
with the VM. Also ships a destructive `pg_truncate_visibility_map()`
function that WAL-logs and truncates the `_vm` fork — a recovery aid for
corrupted VMs. Reads bypass MVCC and tuple-level grants.

## Public API

SQL function entry points (see `pg_visibility--1.1.sql`):

- `pg_visibility_map(regclass, bigint) -> (all_visible, all_frozen)` — `source/contrib/pg_visibility/pg_visibility.c:84`
- `pg_visibility(regclass, bigint) -> (all_visible, all_frozen, pd_all_visible)` — `source/contrib/pg_visibility/pg_visibility.c:123`
- `pg_visibility_map_rel(regclass) -> SETOF (blkno, all_visible, all_frozen)` — `source/contrib/pg_visibility/pg_visibility.c:180`
- `pg_visibility_rel(regclass) -> SETOF (blkno, all_visible, all_frozen, pd_all_visible)` — `source/contrib/pg_visibility/pg_visibility.c:224`
- `pg_visibility_map_summary(regclass) -> (all_visible bigint, all_frozen bigint)` — `source/contrib/pg_visibility/pg_visibility.c:269`
- `pg_check_frozen(regclass) -> SETOF tid` — non-frozen TIDs in all-frozen pages — `source/contrib/pg_visibility/pg_visibility.c:303`
- `pg_check_visible(regclass) -> SETOF tid` — non-visible TIDs in all-visible pages — `source/contrib/pg_visibility/pg_visibility.c:335`
- `pg_truncate_visibility_map(regclass) -> void` — drops VM fork — `source/contrib/pg_visibility/pg_visibility.c:370`

All functions are `REVOKE ALL FROM PUBLIC` in the install script
(`pg_visibility--1.1.sql:68-75`) [verified-by-code]; there is NO C-side
permission check, so the SQL `EXECUTE` grant is the sole gate.

## Invariants

- `check_relation_relkind` rejects non-table-AM relations [verified-by-code]
  (`source/contrib/pg_visibility/pg_visibility.c:925-933`).
- `blkno` range checked against `[0, MaxBlockNumber]`; VM reads past EOF
  silently return zeroes by design [from-comment]
  (`source/contrib/pg_visibility/pg_visibility.c:79-82`).
- Page-level visibility checks take `BUFFER_LOCK_SHARE` on each block
  before reading [verified-by-code]
  (`source/contrib/pg_visibility/pg_visibility.c:158,550,757`).
- `pg_truncate_visibility_map` takes `AccessExclusiveLock`, sets both
  `DELAY_CHKPT_START` and `DELAY_CHKPT_COMPLETE`, runs inside
  `START_CRIT_SECTION`, WAL-logs an `xl_smgr_truncate`, then calls
  `smgrtruncate` [verified-by-code]
  (`source/contrib/pg_visibility/pg_visibility.c:378-419`). Modeled on
  `RelationTruncate` per comment at line 367.
- Lock is released early (not at commit time) because the smgr
  invalidation is non-transactional and posted to shared memory
  immediately [from-comment]
  (`source/contrib/pg_visibility/pg_visibility.c:422-441`).
- `GetStrictOldestNonRemovableTransactionId` deliberately uses a stricter
  horizon than `GetOldestNonRemovableTransactionId` (ignores process
  xmins, KnownAssignedXids, walsender xmin) to avoid false positives in
  corruption checks [from-comment]
  (`source/contrib/pg_visibility/pg_visibility.c:574-606`).
- `CHECK_FOR_INTERRUPTS()` is called per block inside scans
  [verified-by-code] (`source/contrib/pg_visibility/pg_visibility.c:530,668,755`).

## Notable internals

- `collect_visibility_data` uses a `BAS_BULKREAD` access strategy to
  prevent cache trashing when scanning whole relations
  (`source/contrib/pg_visibility/pg_visibility.c:491`).
- `collect_corrupt_items` retakes the (expensive) procarray horizon if
  the first horizon turns out to be too old to confirm non-visibility,
  to avoid false positives [from-comment]
  (`source/contrib/pg_visibility/pg_visibility.c:822-838`).
- The read-stream callback `collect_corrupt_items_read_stream_next_block`
  re-reads VM bits to skip pages with no relevant flag set
  (`source/contrib/pg_visibility/pg_visibility.c:655-681`); it also runs
  CHECK_FOR_INTERRUPTS inside a tight loop.
- Custom WAL handling in `pg_truncate_visibility_map` is a "cut-down
  version of `RelationTruncate`" [from-comment line 367] — duplicating
  this xlog protocol in contrib is unusual.

## Trust-boundary / Phase D surface

The module's defense relies entirely on the install-script `REVOKE ALL
FROM PUBLIC` because the C code does not call `superuser()`,
`object_ownercheck`, or `has_privs_of_role` on any of its entrypoints
[verified-by-code]. The owner of a DB can therefore `GRANT EXECUTE …
TO foo` and hand `foo` the ability to:

1. Bypass MVCC: `pg_check_visible` / `pg_check_frozen` walk every heap
   page with only `AccessShareLock` and report TIDs of tuples that are
   "dead but not yet vacuumed", which an attacker can then probe via
   `ctid`-based system queries. [ISSUE-audit-gap: no C-side check for
   any privilege; install-script REVOKE-from-PUBLIC is the only gate —
   if a DB owner re-grants, callers get unrestricted heap-page
   introspection bypassing RLS/column privs (likely)]
   (`source/contrib/pg_visibility/pg_visibility.c:58-66`).
2. Trigger `pg_truncate_visibility_map` on any relation they can reach
   via OID — including system catalogs (the only check is
   `RELKIND_HAS_TABLE_AM`, not ownership). [ISSUE-correctness: no
   ownership/superuser check before destructive VM truncation; an
   inadvertent GRANT lets non-owners blow away VM forks of arbitrary
   tables including catalogs (confirmed)]
   (`source/contrib/pg_visibility/pg_visibility.c:370-446`).
3. `pg_truncate_visibility_map` modifies catalog-fork state and is
   marked `PARALLEL UNSAFE` with the comment "let's not make this any
   more dangerous"; the function does not refuse to run on system
   catalogs or shared catalogs [verified-by-code]
   (`source/contrib/pg_visibility/pg_visibility.c:925-933`).
   [ISSUE-defense-in-depth: pg_truncate_visibility_map can be called on
   pg_class/pg_attribute if granted — recovery path exists (VACUUM
   rebuilds VM) but a denial-of-service / replication corruption window
   is plausible (maybe)]
4. The strict-horizon function `GetStrictOldestNonRemovableTransactionId`
   takes ProcArrayLock+XidGenLock and releases them via the unusual
   pattern of `LWLockRelease(ProcArrayLock); LWLockRelease(XidGenLock);`
   *after* `GetRunningTransactionData` (which already releases
   ProcArrayLock internally on some paths). [ISSUE-concurrency: the
   lock-release pair at lines 625-626 / 636-637 looks correct given
   GetRunningTransactionData's contract but is fragile; future
   refactoring of GetRunningTransactionData could double-release
   (nit)] (`source/contrib/pg_visibility/pg_visibility.c:622-638`).
5. Memory: `collect_visibility_data` calls
   `palloc0(offsetof(vbits, bits) + nblocks)` where `nblocks` is up to
   `MaxBlockNumber` worth of bytes (8 bits per block). For a relation
   at `MaxBlockNumber` that's ~512 MB just for the bit buffer; no MCXT
   huge-allocation flag. [ISSUE-resource: no MaxAllocSize guard on
   nblocks; very large relations (theoretical 4G blocks)
   could palloc-fail or OOM the backend (maybe)]
   (`source/contrib/pg_visibility/pg_visibility.c:500-501`).

## Cross-refs

- `knowledge/files/contrib/pageinspect/` — same "page-bypass-MVCC" pattern (A12)
- `knowledge/files/contrib/amcheck/` — A12 found amcheck has zero C-side privilege checks; same gap here
- `knowledge/files/contrib/pgstattuple/` — also reads heap pages bypassing MVCC
- `knowledge/subsystems/storage-buffer.md` — buffer-pin/share-lock discipline
- `knowledge/subsystems/access-heap.md` — `HeapTupleSatisfiesVacuum` semantics

## Issues

1. [ISSUE-audit-gap: no C-side privilege checks on any of the 8 entrypoints; install-script REVOKE-from-PUBLIC is the only gate (likely)] — `source/contrib/pg_visibility/pg_visibility.c:58-66`
2. [ISSUE-correctness: pg_truncate_visibility_map does not check ownership or superuser; OK as long as REVOKE persists, but defense-in-depth absent (confirmed)] — `source/contrib/pg_visibility/pg_visibility.c:370-446`
3. [ISSUE-defense-in-depth: pg_truncate_visibility_map accepts system-catalog OIDs (only relkind filter applied) (maybe)] — `source/contrib/pg_visibility/pg_visibility.c:925-933`
4. [ISSUE-concurrency: manual LWLockRelease(ProcArrayLock) + LWLockRelease(XidGenLock) after GetRunningTransactionData is fragile but currently correct (nit)] — `source/contrib/pg_visibility/pg_visibility.c:622-638`
5. [ISSUE-resource: collect_visibility_data palloc0s up to ~MaxBlockNumber bytes without huge-alloc flag (maybe)] — `source/contrib/pg_visibility/pg_visibility.c:500-501`
