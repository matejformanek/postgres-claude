# Issues — `src/include/access`

Per-subsystem issue register for **the access-method API + heap/toast/WAL/multixact/visibility/sequence header layer**. 32 headers / ~70 entries surfaced 2026-06-09 by A17 (slices A17-1 + A17-2).

**Parent docs:** `knowledge/files/src/include/access/*` (now full coverage for the 32 A17 headers; previous A1+A2+A8 covered the index-AM-specific headers).

**Sibling registers:** `knowledge/subsystems/access-heap.md`, `access-nbtree.md`, `access-transam.md` (synthesized subsystem docs); `knowledge/issues/storage-aio.md` (storage-aio).

## Headlines

1. **🚨 `amapi.h` + `tableam.h` extension-surface contract: required callbacks are Assert-only** in `GetIndexAmRoutine` / `GetTableAmRoutine`. In a cassert-disabled production build, a malformed handler reaches the call site as a NULL function pointer. Load-bearing for Phase D's "load arbitrary AM" thread (parallel to A8 output_plugin).
2. **`heaptoast.h` `heap_fetch_toast_slice(valueid, ...)` trusts caller-supplied `valueid` against `toastrel`** — the API surface for A12's `tuple_data_split(do_detoast=true)` cross-table read primitive. No cross-check that `valueid` belongs to `toastrel` at this header layer.
3. **No version/magic field on `IndexAmRoutine` or `TableAmRoutine`** — only `NodeTag` discriminates struct kind. PG_MODULE_MAGIC catches catastrophic .so-version mismatches, but field-by-field struct drift between PG releases is silent garbage.
4. **`itup.h` t_info bit-packing**: 13 bits size (cap 8191), 1 bit hasNulls, 1 bit hasVarwidths, 1 bit AM-reserved. The hasNulls+corrupt-bitmap path is a real OOB-read disk-trust surface that amcheck defends.
5. **`rmgrlist.h` is the SECOND canonical X-macro site in the corpus** (alongside `lwlocklist.h` from A15) — three coordinated edits required (header + desc table + redo code) + `XLOG_PAGE_MAGIC` bump invariant.
6. **`syncscan.h` is a NEW Phase-D echo** — shared start-block hash leaks another session's seq-scan position at 128-block granularity, observable cross-database. Fresh "monitoring-as-extraction" surface (A11/A12/A14 family).
7. **`rewriteheap.h` `pg_logical/mappings/<filename>` leaks dboid + xid + LSN in filenames + DoS via stalled logical slot** — A8 echo at API layer.
8. **`multixact_internal.h` is pg_upgrade's silent contract** — group layout is hardcoded; any change must coordinate with `multixact_read_v18.c` shim or silent corruption.
9. **`visibilitymapdefs.h`** is the A14 `pg_truncate_visibility_map` header anchor (trust model lives only in `pg_visibility.c`).
10. **`sequence.h` cross-tenant `nextval()` side-channel** — monotonic + observable + shared = write-traffic inference vector (A11 echo).
11. **`tsmapi.h` trust gap** — no API-level requirement that `NextSampleBlock`/`NextSampleTuple` stay within bounds; bug in TSM extension drives `heap_fetch` past relation.
12. **`cmptype.h` `CompareType` framework explicitly work-in-progress** — downstream switch-with-default-error code will break as new cases land.

## Entries — A17-1 (access AM API + heap/toast/tuple, 16 headers)

### amapi.h, amvalidate.h
- [ISSUE-defense-in-depth: GetIndexAmRoutine validates required callbacks only via Assert, not ereport (likely)] — `amapi.h:233`
- [ISSUE-api-shape: no version/magic field on IndexAmRoutine struct (nit)] — `amapi.h:233`
- [ISSUE-audit-gap: no amselfcheck hook on IndexAmRoutine for runtime contract verification (nit)] — `amapi.h:295`
- [ISSUE-correctness: handler must return server-lifetime pointer; not enforced (nit)] — `amapi.h:230`
- [ISSUE-defense-in-depth: 64-bit operatorset/functionset bitmask in OpFamilyOpFuncGroup silently truncates (nit)] — `amvalidate.h:24`
- [ISSUE-audit-gap: amvalidate is structural-only; cannot detect operator-semantics mismatches (nit, A13/A14 echo)] — `amvalidate.h:30`

