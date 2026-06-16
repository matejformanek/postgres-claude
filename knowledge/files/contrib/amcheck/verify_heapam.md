# verify_heapam.c

Covers `source/contrib/amcheck/verify_heapam.c` (2180 lines). Source pin:
`4b0bf0788b0`.

## One-line summary

`verify_heapam(relation regclass, on_error_stop, check_toast, skip,
startblock, endblock)` — table-AM verifier that scans `[startblock,
endblock]` of a heap (or sequence) relation under `AccessShareLock`,
validating line-pointer geometry, tuple-header sanity, XID/MXID range vs.
clog horizon, HOT-chain transitions, varlena attribute decoding, and (when
`check_toast=true`) every external TOAST pointer against its toast index;
returns a `SETOF (blkno, offnum, attnum, msg)` tuplestore — does NOT
`ereport(ERROR)` on per-tuple findings.

## Public API / entry points

- `Datum verify_heapam(PG_FUNCTION_ARGS)` — `verify_heapam.c:252-874`. 6
  args, returns SRF. `PG_FUNCTION_INFO_V1` at `:35`. Declared without
  `STRICT` and without `PARALLEL` (see `amcheck--1.2--1.3.sql:18-21`), so
  callers may pass NULLs but each is rejected with
  `ERRCODE_INVALID_PARAMETER_VALUE` early (`:272-294`).
- Helper macros / constants:
  - `HEAPCHECK_RELATION_COLS = 4` — `:38`. Tuplestore column count.
  - `VARLENA_SIZE_LIMIT = 0x3FFFFFFF` — `:41`. Largest valid toast
    `va_rawsize`.
- Static workers (call graph from top down):
  - `heapcheck_read_stream_next_unskippable` — `:882-910` — read-stream
    callback for the `'all-visible'`/`'all-frozen'` skip modes; consults
    the visibility map.
  - `check_tuple` → `check_tuple_header` → `check_tuple_visibility` →
    `check_tuple_attribute` → `check_toasted_attribute` → `check_toast_tuple`
    — `:919-1969` plus `:1556-1910`.
  - `report_corruption_internal` / `report_corruption` /
    `report_toast_corruption` — `:916-975`. Push one row to the
    tuplestore, free msg, set `is_corrupt = true`.
  - `update_cached_xid_range` / `update_cached_mxid_range` — `:2020-2041`.
    `LWLockAcquire(XidGenLock, LW_SHARED)` for `nextXid`/`oldestXid`;
    `ReadMultiXactIdRange` for the mxid pair.
  - `get_xid_status` / `check_mxid_in_range` /
    `check_mxid_valid_in_rel` / `fxid_in_cached_range` /
    `FullTransactionIdFromXidAndCtx` — `:2047-2180`. XID/MXID bounds and
    clog-horizon lookups; takes `XactTruncationLock LW_SHARED` to look up
    `oldestClogXid`.

## Key invariants

### Per-relation prerequisites (raise ERROR, not row)

- Must be heap-AM or RELKIND_SEQUENCE (sequences use heap AM but lie in
  `pg_class.relam`) — `:335-351`.
- Unlogged-during-recovery → silently return NULL — `:358-367`. Same
  semantics as verify_common's index-side skip.
- `startblock` and `endblock`, if given, must each be in `[0, nblocks)` —
  `:382-407`. **Both arguments are bigint** (the SQL signature) but
  validated against `BlockNumber` (uint32). Negative or `>= nblocks` →
  ERROR.
- `skip` text arg must be one of `"all-visible"`, `"all-frozen"`,
  `"none"` — case-insensitive (`pg_strcasecmp`), other values → ERROR.

### Per-line-pointer (per-row findings)

- **Redirected line pointer** must point inside `[FirstOffsetNumber,
  maxoff]` — `:528-543`. Target must be `LP_NORMAL` (not unused, not dead,
  not redirected) — `:551-572`.
- **LP_NORMAL line pointer** must have `lp_off == MAXALIGN(lp_off)`,
  `lp_len >= MAXALIGN(SizeofHeapTupleHeader)`, `lp_off+lp_len <= BLCKSZ`
  — `:588-611`.

