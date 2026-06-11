# `src/backend/storage/large_object/inv_api.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~911
- **Source:** `source/src/backend/storage/large_object/inv_api.c`

Server-side implementation of the legacy "inversion filesystem"
large-object API — `lo_create`, `lo_open`, `lo_read`, `lo_write`,
`lo_seek`, `lo_tell`, `lo_truncate`, `lo_unlink`. The on-disk
representation is `pg_largeobject` rows keyed by `(loid, pageno)` where
each row's `data` bytea holds up to `LOBLKSIZE` (= 2048) bytes. Holes
are allowed: missing `pageno` rows read back as zeroes. The file's
chunked-IO logic is essentially a TOAST-like split done at the SQL
level instead of inside the toast pointer machinery. [verified-by-code]

## API / entry points

### Lifecycle
- `inv_create(lobjId)` — `LargeObjectCreate` (catalog/pg_largeobject)
  + `recordDependencyOnOwner` + `InvokeObjectPostCreateHook` +
  `CommandCounterIncrement`. Returns the assigned OID. Note comment at
  lines 184-189: dependencies record `classId =
  LargeObjectRelationId`, *not* `LargeObjectMetadataRelationId`, for
  pg_dump backwards compatibility (lines 172-202). [verified-by-code]
- `inv_open(lobjId, flags, mcxt)` — open an LO for read/write. Maps
  `INV_READ` / `INV_WRITE` to internal `IFS_RDLOCK` / `IFS_WRLOCK`
  flags; comment at 221-225 says `INV_WRITE` *also* grants read
  ("Historically, no difference is made between (INV_WRITE) and
  (INV_WRITE | INV_READ)"). For read mode uses `GetActiveSnapshot`;
  for write mode uses NULL snapshot ("instantaneous"). ACL checked via
  `pg_largeobject_aclcheck_snapshot` unless `lo_compat_privileges`
  GUC is set (lines 214-292). [verified-by-code]
- `inv_close(obj_desc)` — pfree the descriptor (line 298-303).
- `inv_drop(lobjId)` — `performDeletion(DROP_CASCADE)` on the
  `ObjectAddress`. Always returns 1 ("For historical reasons" - line 329).
  [verified-by-code]
- `close_lo_relation(isCommit)` — end-of-xact cleanup; only closes
  cached `lo_heap_r` and `lo_index_r` on commit (abort path is
  cleaned up by relcache invalidation) (lines 96-122). [verified-by-code]

### IO
- `inv_seek(obj_desc, offset, whence)` — `SEEK_SET` / `SEEK_CUR` /
  `SEEK_END`. SEEK_END calls `inv_getsize` which scans backwards via
  the index. Overflow allowed in the addition because final negative
  results are rejected (comment 399-401). Range check against
  `MAX_LARGE_OBJECT_SIZE` (lines 387-434). [verified-by-code]
- `inv_tell(obj_desc)` — returns `obj_desc->offset`. No permission
  check (lines 436-447). [verified-by-code]
- `inv_read(obj_desc, buf, nbytes)` — index-scan `pg_largeobject` for
  `loid=X AND pageno >= floor(offset/LOBLKSIZE)`, copying page data
  into `buf`. Fills gaps in `pageno` sequence with zeroes (lines
  499-512). Returns bytes actually read. ACL is `IFS_RDLOCK` (line
  465). Re-detoasts each page's `data` column via `getdatafield`
  (lines 489-540). [verified-by-code]
- `inv_write(obj_desc, buf, nbytes)` — index-scan, then for each
  affected `pageno`: load existing row if present, splice in the
  new bytes, `CatalogTupleUpdateWithInfo`; or build a fresh row and
  `CatalogTupleInsertWithInfo`. Holes in the *input* range are filled
  with zeros in the buffer before write. `union workbuf` (lines
  557-563) provides a 2052-byte stack buffer with `alignas(int32) bytea
  hdr` so the bytea header can be written in-place. Returns bytes
  written (lines 542-735). [verified-by-code]
- `inv_truncate(obj_desc, len)` — find the page containing the
  truncation point. If it exists, rewrite it short. If we landed in a
  hole, delete the later page (so the loop won't revisit) and write a
  fresh padded page. Then delete every page after the truncation point.
  Range-checked against `MAX_LARGE_OBJECT_SIZE` (lines 737-911).
  [verified-by-code]
- `inv_getsize(obj_desc)` (static) — `systable_beginscan_ordered` with
  `BackwardScanDirection` to find the last page; returns
  `pageno*LOBLKSIZE + len`. Comment at 359-364: a backwards scan over
  loid-only key visits all pages in reverse pageno because the index
  is on `(loid, pageno)` (lines 340-385). [from-comment]
- `getdatafield(tuple, **pdatafield, *plen, *pfreeit)` (static) —
  extract the `data` bytea from a `pg_largeobject` tuple, detoasting
  if extended. Verifies `0 <= len <= LOBLKSIZE`. Returns
  `pfreeit = true` if detoast palloc'd a new buffer (lines 130-157).
  [verified-by-code]

## Notable invariants / details

- **Single static Relation refs per backend** (lines 64-66): `lo_heap_r`
  and `lo_index_r` are file-static cached opens of `pg_largeobject`
  and its primary index. Ownership is hand-assigned to
  `TopTransactionResourceOwner` on first reference inside a subxact
  (lines 76-91), so a subxact rollback won't close them out from under
  later operations in the same top-level xact. Closed only on commit
  (`close_lo_relation`) or on relcache invalidation. [from-comment]
- The data field is read via the C struct cast (`Form_pg_largeobject ->
  data`) — safe because `data` immediately follows `pageno (int4)`,
  giving 4-byte alignment even with 1-byte varlena headers. The
  detoast-then-bounds-check pattern is `getdatafield`. Header comment
  at lines 7-13 documents this. [from-comment]
- `MAX_LARGE_OBJECT_SIZE` (defined in `large_object.h` as `INT64_MAX -
  LOBLKSIZE`) is enforced in `inv_seek`, `inv_write`, `inv_truncate`.
  Errors use `errmsg_internal` because they include `INT64_FORMAT` and
  translating format strings was deemed not worth it (comments at
  422-425, 768-771). [from-comment]
- "Holes read as zeros" (Unix sparse-file semantics): `inv_read` checks
  `pageoff > obj_desc->offset` after each fetched row and zero-fills
  the gap (lines 499-512). `inv_write` may *create* holes — if the
  caller seeks past EOF and writes, intermediate pages are not
  created. [verified-by-code]
- Snapshot rules: read paths use `GetActiveSnapshot` so they're
  MVCC-consistent. Write paths use NULL snapshot inside
  `LargeObjectExistsWithSnapshot` (instantaneous catalog read) so they
  see the latest committed catalog row at write time
  (lines 237-241). [verified-by-code]
- `inv_write` flow for an existing page (lines 633-685):
  - Load old data into `workb`.
  - If the target offset is past the end of the page's current data,
    zero-fill the gap (lines 648-650).
  - memcpy new bytes; update offset; recompute `len = max(len, off)`.
  - `heap_modify_tuple` + `CatalogTupleUpdateWithInfo` rewrites the row.
- `inv_write` flow for a brand-new page (lines 686-720): zero-fill any
  leading gap, memcpy bytes, `heap_form_tuple` + `CatalogTupleInsertWithInfo`.
  [verified-by-code]
- `inv_write` does a `CommandCounterIncrement` at the end (line 732) so
  subsequent operations in the same xact see the new pages. Likewise
  `inv_create`, `inv_drop`, `inv_truncate`. [verified-by-code]
- `inv_truncate` (line 852-863) has a special case: if the first page
  returned by the scan is *after* `pageno`, we landed in a hole. The
  hole-fill page is the truncation marker; the later (out-of-range)
  page must be deleted explicitly because the main loop only deletes
  pages it visits *after* setup. [verified-by-code]
- Workbuf alignment trick (lines 557-562, 746-751):
  `union { alignas(int32) bytea hdr; char data[LOBLKSIZE + VARHDRSZ]; }`
  guarantees the union starts aligned for the bytea header while
  giving room for `LOBLKSIZE` bytes + 4-byte header. Used both in
  `inv_write` and `inv_truncate`. [verified-by-code]
- `lo_compat_privileges` GUC (line 56) bypasses ACL on read/write —
  the legacy "anyone can read any LO" semantic from pre-9.0.
  [from-comment]
- Permission scheme: `inv_seek`/`inv_tell` deliberately *don't* re-check
  permissions ("We allow seek/tell if you have either read or write
  permission"; lines 394-396, 441-443) — the ACL gate is at `inv_open`.
  [from-comment]
- "Paranoia" null checks (`HeapTupleHasNulls`) fire on every fetched
  pg_largeobject row (lines 373, 495, 621, 805) — `loid` and `pageno`
  are NOT NULL but `data` isn't marked NOT NULL by initdb (per header
  comment lines 11-13), so the check protects against
  corrupted-by-other-means cases. [from-comment]
- Detoast safety: `VARATT_IS_EXTENDED` in `getdatafield` (line 142)
  covers both compressed and externalised varlenas. The `pfree(datafield)`
  on `pfreeit = true` releases the palloc'd detoasted copy. [verified-by-code]

## Potential issues

- Line 64-66. The `lo_heap_r` / `lo_index_r` file-static caches mean
  there can only be one in-flight `inv_*` call per backend at a time
  (or rather, all of them share the same Relation refs). Reentrancy
  via, say, a user-defined function that calls into another LO API
  during a hook would work because the cache is xact-scoped, but
  parallel workers don't share these and would need their own opens.
  [ISSUE-undocumented-invariant: file-static Relation caches mean LO
  API is not reentrant across processes (nit)]
- Line 226-241. Comment "Historically, no difference is made between
  (INV_WRITE) and (INV_WRITE | INV_READ)". This bakes a 30-year-old
  client-API behaviour into the server; an LO opened `INV_WRITE` can
  be read without `pg_largeobject_aclcheck_snapshot(ACL_SELECT)` —
  the only ACL check is `ACL_UPDATE`. So a user with UPDATE-but-not-SELECT
  on an LO can read it via `lo_open(..., INV_WRITE) + loread`.
  [ISSUE-security: lo_open(INV_WRITE) allows reads with only ACL_UPDATE
  check, bypassing the ACL_SELECT gate (maybe)]
- Line 239. Write paths use `snapshot = NULL` ("instantaneous").
  Comment at 237 says "If write is requested, use an instantaneous
  snapshot." This is documented but worth noting: writes never see a
  consistent point-in-time view of the LO's pages across the write
  operation — concurrent commits land immediately. Probably fine
  because the user holds a row-level lock implicitly via
  `CatalogTupleUpdate`, but worth a doc cross-ref. [verified-by-code]
- Line 329. `inv_drop` always returns 1. The comment "For historical
  reasons" papers over an API quirk; this is fine but the caller-side
  (`lo_unlink`) ignores the return value, making the historical
  contract effectively unused. [from-comment]
- Lines 416-420 and 769-776. `errmsg_internal` for the seek/truncate
  overflow errors means non-English users see the raw English. Comment
  acknowledges this is "not worth the trouble" — a deliberate trade-off
  but worth a `[from-comment]` tag. [from-comment]
- Lines 489-535. `inv_read` loops without a sanity bound on
  `nbytes - nread > 0`; if `pageoff > obj_desc->offset` consumes all
  remaining `nbytes - nread`, the inner `if (nread < nbytes)` block
  skips and the loop continues to the next tuple. Correct, but
  intricate enough to be worth a code-comment cross-ref. [verified-by-code]
- Line 802-808. `olddata = (Form_pg_largeobject) GETSTRUCT(oldtuple);`
  in `inv_truncate` then dereferences `olddata->pageno`. If the heap
  tuple were somehow shorter than `Natts_pg_largeobject`, this would
  be a buffer over-read. The `HeapTupleHasNulls` check at 805 catches
  null fields but not short tuples. Practically impossible because
  `pg_largeobject` has fixed natts and TOAST handles `data`. [verified-by-code]
- Line 583-584. The `nbytes + obj_desc->offset` overflow comment "can't
  overflow because nbytes is only int32" — true on the int level, but
  `obj_desc->offset` is int64. The promotion `(int64) + (int32)` gives
  int64 arithmetic; no overflow within int64 because both summands are
  bounded by `MAX_LARGE_OBJECT_SIZE < INT64_MAX`. The comment elides
  the type-promotion step. Cosmetic. [verified-by-code]
- Line 56. `bool lo_compat_privileges` is GUC-driven. When true, *all*
  ACL checks are bypassed for read and write — this is the
  pre-9.0 "anyone can do anything with any LO" semantic. Off by
  default but worth noting as the only path that completely disarms LO
  ACL. [from-comment]
- `inv_seek` with `SEEK_END` triggers a *backward* index scan of
  `pg_largeobject` for the LO — for a sparse LO with a single high
  page, this is one index lookup, but the scan happens unconditionally
  even when the caller just wants the current size with no intent to
  seek. Cheap, but synchronous. [verified-by-code]