### tableam.h, table.h, genam.h, relscan.h
- [ISSUE-defense-in-depth: TableAmRoutine required callbacks Assert-only (likely)] — `tableam.h:312`
- [ISSUE-api-shape: no version/magic on TableAmRoutine (nit)] — `tableam.h:321`
- [ISSUE-security: index_fetch_tuple has no cross-AM/cross-relation enforcement (nit)] — `tableam.h:472`
- [ISSUE-error-handling: elog (no errcode) on CheckXidAlive trip in scan-begin guards (nit)] — `tableam.h:930,1354`
- [ISSUE-defense-in-depth: SO_HINT_REL_READ_ONLY is advisory, not contractual (nit)] — `tableam.h:70`
- [ISSUE-audit-gap: table_open does no permission check; caller-responsibility (nit, A6/A12)] — `table.h:21`
- [ISSUE-audit-gap: BuildIndexValueDescription column-redaction is inside-C-only, not at header contract (nit, A14 amcheck echo)] — `genam.h:217`
- [ISSUE-correctness: systable_inplace_update_* bypasses MVCC by design (nit)] — `genam.h:243`
- [ISSUE-api-shape: IndexBulkDeleteResult is "first field" of extensible struct; sizeof undefined for AMs (nit)] — `genam.h:71`
- [ISSUE-api-shape: IndexScanDescData.opaque is void* with no type tag (nit)] — `relscan.h:165`
- [ISSUE-concurrency: phs_mutex spinlock-protects parallel-scan startblock (nit)] — `relscan.h:102`
- [ISSUE-memory: ParallelIndexScanDescData uses FLEXIBLE_ARRAY_MEMBER for snapshot data (nit)] — `relscan.h:213`

### heaptoast.h, toast_helper.h, toast_internals.h
- [ISSUE-security: heap_fetch_toast_slice trusts caller-supplied valueid against toastrel (likely, A12 anchor)] — `heaptoast.h:145`
- [ISSUE-resource: no input-size cap at heaptoast API surface for decompression (likely, A11/A5 echo)] — `heaptoast.h:145`
- [ISSUE-correctness: TOAST_MAX_CHUNK_SIZE change requires initdb but not catalog-enforced (nit)] — `heaptoast.h:78`
- [ISSUE-correctness: ToastTupleContext.ttc_attr sizing contract is comment-only, no Assert (nit)] — `toast_helper.h:55`
- [ISSUE-memory: TOAST_NEEDS_FREE / TOASTCOL_NEEDS_FREE requires manual toast_tuple_cleanup (nit)] — `toast_helper.h:71`
- [ISSUE-security: compress-header method field 2-bit; reader must defend unused codes 2/3 (nit)] — `toast_internals.h:34`

### tupconvert.h, itup.h, tupmacs.h, attnum.h, printsimple.h, stratnum.h, sdir.h
- [ISSUE-correctness: tupconvert attrMap > indesc->natts is silent OOB read (nit)] — `tupconvert.h:42`
- [ISSUE-correctness: t_info size=0 in corrupted IndexTuple loops scans (nit)] — `itup.h:65`
- [ISSUE-correctness: hasNulls bit set but no/garbage bitmap → OOB read in att_isnull (nit)] — `itup.h:154`
- [ISSUE-correctness: fetch_att_noerr length-validation contract is comment-only (nit)] — `tupmacs.h:131`
- [ISSUE-correctness: first_null_attr walks past bitmap unless caller guarantees a 0 bit (nit)] — `tupmacs.h:235`
- [ISSUE-correctness: AttrNumberGetAttrOffset on negative (system) attnum is Assert-only (nit)] — `attnum.h:51`
- [ISSUE-correctness: strategy-number semantics are convention-only (nit, A13/A14 echo)] — `stratnum.h:29`

## Entries — A17-2 (WAL/rmgr/multixact/sequence/visibility, 16 headers)