### Per-tuple header (`check_tuple_header`, `:1000-1079`)

- `t_hoff <= lp_len` — `:1009-1015`.
- `HEAP_XMAX_COMMITTED && HEAP_XMAX_IS_MULTI` is contradictory → reported
  but does not stop further checks — `:1017-1029`.
- `IsHotUpdated && !TransactionIdIsValid(curr_xmax)` → reported but does
  not stop — `:1031-1042`.
- `HeapTupleHeaderIsHeapOnly && !HEAP_UPDATED` → reported, doesn't stop
  — `:1044-1051`.
- `t_hoff` must equal the computed `expected_hoff` (MAXALIGN(header +
  optional null-bitmap)) — `:1053-1076`.

### Per-tuple visibility (`check_tuple_visibility`, `:1113-1537`)

- xmin in `[oldest_fxid, next_fxid)`; xmax similarly. Three violation
  modes — `XID_IN_FUTURE`, `XID_PRECEDES_CLUSTERMIN`,
  `XID_PRECEDES_RELMIN` — `:1130-1160`, `:1469-1498`. Out-of-range XIDs are
  reported and visibility checking abandoned.
- Pre-9.0 `HEAP_MOVED_OFF` / `HEAP_MOVED_IN` xvac handling — long
  enumeration of legal/illegal combinations — `:1170-1305`.
- If inserting xact never committed, can't trust tupledesc, so don't
  recurse into attributes — `:1306-1318`. Conservative even for
  `XID_IS_CURRENT_XID`.
- For `HEAP_XMAX_IS_MULTI`: multixact bounds-checked before
  `HEAP_XMAX_INVALID`/`HEAP_XMAX_IS_LOCKED_ONLY` decisions — `:1327-1370`,
  with the comment explaining "eventually we're going to have to freeze,
  and that process will ignore hint bits" (`:1334-1336`).
