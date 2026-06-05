# Issues — `contrib/postgres_fdw`

Per-subsystem issue register for **postgres_fdw**, the flagship
cross-cluster trust-boundary module in the PostgreSQL tree. 6 source
files, ~16 916 LOC. The newer of the two cross-cluster bridges
(versus `dblink`); strictly stronger discipline on credentials and
connection lifecycle.

**Parent docs:** `knowledge/files/contrib/postgres_fdw/*` (6 docs:
`postgres_fdw.c.md`, `connection.c.md`, `deparse.c.md`,
`option.c.md`, `shippable.c.md`, `postgres_fdw.h.md`).

**Source:** 61 entries surfaced 2026-06-04 by the A11 foreground sweep
(agent A11-2). Mirrored in each per-file doc's `## Issues spotted`
block.

## Headlines

1. **`password_required` enforcement is two-layered and load-bearing.**
   `option.c:194` (CREATE-time superuser check) + `connection.c:759`
   (`check_conn_params` pre-connect) + `connection.c:446`
   (`pgfdw_security_check` post-connect cross-checking
   `PQconnectionUsedPassword`). **The canonical loopback-bypass-RLS
   attack requires the superuser to have explicitly set
   `password_required=false` on a USER MAPPING.** SCRAM passthrough
   adds a third allowed path (`require_auth=scram-sha-256`
   enforced). **This is the discipline that dblink lacks.**

2. **Connection cache keyed by `umid` alone** (`connection.c:54-55`).
   Collapses the PUBLIC user mapping case (one shared conn for all
   roles using it) and keeps per-role mappings isolated.
   Cross-role conn-reuse cannot happen within one backend. But
   `postgres_fdw_disconnect_all` lets non-superuser close
   superuser-opened conns in same session — explicit XXX comment
   at `connection.c:2576-2584`.

3. **Stats-import + ANALYZE-as-table-owner enlarge the privileged
   attack surface.** `postgres_fdw.c:5269` opens remote conn AS
   `relowner` during ANALYZE — any user with ANALYZE privilege
   thereby uses the owner's user mapping (including
   `password_required=false` if owner set it). `postgres_fdw.c:5591`
   imports remote `pg_stats` into local `pg_statistic` when
   `restore_stats=true` — a hostile remote can plant decoy MCVs to
   bias the local planner.

4. **TLS not enforced.** `option.c` does not default any minimum
   `sslmode`; libpq's default `prefer` allows MITM downgrade unless
   DBA sets `sslmode=require`. **Phase D candidate: optional
   `postgres_fdw.min_sslmode` GUC.**

5. **Cross-cluster semantic mismatch is silent.** Shippable
   functions/aggregates/types resolved by NAME at remote, no
   version/signature check. `shippable.c:117` only verifies
   extension membership locally. Collation pushdown
   (`deparse.c:347-388`) assumes local `varcollid` == remote
   column collation without verification. **Aggregate pushdown
   resolves by name — same-named aggregate with different semantics
   = silently wrong result** (`deparse.c:952`).

6. **`parallel_commit` is NOT 2PC** — split-brain on partial-commit
   failure. By design, but worth loud documentation
   (`connection.c:1216`).

7. **Remote tuple data leaks into local error messages.**
   `pgfdw_report_internal` echoes remote `PG_DIAG_MESSAGE_PRIMARY`
   verbatim into local logs (`connection.c:1153`) — remote tuple
   data the local user may lack RLS access to ends up in
   server-log strings.

8. **Extension-membership changes don't invalidate shippable cache**
   (`shippable.c:56-62`, XXX in code comment) — `ALTER EXTENSION
   ADD/DROP MEMBER` won't flush. Per-backend monotonic growth.

## Cross-sweep references

- **dblink (A11-1)**: same cross-cluster trust class but weaker
  posture — no `password_required` enforcement layer, no SCRAM
  passthrough, conninfo-trust model accepts any host.
- **A2 libpq**: postgres_fdw is the highest-leverage CONSUMER of
  the libpq API; the secret-scrub discipline, `password_required`
  invariant, SCRAM negotiation all flow through libpq machinery
  catalogued in A2.
- **NAME-vs-OID Phase D pattern**: postgres_fdw resolves every
  shippable type/function/aggregate by NAME at remote. Joins
  A3+A6+A7+A8+A9+A10+A11.
- **A4 pg_dump trust-the-source model**: postgres_fdw `restore_stats`
  is the same posture — local plans get poisoned by hostile remote
  statistics.

## Entries

### postgres_fdw.c (8 837 LOC)