### rmgrlist.h, rmgrdesc_utils.h, bufmask.h, timeline.h
- [ISSUE-api-shape: rmgrlist.h header doesn't mention RegisterCustomRmgr as the extension hook (nit)] — `rmgrlist.h:18`
- [ISSUE-correctness: rmgrlist.h ID assignment is positional with no compile-time stability check (likely, lwlocklist.h echo)] — `rmgrlist.h:19`
- [ISSUE-documentation: rmgrdesc_utils.h `void *data` parameter undocumented at header level (nit)] — `rmgrdesc_utils.h:15`
- [ISSUE-documentation: bufmask.h doesn't directly name `wal_consistency_checking` (nit)] — `bufmask.h:5`
- [ISSUE-documentation: timeline.h doesn't document the on-disk text format of `.history` files (nit)] — `timeline.h:1`

### tsmapi.h, multixact_internal.h, sequence.h
- [ISSUE-security: tsmapi.h has no API-level documentation that `NextSampleBlock`/`NextSampleTuple` MUST stay within bounds (likely)] — `tsmapi.h:37`
- [ISSUE-documentation: tsmapi.h flags "more function pointers likely added" but no extension-author guidance (nit)] — `tsmapi.h:51`
- [ISSUE-documentation: multixact_internal.h "8 bytes per offset" wording ambiguous (nit)] — `multixact_internal.h:31`
- [ISSUE-security: multixact_internal.h is the silent contract pg_upgrade relies on (likely)] — `multixact_internal.h:6`
- [ISSUE-documentation: sequence.h too thin to convey RELKIND-checking chokepoint role (nit)] — `sequence.h:20`
- [ISSUE-security: sequence.h no comment about cross-tenant nextval() side-channel (Phase D) (likely, A11 echo)] — `sequence.h:20`

### visibilitymapdefs.h, syncscan.h, sysattr.h
- [ISSUE-security: visibilitymapdefs.h is header anchor for A14 pg_truncate_visibility_map no-restriction finding (likely)] — `visibilitymapdefs.h:20`
- [ISSUE-documentation: visibilitymapdefs.h missing "heap blocks per VM page" formula (nit)] — `visibilitymapdefs.h:17`
- [ISSUE-security: syncscan.h shared start-block hash is cross-tenant observation channel — 128-block granularity (likely, NEW monitoring-as-extraction echo)] — `syncscan.h:25`
- [ISSUE-documentation: syncscan.h doesn't document SYNC_SCAN_REPORT_INTERVAL or SYNC_SCAN_NELEM (nit)] — `syncscan.h:25`
- [ISSUE-documentation: sysattr.h slot -7 was ObjectIdAttributeNumber pre-PG12; not noted (nit)] — `sysattr.h:27`
- [ISSUE-security: sysattr.h is named-place for xmin/xmax/cmin/cmax xid-scrape surface (likely)] — `sysattr.h:21`

### cmptype.h, gin_tuple.h, tidstore.h
- [ISSUE-api-shape: cmptype.h CompareType framework flagged "not fully developed" — downstream switch breaks (likely)] — `cmptype.h:27`
- [ISSUE-documentation: cmptype.h doesn't name `amtranslatestrategy` consumer hook (nit)] — `cmptype.h:31`
- [ISSUE-documentation: gin_tuple.h doesn't cross-reference posting-list vs posting-tree pivot (nit)] — `gin_tuple.h:17`
- [ISSUE-documentation: tidstore.h TidStoreIterResult.internal_page opaque but raw pointer; misuse-after-end is UB (nit)] — `tidstore.h:30`
- [ISSUE-api-shape: tidstore.h has no "forget block" or "remove specific TID" API (nit)] — `tidstore.h:41`

### valid.h, skey.h, rewriteheap.h
- [ISSUE-documentation: valid.h misnomer — only holds HeapKeyTest for ScanKey eval (nit)] — `valid.h:4`
- [ISSUE-api-shape: skey.h SK_UNARY flag declared but explicitly "not supported" — dead bit (nit)] — `skey.h:116`
- [ISSUE-api-shape: skey.h carries nine subtly-different semantic modes on one struct (nit)] — `skey.h:115`
- [ISSUE-security: rewriteheap.h `pg_logical/mappings/<filename>` leaks dboid + xid + LSN; DoS via stalled logical slot (likely, A8 echo)] — `rewriteheap.h:43`
- [ISSUE-resource: rewriteheap.h no accounting/limit on mapping-file count (likely)] — `rewriteheap.h:55`

## Cross-sweep references

- **A12 `tuple_data_split` cross-table read primitive** — heaptoast.h API host.
- **A11 pgcrypto pgp-decompression bomb + A5 pg_lzcompress no-cap** — heaptoast.h toast-decompress echo.
- **A14 amcheck zero C-side permission checks** — amapi.h + tableam.h API hosts.
- **A8 output_plugin "load arbitrary code"** — amapi.h is the parallel "load arbitrary index AM" extension surface.
- **A15 lwlocklist.h INCLUDE-trick** — rmgrlist.h is the second canonical site.
- **A14 pg_truncate_visibility_map** — visibilitymapdefs.h header anchor.
- **A11/A12/A14 monitoring-as-extraction** — syncscan.h (NEW echo), sequence.h, sysattr.h header anchors.
- **A14 TSM modules** — tsmapi.h extension surface anchor.
- **A8/A14 SLRU wrap-around** — multixact_internal.h companion.
- **A8 logical replication retention** — rewriteheap.h echo at header layer.
