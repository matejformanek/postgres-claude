# Issues — `contrib/amcheck`

Per-subsystem issue register for **amcheck**, the canonical
PostgreSQL relation/index integrity-verification toolkit. 5 source
files / ~6 800 LOC. The backend counterpart to A6's pg_amcheck CLI
wrapper.

**Parent docs:** `knowledge/files/contrib/amcheck/*` (4 docs:
`verify_common.md` combines .c+.h, `verify_gin.md`,
`verify_heapam.md`, `verify_nbtree.md`).

**Source:** ~30 entries surfaced 2026-06-09 by the A12 foreground
sweep (agent A12-1). Mirrored in each per-file doc's `## Issues
spotted` block.

## Headlines

1. **amcheck's ONLY access gate is `REVOKE FROM PUBLIC` in install
   SQL** (`verify_common.c:155-159` — explicit "intentionally not
   checking permissions" comment). The C backend has ZERO
   `superuser()` / `has_privs_of_role()` checks. A misconfigured
   `GRANT EXECUTE` or SECURITY DEFINER wrapper fully exposes the
   checker — and amcheck error details surface page LSN + heap-TID +
   downlink block + xmin/xmax XID values across all three verifiers.
   **Side-channel exposing per-page write timing + XID disclosure +
   physical layout.**

2. **`verify_heapam(check_toast=true)` is explicitly documented as
   "can crash the backend" if the toast index is corrupted**
   (`verify_heapam.c:242-249, 1887-1899`). Only contrib function in
   the tree with this level of honest crash disclosure. The
   prerequisite workaround (run `bt_index_check` on the toast index
   first) is NOT enforced.

3. **TOAST-pointer fuzzing surface is well-defended in principle.**
   The 4-step check at `verify_heapam.c:1724-1810` is the canonical
   anti-OOB recipe (IS_EXTERNAL → VARTAG_EXTERNAL == VARTAG_ONDISK →
   alignment GET_POINTER → va_rawsize bound → compression method
   ID). In release builds the VARTAG_SIZE Assert at `:1721-1723` is
   the second line of defense; the short-circuit at `:1728-1735`
   should prevent it ever firing.

4. **verify_heapam vs verify_nbtree differ sharply on error policy**
   — heap accumulates into tuplestore with `on_error_stop` knob;
   nbtree/gin ereport(ERROR) on first finding. On a 1 TB index with
   corruption near block 0, `bt_index_check` gives one row then
   dies; same table via `verify_heapam` reports every finding. The
   nbtree path is the higher-confidence side channel because every
   finding immediately surfaces in client output.

## Cross-sweep references

- **A6 pg_amcheck CLI** wraps amcheck backend; the fail-open at
  per-database level documented in A6 is INHERITED here at the
  backend (amcheck does not enforce its own role gate).
- **A11 contrib trust-gate ranking**: amcheck is structurally
  WEAKER than postgres_fdw — no role-check at all vs postgres_fdw's
  two-layered defense.

## Entries (~30 total)

### verify_common.c + verify_common.h

- [ISSUE-audit-gap: REVOKE-FROM-PUBLIC is the only access gate; no
  `superuser()`/`has_privs_of_role()` check in C (likely)] —
  `source/contrib/amcheck/verify_common.c:155-159` — comment is
  explicit ("intentionally not checking permissions").
- [ISSUE-security: amcheck error details leak tid/lp/page-LSN of
  tables the invoker may not be able to SELECT from (maybe)] —
  `source/contrib/amcheck/verify_common.c:62-150` + sites in
  verify_nbtree/verify_heapam.
- [ISSUE-correctness: post-IndexGetRelation race recheck defeatable
  by very fast drop-recreate cycle (nit)] —
  `source/contrib/amcheck/verify_common.c:126`.
- [ISSUE-documentation: hot-standby ShareLock behavior is implicit
  via `index_open` failing, not explicit (nit)] —
  `source/contrib/amcheck/verify_common.c:81`.

### verify_gin.c

- [ISSUE-concurrency: GIN walker under AccessShareLock can race
  posting-tree page recycling and raise spurious "unexpected zero
  page" / "corrupted page" (maybe)] —
  `source/contrib/amcheck/verify_gin.c:670-708`.
- [ISSUE-defense-in-depth: posting-tree root recursion guarded only
  by debug-only `Assert(GinPageIsData)` (likely)] —
  `source/contrib/amcheck/verify_gin.c:179`.
- [ISSUE-defense-in-depth: no vacuum_delay_point / cost yield in
  long GIN walks (nit)] —
  `source/contrib/amcheck/verify_gin.c:431,172`.
- [ISSUE-error-handling: bare `elog(ERROR,...)` at `:112-113` leaks
  internal counter values to invoker (nit)] —
  `source/contrib/amcheck/verify_gin.c:112-113`.
- [ISSUE-defense-in-depth: no `gin_index_parent_check`;
  AccessShareLock-only — heavyweight cross-checks unavailable for
  GIN (likely)] — `source/contrib/amcheck/verify_gin.c:83-87`.
- [ISSUE-documentation: pre-9.4 binary-upgrade pd_lower exception
  noted but hard-ERROR enforced anyway (nit)] —
  `source/contrib/amcheck/verify_gin.c:263-274`.
- [ISSUE-correctness: `palloc(0)` for empty uncompressed branch —
  legal but inconsistent (nit)] —
  `source/contrib/amcheck/verify_gin.c:115-117`.

### verify_heapam.c

- [ISSUE-correctness: `verify_heapam(..., check_toast=true)` can
  crash backend if toast index itself is corrupted; documented in
  header (confirmed)] —
  `source/contrib/amcheck/verify_heapam.c:242-249,1887-1899`.
- [ISSUE-defense-in-depth: TOAST-tag short-circuit relies on
  `VARTAG_SIZE` being safe for unknown tags in release builds;
  debug Assert is the actual defense (likely)] —
  `source/contrib/amcheck/verify_heapam.c:1721-1736`.
- [ISSUE-security: per-finding errmsg quotes raw xmin/xmax/xvac —
  leaks xact IDs of writers to non-superuser invokers (maybe)] —
  `source/contrib/amcheck/verify_heapam.c:1141-1158,1411-1430,1476-1495`.
- [ISSUE-concurrency: `XactTruncationLock` released before
  `TransactionIdDidCommit` returns — racing CLOG truncation could
  in principle return garbage (nit)] —
  `source/contrib/amcheck/verify_heapam.c:2161-2176`.
- [ISSUE-concurrency: `tuple_could_be_pruned` predicate depends on
  clog-race-tolerant horizon — if predicate wrong, we could follow
  dangling toast pointer (nit)] —
  `source/contrib/amcheck/verify_heapam.c:1452-1454,1839-1850`.
- [ISSUE-error-handling: `on_error_stop` semantics are "stop at END
  of current page", not at first row (documentation)] —
  `source/contrib/amcheck/verify_heapam.c:228-232,854-855`.
- [ISSUE-api-shape: `startblock`/`endblock` are bigint but cast to
  BlockNumber; pre-cast range check correct (nit)] —
  `source/contrib/amcheck/verify_heapam.c:382-407`.
- [ISSUE-memory: catastrophic corruption can produce
  O(MaxOffsetNumber) rows per page; tuplestore growth proportional.
  No rate-limit (nit)] —
  `source/contrib/amcheck/verify_heapam.c:325-327,482-856`.
- [ISSUE-defense-in-depth: no rate-limit / abort on excessive
  corruption-row count (nit)] —
  `source/contrib/amcheck/verify_heapam.c:482-856`.
- [ISSUE-audit-gap: pre-9.0 `HEAP_MOVED_OFF`/`HEAP_MOVED_IN` xvac
  handling still present (~135 LOC, dead-end paths) (nit)] —
  `source/contrib/amcheck/verify_heapam.c:1170-1305`.
- [ISSUE-concurrency: BUFFER_LOCK_SHARE released before toast
  cross-check fan-out (nit)] —
  `source/contrib/amcheck/verify_heapam.c:839-852,1839-1850`.
- [ISSUE-documentation: header at `:242-249` is honest crash
  disclosure; worth promoting to user docs (nit)].

### verify_nbtree.c

- [ISSUE-security: page LSN in errdetail leaks per-page write
  timing to non-superuser invokers (maybe)] — endemic across
  `source/contrib/amcheck/verify_nbtree.c:1274,1322,1397,1426,1478,1585,1632,2226,2312,2354,2493,2693`.
- [ISSUE-security: heap-TID and downlink-block in errdetail leak
  physical layout to non-superuser invoker (maybe)] —
  `source/contrib/amcheck/verify_nbtree.c:1397-1399,2491-2496`.
- [ISSUE-defense-in-depth: heapallindexed Bloom seed from
  `pg_global_prng_state`, not cryptographic source (nit)] —
  `source/contrib/amcheck/verify_nbtree.c:431`.
- [ISSUE-defense-in-depth: `bt_index_parent_check` holds ShareLock
  for entire walk; no vacuum_delay_point / cost yield (nit)] —
  `source/contrib/amcheck/verify_nbtree.c:653,1305,2641`.
- [ISSUE-concurrency: under !readonly the `lowkey` threading across
  pages "wasn't investigated yet" for concurrent splits
  (from-comment / likely)] —
  `source/contrib/amcheck/verify_nbtree.c:815-818`.
- [ISSUE-concurrency: missing-P_NONE-validation in
  bt_recheck_sibling_links left-side under !readonly (likely)] —
  `source/contrib/amcheck/verify_nbtree.c:762-768`.
- [ISSUE-correctness: `bt_pivot_tuple_identical` is raw memcmp —
  both copies corrupt with matching wrong contents would pass
  (nit)] — `source/contrib/amcheck/verify_nbtree.c:2071-2104`.
- [ISSUE-error-handling: first corruption finding aborts whole
  call; no `on_error_stop`-style knob (api-shape)] — endemic, e.g.
  `source/contrib/amcheck/verify_nbtree.c:1318-1327`.
- [ISSUE-defense-in-depth: `bt_rootdescend` passes NULL snapshot to
  `_bt_search` (correct but undocumented in C-side comment) (nit)]
  — `source/contrib/amcheck/verify_nbtree.c:3028`.
- [ISSUE-audit-gap: `checkunique` reuses `state->snapshot` from
  heapallindexed path; refactor surface (nit)] —
  `source/contrib/amcheck/verify_nbtree.c:471-477`.
- [ISSUE-concurrency: `bt_recheck_sibling_links` couples buffer
  locks under !readonly — only place in amcheck (from-comment /
  nit)] — `source/contrib/amcheck/verify_nbtree.c:1108-1166`.
- [ISSUE-defense-in-depth: `bt_normalize_tuple` external-varlena
  check unreachable from poisoned-heap path during heapallindexed
  Bloom flow (api-shape)] —
  `source/contrib/amcheck/verify_nbtree.c:2884-2890`.
- [ISSUE-documentation: rootdescend O(N log N) cost not in C-side
  function comment (nit)] —
  `source/contrib/amcheck/verify_nbtree.c:283-306`.
- [ISSUE-correctness: half-dead-internal-page errhint suggests
  REINDEX even though hot standby can't REINDEX (nit)] —
  `source/contrib/amcheck/verify_nbtree.c:3419-3424`.