- [ISSUE-security: remote string value leaks into local error via
  `InputFunctionCall` (likely)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:8523` — type-mismatch
  raises `invalid input syntax for type X: "<remote val>"` echoing
  data the local user may lack RLS access to.
- [ISSUE-security: ANALYZE opens connection AS TABLE OWNER (likely
  — Phase D)] — `source/contrib/postgres_fdw/postgres_fdw.c:5269` —
  a user with ANALYZE privilege thereby uses the owner's user
  mapping (including `password_required=false` if owner set it).
- [ISSUE-security: stats-import lets remote influence local
  pg_statistic (likely — Phase D)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:5591` — hostile
  remote can plant decoy MCVs to bias local planner. Mitigated by
  `restore_stats` opt-in.
- [ISSUE-security: IMPORT FOREIGN SCHEMA interpolates `format_type`
  / `pg_get_expr` raw into local DDL (maybe defense-in-depth)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:6541,6560` — trusts
  remote pg_catalog output is well-formed.
- [ISSUE-correctness: EXEC_FLAG_EXPLAIN_ONLY skips connection open
  — EXPLAIN may show stale schema (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:1730`.
- [ISSUE-correctness: `postgresIsForeignRelUpdatable` reads option
  at plan time; race with concurrent ALTER FOREIGN TABLE (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:2528`.
- [ISSUE-correctness: `find_modifytable_subplan` only handles
  ForeignScan immediate-child or Append-child of ModifyTable;
  other shapes silently fall back to non-direct modify (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:2625`.
- [ISSUE-correctness: floats sent as Params lose precision —
  `set_transmission_modes` doesn't cover param-value text emit
  (maybe)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:5065`.
- [ISSUE-correctness: `get_remote_estimate` parses `(cost=A..B
  rows=R width=W)` via sscanf; fragile to remote EXPLAIN format
  changes (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:3844`.
- [ISSUE-correctness: `postgresPlanForeignModify` opens local rel
  with NoLock trusting caller (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:2014`.
- [ISSUE-concurrency: `postgresForeignAsyncConfigureWait` decision
  tree for which pending request to drain has been historical bug
  source (maybe)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:8159-8229`.
- [ISSUE-error-handling: `process_pending_request` doesn't unset
  `callback_pending` if `fetch_more_data` throws (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:8373`.
- [ISSUE-defense-in-depth: no `FdwRoutine_hook` for monitoring/audit
  shims (likely)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:769`.
- [ISSUE-audit-gap: no instrumentation around
  `pgfdw_security_check` denials — bursty denials could indicate
  attack but go unlogged (maybe)] —
  `source/contrib/postgres_fdw/connection.c:446` (via conn-opening
  sites in this file).
- [ISSUE-correctness: stats-import doesn't support extended
  statistics; WARNING + return false (documented)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:5643`.
- [ISSUE-correctness: direct-modify bypasses ExecBuildAuxRowMark;
  uncertain whether local RLS-derived quals block this via
  `scan.plan.qual == NIL` (maybe)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:2701-2706`.
- [ISSUE-correctness: `apply_server_options`/`apply_table_options`
  O(N) per-partition — perf nit for partition-heavy schemas
  (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:7092`.
- [ISSUE-correctness: `postgresExplainDirectModify` only emits
  Remote SQL on VERBOSE — UX nit (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:3186`.
- [ISSUE-correctness: `fpinfo->user` cached at plan time; RESET
  ROLE before exec means different user at runtime (by-design but
  undocumented) (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:887,3381,1743`.
- [ISSUE-defense-in-depth: direct-modify RETURNING uses local
  apply_returning_filter; remote schema drift surfaces only at
  type-mismatch (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:2843`.
- [ISSUE-correctness: TRUNCATE same-server assertion is
  defense-in-depth; release-build wrong-server case relies on core
  never violating contract (resolved)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:3247-3250`.
- [ISSUE-correctness: EXEC_FLAG_EXPLAIN_ONLY-protected DirectBegin
  / ScanBegin paths skip auth — verified safe but worth a
  regression test (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.c:1730,2876`.

### connection.c (2 756 LOC)

- [ISSUE-security: `postgres_fdw_disconnect_all` lets non-superuser
  close superuser conn in same session (likely — XXX in code
  comment)] — `source/contrib/postgres_fdw/connection.c:2587`.
- [ISSUE-security: `configure_remote_session` is one-shot at
  connect; a malicious remote view can subvert via `set_config`
  (defense-in-depth maybe — comment admits)] —
  `source/contrib/postgres_fdw/connection.c:811`.
- [ISSUE-security: `pgfdw_report_internal` echoes remote
  PG_DIAG_MESSAGE_PRIMARY verbatim — remote tuple data in error
  messages leaks to local logs (likely)] —
  `source/contrib/postgres_fdw/connection.c:1153`.
- [ISSUE-security: parallel_commit is NOT 2PC — split-brain on
  partial-commit failure (likely — by design)] —
  `source/contrib/postgres_fdw/connection.c:1216`.
- [ISSUE-security: SCRAM passthrough requires
  `require_auth=scram-sha-256` ✓, but default `sslmode` is libpq's
  `prefer` — downgrade-vulnerable (likely)] —
  `source/contrib/postgres_fdw/connection.c:611`.
- [ISSUE-correctness: `CONNECTION_CLEANUP_TIMEOUT=30000`
  hard-coded; high-latency remotes get permanently poisoned
  (likely)] — `source/contrib/postgres_fdw/connection.c:106`.
- [ISSUE-correctness: `prep_stmt_number` never resets — 4B-stmt
  wraparound theoretically collides (nit)] —
  `source/contrib/postgres_fdw/connection.c:1056`.
- [ISSUE-correctness: `XACT_EVENT_PRE_PREPARE` errors unconditionally;
  read-only remote xact PREPARE could be allowed (documented
  limitation)] —
  `source/contrib/postgres_fdw/connection.c:1249-1262`.
- [ISSUE-error-handling: `do_sql_command_end` blocks on
  `pgfdw_get_result`; malicious NoticeResponse loop relies on
  libpq's CHECK_FOR_INTERRUPTS (maybe)] —
  `source/contrib/postgres_fdw/connection.c:863`.
- [ISSUE-error-handling: `connect_pg_server` PG_TRY/CATCH around
  volatile PGconn; `libpqsrv_disconnect(NULL)` had better be safe
  (nit)] —
  `source/contrib/postgres_fdw/connection.c:628-684`.
- [ISSUE-concurrency: `pgfdw_security_check` runs once post-connect;
  no re-check on auth-refresh (nit)] —
  `source/contrib/postgres_fdw/connection.c:446`.
- [ISSUE-defense-in-depth: `appendEscapedValue` correctly quotes for
  SQL connection string, but `postgres_fdw_connection` emits raw
  password from mapping options — ACL-protected, defense-in-depth
  concern (nit)] —
  `source/contrib/postgres_fdw/connection.c:2456-2467`.
- [ISSUE-audit-gap: no audit log entry on connection open/close to
  foreign server (likely — defense-in-depth)] —
  `source/contrib/postgres_fdw/connection.c:628`.
- [ISSUE-correctness: `pgfdw_inval_callback` decision logic is
  correct but fiddly; concurrent ALTER USER MAPPING race window
  verified safe (nit)] —
  `source/contrib/postgres_fdw/connection.c:1442`.

### deparse.c (4 255 LOC)

- [ISSUE-correctness: T_CaseExpr pushdown bails when WHEN isn't
  OpExpr+CaseTestExpr; optimizer pass changes silently demote
  pushable CASE (likely)] —
  `source/contrib/postgres_fdw/deparse.c:793-816`.
- [ISSUE-correctness: result-type check `is_shippable(exprType(node))`
  fragile vs `check_type=false` for List nodes (nit)] —
  `source/contrib/postgres_fdw/deparse.c:935,1050`.
- [ISSUE-security: aggregate pushdown resolves by name at remote;
  same-named aggregate with different semantics → silently wrong
  result (likely — Phase D class)] —
  `source/contrib/postgres_fdw/deparse.c:952`.
- [ISSUE-correctness: JOIN collation pushdown assumes local
  `varcollid` matches remote column collation; no verification
  (likely)] — `source/contrib/postgres_fdw/deparse.c:347-388`.
- [ISSUE-correctness: T_Aggref pushdown only fires in UPPER_REL
  context; future planner refactor might silently downgrade to
  local (nit)] — `source/contrib/postgres_fdw/deparse.c:943`.
- [ISSUE-defense-in-depth: `deparse_type_name` schema-qualifies
  with LOCAL schema name; remote `myschema.mytype` with different
  semantics is silently mis-emitted (likely)] —
  `source/contrib/postgres_fdw/deparse.c:1190-1198`.
- [ISSUE-correctness: DECLARE CURSOR ... FOR UPDATE behavior
  differs across remote PG versions (documented limitation)] —
  `source/contrib/postgres_fdw/deparse.c:1530-1540`.
- [ISSUE-correctness: `truncatable=false` foreign-table option is
  checked at TRUNCATE statement level, NOT at remote-CASCADE path
  (likely — Phase D class)] —
  `source/contrib/postgres_fdw/deparse.c:2677`,
  `source/contrib/postgres_fdw/postgres_fdw.c:3265`.
- [ISSUE-correctness: `deparseConst` numeric bare-emit gate via
  `strspn` — locale-dependent inputs (theoretical, mitigated by
  `set_transmission_modes`) (nit)] —
  `source/contrib/postgres_fdw/deparse.c:3092`.
- [ISSUE-correctness: PARAM_MULTIEXPR bailout ties to planner-stage
  detail; future stage-ordering change breaks it (nit —
  defensive)] —
  `source/contrib/postgres_fdw/deparse.c:486-500`.
- [ISSUE-audit-gap: no Deparse_hook — pgaudit-style logging cannot
  intercept emitted SQL without monkey-patching (likely —
  defense-in-depth)] — entire file.
- [ISSUE-correctness: TS-config `FirstNormalObjectId` cutoff vs
  builtin `FirstGenbkiObjectId` cutoff asymmetry, code-smell trap
  (nit)] — `source/contrib/postgres_fdw/deparse.c:439`.

### option.c (596 LOC)

- [ISSUE-security: ALTER USER MAPPING validator doesn't see old
  value; documented but should have regression test (nit —
  defensive)] — `source/contrib/postgres_fdw/option.c:187`.
- [ISSUE-security: no enforcement of minimum `sslmode` —
  `sslmode=disable` for non-superuser USER MAPPING silently
  accepted (maybe defense-in-depth)] —
  `source/contrib/postgres_fdw/option.c:244-301`.
- [ISSUE-security: SERVER-level `host`/`port`/`hostaddr` + USER
  MAPPING `password_required=false` = canonical loopback-bypass-
  RLS pattern (likely — well-known Phase D)] —
  `source/contrib/postgres_fdw/option.c:244-301`.
- [ISSUE-security: `process_pgfdw_appname` interpolates local
  user-controlled
  `application_name`/`user_name`/`database_name` into remote
  `application_name` — info-flow channel to remote logs (nit)] —
  `source/contrib/postgres_fdw/option.c:496`.
- [ISSUE-correctness: `is_valid_option`/`is_libpq_option` linear
  scans (~30 entries, trivial) (nit)] —
  `source/contrib/postgres_fdw/option.c:379`.
- [ISSUE-defense-in-depth: `ExtractExtensionList` warns-only on
  unknown extensions at validate time, silently treats as
  non-shippable at plan time — typo masks extension removal
  (nit)] — `source/contrib/postgres_fdw/option.c:469-481`.
- [ISSUE-api-shape: `postgres_fdw.application_name` GUC has no
  check_hook — invalid strings deferred to next connect (nit)] —
  `source/contrib/postgres_fdw/option.c:583`.
- [ISSUE-correctness: asymmetric memory handling — libpq keywords
  pstrdup'd, non-libpq table memcpy'd as static pointers; foot-gun
  for future runtime-built keywords (nit)] —
  `source/contrib/postgres_fdw/option.c:351,371`.

### shippable.c (207 LOC)

- [ISSUE-correctness: extension-membership changes (`ALTER
  EXTENSION ADD/DROP MEMBER`) don't invalidate shippable cache;
  XXX in comment confirms by-design (likely)] —
  `source/contrib/postgres_fdw/shippable.c:56-62`.
- [ISSUE-security: extension declared "shippable" assumes remote
  version compatibility without verification — Phase D
  cross-cluster semantics mismatch (maybe defense-in-depth)] —
  `source/contrib/postgres_fdw/shippable.c:117`.
- [ISSUE-correctness: TS-config / TS-dictionary use
  `FirstNormalObjectId` (16384) instead of `FirstGenbkiObjectId`
  cutoff — asymmetric trap (nit)] —
  `source/contrib/postgres_fdw/deparse.c:439` and
  `source/contrib/postgres_fdw/shippable.c:155`.
- [ISSUE-memory: shippable cache grows monotonically per backend
  (nit)] — `source/contrib/postgres_fdw/shippable.c:100`.
- [ISSUE-defense-in-depth: `is_builtin` returns true for
  information_schema fns since they may be < `FirstGenbkiObjectId`;
  types are tighter via `deparse_type_name`, functions/operators
  not — asymmetric (nit)] —
  `source/contrib/postgres_fdw/shippable.c:144`.

### postgres_fdw.h (262 LOC)

- [ISSUE-api-shape: `PgFdwRelationInfo` has no version stamp;
  extensions subclassing (none today, but header installed in
  pkg-include) would silently break across PG upgrades (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.h:30`.
- [ISSUE-documentation: line 88 comment says `user` only set in
  remote-estimate mode but doesn't enumerate callers — future
  contributors risk NPE (nit)] —
  `source/contrib/postgres_fdw/postgres_fdw.h:88`.