- `ctx->tuple_could_be_pruned` is true iff the tuple's xmax precedes
  `safe_xmin` (a copy of our snapshot's xmin) — `:1452-1454`, `:1522-1524`.
  Used to decide whether to follow TOAST pointers.

### Per-attribute (`check_tuple_attribute`, `:1661-1853`)

- Attribute offsets monotone, bounded by `lp_len` — `:1676-1684`,
  `:1696-1704`, `:1742-1751`.
- For varlena attrs: if `VARATT_IS_EXTERNAL`, `VARTAG_EXTERNAL` MUST be
  `VARTAG_ONDISK` — `:1724-1736`. Any other tag → "toasted attribute has
  unexpected TOAST tag %u" and abort attribute checks for this tuple.
- After safely extracting `toast_pointer` via `VARATT_EXTERNAL_GET_POINTER`
  (`:1775`), check `va_rawsize <= 0x3FFFFFFF` — `:1778-1783`.
- Compressed: `TOAST_COMPRESS_METHOD` must be `TOAST_PGLZ_COMPRESSION_ID`
  or `TOAST_LZ4_COMPRESSION_ID` — `:1785-1810`. `TOAST_INVALID_COMPRESSION_ID`
  reported, anything else is unreachable (no `default` in switch). NB: the
  `case TOAST_INVALID_COMPRESSION_ID: break;` falls through to `if (!valid)`
  which reports — i.e. invalid IDs ARE caught.
- `HEAP_HASEXTERNAL` flag must be set on the tuple header when an
  external varlena is found — `:1813-1819`.
- Relation must have a toast relation when any external varlena is found
  — `:1822-1828`.

### Per-toast-chunk (`check_toast_tuple`, `:1555-1639`)

- `chunk_seq` not null, must equal expected — `:1568-1585`.
- Chunk data not null — `:1588-1597`.
- Chunk varlena header must be `4B-not-extended` or `SHORT`; anything
  else (including external — toast chunks can't reference further toast)
  → report and bail — `:1598-1617`.
- `chunk_seq <= last_chunk_seq` — `:1622-1629`.
- `chunksize == (chunk_seq < last ? TOAST_MAX_CHUNK_SIZE : tail-bytes)`
  — `:1631-1638`.

### HOT-chain validation (the main loop at `verify_heapam.c:482-836`)

- For each (offnum, successor) pair where successor is on the same page
  and lp_valid:
  - **Redirect must point to a heap-only tuple** — `:680-685`.
  - **A given successor offnum is reached at most once** ("HOT chains
    should not intersect") — `:687-694, :720-727`.
  - **xmax(curr) == xmin(next)** is the chain-link condition — `:716-718`.
  - **HOT_UPDATED ↔ heap-only-tuple agreement** — `:744-757`. Both
    directions reported.
  - **In-progress xmin can't be predecessor of committed xmin** —
    `:769-781`. Rechecks `TransactionIdIsInProgress(curr_xmin)` to defend
    against the curr-xmin committing between our earlier check and this
    one.
  - **Aborted xmin can't be predecessor of in-progress / committed xmin**
    — `:787-803`.
- **Chain-root rule.** A tuple that is committed/in-progress and has no
  predecessor must NOT be heap-only — `:813-836`. Catches detached HOT
  fragments.

### Other

- **`HeapTupleHeaderGetNatts(tuphdr) <= RelationGetDescr(rel)->natts`** —
  `:1944-1951`. Tuples with more attributes than the catalog claims are
  reported.

## Notable internals

- **`AccessShareLock` only.** Heap is opened (`:330`) and toast / toast
  index too (`:415-421`) with `AccessShareLock`. Per-buffer lock is
  `BUFFER_LOCK_SHARE` (`:497`), released at `:839` before the toast
  cross-check fans out (`:844-852`) — i.e. toast lookups happen with no
  main-table buffer lock held.
- **Read stream with skip modes.** `SKIP_PAGES_NONE` uses
  `block_range_read_stream_cb` with `READ_STREAM_SEQUENTIAL |
  READ_STREAM_FULL | READ_STREAM_USE_BATCHING` (`:456-460`); skip-flavors
  use a stateful callback consulting the visibility map (`:882-910`) and
  can't batch because the callback takes locks (`:464-468`).
- **Read strategy `BAS_BULKREAD`** — `:377`.
- **Per-page state arrays.** `predecessor[MaxOffsetNumber]`,
  `successor[MaxOffsetNumber]`, `lp_valid[MaxOffsetNumber]`,
  `xmin_commit_status_ok[MaxOffsetNumber]`, `xmin_commit_status[MaxOffsetNumber]`
  — `:485-489`. Stack-allocated per-page; ~2-4 KB total at default page
  size.
- **`safe_xmin` cached at start** from `GetTransactionSnapshot()->xmin`
  (`:315`). Used to know which tuples and their toast can still be
  vacuumed away.
- **Tuple-pruning gating.** `ctx->tuple_could_be_pruned` controls whether
  to push the toast pointer onto `ctx->toasted_attributes` for later
  lookup (`:1839-1850`). Pruning-eligible tuples are NOT cross-checked
  against the toast table — avoids racing VACUUM.
- **Toast lookup uses `get_toast_snapshot()`** (the toast-specific
  snapshot defined in `access/heap/heapam_visibility.c`) and
  `systable_beginscan_ordered` against the valid toast index — `:1879-1899`.
  So the toast lookup uses an effective `SnapshotToast`, not the caller's
  MVCC snapshot. Combined with the `tuple_could_be_pruned` guard, this is
  the discipline that prevents "follow a TOAST pointer whose chunks were
  already vacuumed."
- **`is_corrupt` + `on_error_stop`** — the only "stop" knob. If
  `on_error_stop=true`, the outer loop breaks after any page where any
  row was added to the tuplestore (`:854-855`). Otherwise the whole
  relation is scanned.
- **Memory leak avoidance.** Every `report_corruption*` pfrees the
  passed `msg` immediately (`:931-939`) to avoid >work_mem-sized leaks on
  catastrophically corrupt relations.
- **Caching xid lookups.** `ctx->cached_xid` / `ctx->cached_status` is
  populated by `get_xid_status` at `:2177-2178`; if the same xid is asked
  again before any other xid, the clog lookup is skipped (`:2154-2158`).
  Single-element cache, not LRU.
- **Pre-9.0 xvac branches still present** (`:1170-1305`) — long-dead
  code path for `HEAP_MOVED_OFF` / `HEAP_MOVED_IN`. PG 14 removed the
  ability to *produce* these but reading them is still supported.
- **`FullTransactionIdFromXidAndCtx`** — `:1978-2015` — tolerates
  pre-epoch-0 xids by clamping to `FirstNormalFullTransactionId`. The
  Assert at `:2007` guarantees we only do that when epoch==0.

## Trust boundary / Phase D surface

This is the densest Phase D surface in amcheck. The relation may be
arbitrarily corrupt — every assumption the rest of the heap code makes
must be defended explicitly.

- **TOAST pointer validation.** The two-stage defense
  (`VARATT_IS_EXTERNAL` → check `VARTAG_EXTERNAL == VARTAG_ONDISK` →
  `VARATT_EXTERNAL_GET_POINTER` into a local for alignment → check
  `va_rawsize <= 0x3FFFFFFF` → check compression-method ID → only THEN
  push to toasted_attributes) is the canonical anti-OOB recipe. A fuzzed
  toast pointer pointing at a `va_tag` of e.g. `VARTAG_INDIRECT` is
  caught at `:1728-1735` BEFORE `VARATT_EXTERNAL_GET_POINTER` could read
  past the page.
- **However:** `VARTAG_SIZE` is invoked implicitly by `VARATT_IS_EXTERNAL`
  paths. The comment at `:1721-1723` says "Check that VARTAG_SIZE won't
  hit an Assert on a corrupt va_tag before risking a call into
  att_addlength_pointer." The Assert is only debug-build; in release,
  `VARTAG_SIZE` on an unknown tag returns 0 (per `varatt.h`), which makes
  the subsequent `att_addlength_pointer` advance offset by 0 and then we
  check bounds. So even debug-Assert failure is the only consequence,
  and the explicit `va_tag != VARTAG_ONDISK` short-circuit prevents the
  Assert from firing.
  [ISSUE-defense-in-depth: TOAST-tag defense relies on `VARTAG_SIZE`
  returning 0 for unknown tags — release-build behavior depends on the
  inline expansion (likely)] — `verify_heapam.c:1721-1736`.
- **TOAST chunk read uses real index lookup with toast snapshot.** This
  IS the canonical "regular index lookup to try to fetch TOAST tuples"
  that the function header at `:242-249` warns about: "If check_toast is
  true, we'll use regular index lookups to try to fetch TOAST tuples,
  which can certainly cause crashes if the right kind of corruption
  exists in the toast table or index." The check stops at index-search
  level; if the toast index itself is corrupt enough to crash
  `_bt_search`, the backend dies.
  [ISSUE-correctness: verify_heapam with check_toast=true can crash the
  backend if the toast index is corrupted (likely / confirmed by header
  comment)] — `verify_heapam.c:1887-1899`. Workaround: run
  `bt_index_check` on the toast index first.
- **No protection against malicious heap that lies about its own xids.**
  If an xid in the heap is `oldestClogXid - 1` (`XID_PRECEDES_CLUSTERMIN`),
  the function reports it and returns from `check_tuple_visibility`
  (`:1146-1152`) — does NOT then call `TransactionIdDidCommit` on it.
  But for xids inside the cached range, `TransactionIdDidCommit` IS
  called (`:2171`), and `clog_horizon` is rechecked under
  `XactTruncationLock` at `:2161-2164`. Even so, racing clog truncation
  could in theory deliver garbage results — caller of
  `update_cached_xid_range` doesn't re-take the lock during the lookup.
  [ISSUE-concurrency: clog truncation can advance between
  `XactTruncationLock` release and `TransactionIdDidCommit` call (nit)]
  — `verify_heapam.c:2161-2176`.
- **HOT-chain rules are the canonical reference.** Any tool that
  validates HOT chains externally cross-references this file. The
  predecessor[] / successor[] / xmin-status pattern at `:482-836` is the
  invariant set.
- **`tuple_could_be_pruned` is the toast safety predicate.** A tuple
  whose xmax committed before `safe_xmin` is "pruneable" → toast tuples
  for it could be already vacuumed. The function specifically refuses to
  follow toast pointers from those tuples (`:1839-1850`). This is the
  defense that keeps `verify_heapam` from racing VACUUM on toast tables.
- **Error reporting layer is row-based.** Errors are pushed to a
  tuplestore (`report_corruption_internal`, `:916-943`); the function
  returns SETOF, so the SQL invoker reads off every finding. **Tuple
  contents are NOT included in messages.** Only psprintf'd integers:
  block, offset, lp_off, lp_len, lengths, xids. So even with a
  non-superuser GRANT, the messages don't leak user-row contents — only
  physical layout and XID values. Per-XID disclosure is real, though
  (you learn the inserting xact's ID for any tuple where there's
  corruption in xmin) — that's a side channel of write activity.
  [ISSUE-security: per-finding errmsg contains exact xmin/xmax/xvac
  values; non-superuser invokers learn xact IDs of writers (maybe)] —
  `verify_heapam.c:1141-1158, :1182-1199, :1411-1430`.
- **Buffer-pinning DoS surface.** One buffer pinned at a time on main
  table; one VM buffer pinned for the duration of the scan
  (`vmbuffer` at `:256`, released at `:860-861`). Toast lookup may
  separately pin toast pages. For a 1TB table with `skip='none'`,
  this is a long scan that holds no global resources — but the toast
  systable scan internally takes more pins. Bounded by `BAS_BULKREAD`
  ring usage.
- **`startblock`/`endblock` validation.** `:382-407` rejects negative
  and `>= nblocks`. Both args are `bigint`; cast to `BlockNumber` after
  range check. No off-by-one here: `endblock = nblocks - 1` is allowed,
  inclusive. The read-stream init uses `last_exclusive = last_block +
  1` (`:445`), so it's `[first, last]` inclusive. No unsigned overflow
  because we validate `< nblocks` before casting.
- **`indcheckxmin` not honored on toast index.** Comment at
  `verify_common.c:113-117` waives the usability horizon for the
  index-side caller, but `verify_heapam` re-opens the toast index via
  `toast_open_indexes` (`:417-421`) directly; it could theoretically
  return a partial index that's not yet usable. In practice the toast
  index is built at create-time and never re-built without exclusive
  lock.
- **No `RecoveryInProgress` check beyond unlogged-skip.** A heap check
  during recovery is allowed; xid bounds come from
  `TransamVariables->nextXid` / `oldestXid` (live on standby).
- **Sequence handling.** `RELKIND_SEQUENCE` is explicitly accepted at
  `:336` — useful in PG 17+ where sequences use a 1-tuple heap page.
  Sequence's `relam` is 0, so the second check (`:347-351`) is
  conditionalized to skip sequences.
- **`InitMaterializedSRF`** at `:325` — materializes the whole
  tuplestore in memory (up to `work_mem`). Pathological corruption ⇒
  unbounded findings ⇒ memory pressure capped at work_mem
  (rows-on-disk spillover applies after). Comment at `:931-938`
  acknowledges and mitigates the per-msg leak.

## Cross-references

- Backend: `access/heap/heapam.c`, `access/heap/heapam_visibility.c`
  (`HeapTupleSatisfies*`, `get_toast_snapshot`),
  `access/common/toast_internals.c` (`toast_open_indexes`,
  `TOAST_MAX_CHUNK_SIZE`), `access/heap/heaptoast.c`,
  `access/common/detoast.c` (`detoast_external_attr` — the production
  consumer that this function mirrors and guards),
  `access/transam/transam.c` (`TransactionIdDidCommit`,
  `TransactionIdIsInProgress`),
  `access/transam/multixact.c` (`ReadMultiXactIdRange`),
  `storage/buffer/bufmgr.c` (`ReadBufferExtended`, `LockBuffer`),
  `storage/ipc/procarray.c` (`safe_xmin` semantics),
  `access/transam/clog.c` (`TransactionIdDidCommit` chain).
- Visibility map: `access/heap/visibilitymap.c:visibilitymap_get_status`
  consumed by `:892`.
- amcheck siblings: `verify_common.c` is NOT called from
  verify_heapam — heap doesn't go through the index lock-wrap. It
  opens the heap directly at `:330`.
- Prior sweeps: A6 documented `pg_amcheck` which wraps both
  `verify_heapam` and `bt_index_check` from one CLI call.

<!-- issues:auto:begin -->
- [Issue register — `amcheck`](../../../issues/amcheck.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-correctness: `verify_heapam(..., check_toast=true)` can crash
  backend if the toast index is itself corrupted; documented by the
  function header but not defended against (confirmed)] —
  `verify_heapam.c:242-249,1887-1899`.
- [ISSUE-defense-in-depth: TOAST-tag short-circuit relies on
  `VARTAG_SIZE` being safe for unknown tags in release builds; debug
  Assert is the actual defense (likely)] — `verify_heapam.c:1721-1736`.
- [ISSUE-security: per-finding errmsg quotes raw xmin/xmax/xvac
  values — leaks xact IDs of writers to non-superuser invokers with
  EXECUTE grant (maybe)] — many sites, e.g.
  `verify_heapam.c:1141-1158,1411-1430,1476-1495`.
- [ISSUE-concurrency: `XactTruncationLock` released before
  `TransactionIdDidCommit` returns — racing CLOG truncation could
  in principle return garbage (nit)] — `verify_heapam.c:2161-2176`.
- [ISSUE-concurrency: heap scan + concurrent VACUUM on toast — toast
  lookup uses `get_toast_snapshot()` and `tuple_could_be_pruned`
  predicate; design is sound but if the predicate is wrong (e.g. due
  to clog truncation race above), we may follow a dangling toast
  pointer. (nit)] — `verify_heapam.c:1452-1454,1839-1850`.
- [ISSUE-error-handling: `on_error_stop` semantics are "stop at
  END of current page", not at first row — page may produce many
  rows before the loop breaks (documentation)] —
  `verify_heapam.c:228-232,854-855`.
- [ISSUE-api-shape: `startblock`/`endblock` are bigint but cast to
  BlockNumber; pre-cast range check at `:382-407` is correct, but a
  signed 0 from SQL would be coerced silently. Caller can pass
  `startblock=NULL, endblock=NULL` (defaults to whole table) (nit)] —
  `verify_heapam.c:382-407`.
- [ISSUE-memory: `tupstore` is materialized via `InitMaterializedSRF`;
  on catastrophic corruption, memory grows up to work_mem before
  spilling. Per-msg leak is freed eagerly (`:931-939`) so growth is
  proportional to corruption-row count, not msg-size churn. (nit)] —
  `verify_heapam.c:325-327,931-939`.
- [ISSUE-defense-in-depth: no rate-limit / abort on excessive
  corruption rows (nit)] — `verify_heapam.c:482-856`. Pathological
  page with all line-pointers corrupted produces O(MaxOffsetNumber)
  rows per page.
- [ISSUE-audit-gap: pre-9.0 `HEAP_MOVED_OFF`/`HEAP_MOVED_IN` xvac
  handling still present (~135 LOC of dead-end paths). Not a security
  issue but a maintenance one. (nit)] — `verify_heapam.c:1170-1305`.
- [ISSUE-concurrency: `BUFFER_LOCK_SHARE` released before toast
  cross-check fan-out (`:839`); checked toasted-attribute list may
  refer to a page that's been concurrently modified by HOT prune
  (which is fine for prune since we only released the lock, but the
  TID stored in `ta->blkno/offnum` may now describe a heap-only
  tuple that's been moved). The tuple's `tuple_could_be_pruned`
  guard should still hold, but only because xmax-vs-safe_xmin
  doesn't move. (nit)] — `verify_heapam.c:839-852,1839-1850`.
- [ISSUE-documentation: header at `:242-249` is the most honest crash
  disclosure in contrib/. Worth promoting to user-docs explicitly.
  (nit)]
