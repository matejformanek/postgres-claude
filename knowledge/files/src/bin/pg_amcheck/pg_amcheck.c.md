# `src/bin/pg_amcheck/pg_amcheck.c`

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`. File is ~2240 lines.

## Purpose

`pg_amcheck` is a **client-side driver** for the `amcheck` contrib extension.
It does **no** page parsing or corruption detection itself — it just enumerates
relations across one or more databases, sends `verify_heapam()` (heap) or
`bt_index_check()` / `bt_index_parent_check()` (btree) calls to the server over
libpq, and renders the results to stdout. The actual page-walking, checksum
verification, line-pointer validation, and TOAST chain traversal all live in
`contrib/amcheck` on the backend side.

What it **does**:

- Build a list of databases (from `--all`, `--database PATTERN`, or the
  positional `DBNAME`) [verified-by-code, pg_amcheck.c:484-515].
- For each database, optionally `CREATE EXTENSION amcheck`
  [pg_amcheck.c:547-564], discover the schema amcheck is installed in
  [pg_amcheck.c:573-600], then compile a list of relations via a complex CTE
  query [pg_amcheck.c:1884-2240].
- Fan out check queries across `-j N` parallel slots
  [pg_amcheck.c:703-797].
- Render server-returned corruption tuples (heap) or libpq error messages
  (btree) [pg_amcheck.c:1038-1173].

What it **doesn't**:

- It does **not** open relation files directly. No `mmap`, no `pg_pread`.
  Everything happens over SQL.
- It does **not** decode WAL, recover, or modify any data.
- It does **not** drop or recreate amcheck except when
  `--install-missing` is given, in which case it issues a
  `CREATE EXTENSION IF NOT EXISTS` per database.

## Role in pg_amcheck (main loop)

`main()` at pg_amcheck.c:219-825:

1. **Option parse** (lines 299-450). `getopt_long` over a 36-entry option
   table; pattern collectors push into `opts.include` / `opts.exclude`
   `PatternInfoArray`s.
2. **Initial connect** (lines 484-515). Picks `--maintenance-db` (postgres /
   template1) if `--all` was given, else the named DB or the env-derived
   default.
3. **Compile database list** (line 500 or 514, → `compile_database_list`).
4. **Per-database loop** (lines 528-637): reconnect if datname differs, install
   amcheck if asked, look up `amcheck_schema` via the `amcheck_sql` query, then
   `compile_relation_list_one_db()` to grow the global `relations` list.
5. **Inclusion-pattern audit** (lines 643-671): every `--table` / `--schema`
   pattern that matched zero relations becomes either a warning or a fatal
   error depending on `--strict-names` (default on).
6. **Set up parallel slots** (lines 703-709). `ParallelSlotsAdoptConn`
   donates the initial connection back to the pool.
7. **Main dispatch loop** (lines 712-797). For each `RelationInfo`, build the
   per-relation SQL via `prepare_heap_command` or `prepare_btree_command`,
   install a handler, and `PQsendQuery` it via the slot.
8. **Wait for completion** (lines 800-812). `ParallelSlotsWaitCompletion`.
9. **Exit codes** (lines 820-824):
   - `exit(1)` if a slot's check command failed catastrophically.
   - `exit(2)` if all queries succeeded but `all_checks_pass` was flipped to
     `false` because at least one corruption row was returned.
   - `exit(0)` (implicit) only if every check ran AND found nothing.

This three-valued exit code is meaningful — see "Phase D notes" below.

## Key functions

| Function | Lines | Role |
|---|---|---|
| `main` | 219-825 | Driver, see above. |
| `prepare_heap_command` | 842-864 | Build `SELECT … FROM …verify_heapam(...)` for one heap relation. |
| `prepare_btree_command` | 882-916 | Build `SELECT bt_index_check / bt_index_parent_check(...)`. |
| `run_command` | 931-945 | `PQsendQuery` non-blocking; `exit(1)` on hard send failure. |
| `should_processing_continue` | 963-1000 | Decide if a `PGresult` is fatal enough to drain the queue. FATAL / PANIC sev → stop; everything else (incl. PGRES_NONFATAL_ERROR, regular ERROR) → continue. |
| `indent_lines` | 1007-1026 | Render a multi-line libpq error message with each line indented 4 spaces. |
| `verify_heap_slot_handler` | 1038-1104 | Print each heap-corruption tuple as `heap table "db.schema.tbl", block X, offset Y, attribute Z:` + message. |
| `verify_btree_slot_handler` | 1119-1173 | Btree returns either zero rows or one void; >1 rows = pg_amcheck/amcheck version mismatch warning. Non-OK status → render libpq error as the corruption report. |
| `help` | 1182-1232 | Usage. |
| `progress_report` | 1243-1327 | Throttled stderr progress at most once per second, includes per-DB name with leading-truncation. |
| `extend_pattern_info_array` | 1335-1346 | Realloc-grow the pattern array by one. |
| `append_database_pattern` | 1357-1376 | Parse `--database PATTERN` via `patternToSQLRegex`; reject dotted names. |
| `append_schema_pattern` | 1387-1416 | Parse `db.schema` form; allow one dot. |
| `append_relation_pattern_helper` | 1429-1467 | Parse `db.schema.rel` form; allow two dots. |
| `append_relation_pattern` / `append_heap_pattern` / `append_btree_pattern` | 1479-1515 | Thin wrappers that flag `heap_only` / `btree_only`. |
| `append_db_pattern_cte` | 1538-1569 | Emit `VALUES (id, dbregex)` rows for database-only patterns. |
| `compile_database_list` | 1584-1754 | Build a multi-CTE query that joins patterns against `pg_database`, filtering by `datallowconn AND datconnlimit != -2`. |
| `append_rel_pattern_raw_cte` | 1776-1825 | Emit the six-column VALUES seed CTE for relation patterns. |
| `append_rel_pattern_filtered_cte` | 1845-1862 | Filter the raw CTE by the currently connected database. |
| `compile_relation_list_one_db` | 1884-2240 | The big one: join `pg_class`/`pg_namespace`/`pg_index` against include/exclude CTEs + the `--no-dependent-toast` / `--no-dependent-indexes` UNION arms. Produces relations sorted by `relpages DESC`. |

## State / globals

- `static AmcheckOptions opts` [pg_amcheck.c:112-139]. The whole command line
  rolled up into one struct, with explicit defaults including
  `.strict_names = true` (so unmatched patterns are an error, not a warning),
  `.reconcile_toast = true`, `.startblock = -1`, `.endblock = -1`,
  `.install_schema = "pg_catalog"`.
- `static const char *progname` [pg_amcheck.c:141].
- `static bool all_checks_pass = true` [pg_amcheck.c:144]. Flipped to false by
  `verify_heap_slot_handler` if any tuple comes back, and by either handler if
  a query returns a non-OK status. **Drives the exit-code-2 path.**
- `static pg_time_t last_progress_report` + `static bool
  progress_since_last_stderr` [pg_amcheck.c:147-148].

No password retention here — the password is consumed by libpq during the
initial connect and again during each reconnect via the shared `cparams`. The
`ConnParams` struct holds no password; that's libpq's job via the
`PGPASSWORD` env or `.pgpass`.

## The check pipeline — attacker-influenced inputs flowing to the backend

This is where pg_amcheck's posture as a verifier matters. The actual SQL
fired into the server is constructed in `prepare_heap_command` and
`prepare_btree_command`. **Every per-call argument is either a numeric
constant, an OID we just selected from `pg_class`, or a token from a small
whitelist** [verified-by-code, pg_amcheck.c:846-915]:

- `relation := <reloid>` — `Oid`, formatted with `%u`. Came from
  `SELECT c.oid FROM pg_catalog.pg_class`. Trusted.
- `on_error_stop := true/false` — boolean from `opts.on_error_stop`.
- `check_toast := true/false` — boolean from `opts.reconcile_toast`.
- `skip := 'all-visible' | 'all-frozen' | 'none'` — pg_amcheck pins this to
  one of three literal C strings before we ever get here
  [pg_amcheck.c:397-405], so the single-quoted value can't be attacker-
  controlled. Even if a future maintainer parametrises `--skip`, the values
  would still flow as a SQL string literal embedded with `%s` — that **would**
  be a vector if the validation were dropped. Tag below.
- `startblock := <int64>` — `int64` previously validated against
  `MaxBlockNumber` and `strtoul` errno checks [pg_amcheck.c:406-422]. Note:
  `MaxBlockNumber` is `0xFFFFFFFE` (≈ 4.29 G), and pg_amcheck stores it in
  `int64`. Safe.
- `endblock := <int64>` — same. And `endblock < startblock` is rejected at
  line 452.
- `heapallindexed := true/false`, `rootdescend := true/false`,
  `checkunique := true` — booleans; the latter is only added when
  `dat->is_checkunique` was confirmed by version probe.
- The amcheck schema name is pre-escaped via `PQescapeIdentifier` at line 599
  and stored in `dat->amcheck_schema`. **This is the only string interpolated
  with `%s` into the function-call SQL.**

In short: the SQL that reaches `verify_heapam` / `bt_index_check` carries no
user-typed strings — only OIDs, ints, and a hardcoded enum. Pattern strings
go through `patternToSQLRegex` and reach the server **as string literals
inside CTEs** that `pg_class.relname ~ ...` matches against; they never become
SQL identifiers, so injection-via-pattern is not a concern.

What actually gets parsed by attackers? **The heap pages themselves.** If
the heap is corrupt, `verify_heapam()` returns rows or raises errors, but the
parsing happens server-side and the output flows back as Datum text.
pg_amcheck has no exposure here beyond "render whatever the server told us".

## Output / error formatting

Three sinks:

- **stdout** for the corruption reports themselves
  [pg_amcheck.c:1062-1083, 1091-1095]:

  ```
  heap table "db.schema.tbl", block 42, offset 7, attribute 3:
      <msg from verify_heapam.msg column>
  ```

  The `msg` value is `PQgetvalue(res, i, 3)` — the raw `text` column from the
  server. **It is printed via `printf("    %s\n", msg)` with no escaping.**
  This is the same posture as pg_dump's relname-in-comment exposure: if an
  attacker can plant arbitrary text in a backend's amcheck-message output, a
  terminal emulator might interpret control sequences. In practice
  `verify_heapam` produces canned messages, but the msg can include attribute
  values, table names, etc. Tag below.

- **stderr** for `pg_log_*` and the libpq-error rendering for btree
  [pg_amcheck.c:1088-1097, 1156-1166]. Btree errors come back as
  `PQerrorMessage(conn)` which `indent_lines()` reformats with a 4-space
  leading indent — `printf("%s", msg)` after that, again unescaped.

- **stderr** for progress only when `--progress` is on
  [pg_amcheck.c:1243-1327]. The progress line includes `datname` truncated to
  35 chars with a leading `...` if too long. Datname comes from `pg_database`
  and is trusted to be a valid pg-identifier, but a stray TAB / DEL in a
  database name would still pass through unescaped.

## Phase D notes

**1. Pattern parser — `patternToSQLRegex`, NOT `processSQLNamePattern`.**
pg_amcheck uses `fe_utils/string_utils.c:patternToSQLRegex` for `--database`,
`--schema`, `--table`, `--index`, `--relation` and their exclude twins
[pg_amcheck.c:1365, 1398, 1443]. This is the **regex-producing** sibling of
`processSQLNamePattern`. Both share the same quote/escape machinery in
`patternToSQLRegex` (lines 1219-… in `src/fe_utils/string_utils.c`); the
output goes into a CTE `VALUES` literal via `appendStringLiteralConn` and is
applied as `pg_class.relname ~ regex`. So the same chokepoint discipline
that pg_dump and psql enjoy applies here, just via a different exit point.
**Pattern injection is not a vector** — the regex is parameterised, the
relname is matched, not concatenated.

**2. Fail-open vs fail-closed posture.** pg_amcheck is mostly fail-closed
but with a deliberate fail-open seam:

- A per-relation amcheck call that fails with a regular ERROR (not FATAL /
  PANIC) flips `all_checks_pass = false` and is rendered to the user as
  a corruption report [pg_amcheck.c:1086-1097, 1156-1166]. So "the check
  couldn't run" looks identical to "the check found corruption" — both
  drive exit-code 2. This is fail-CLOSED for the per-relation case.
- However, an entire database is **silently skipped** if `amcheck` is not
  installed: `pg_log_warning("skipping database \"%s\": amcheck is not
  installed")` then `continue` [pg_amcheck.c:585-594]. There's no impact on
  `all_checks_pass` and no impact on the final exit code. If an operator runs
  `pg_amcheck --all` and one of N databases is missing the extension, exit-0
  is possible despite that database never being checked. `[ISSUE-state-transition: --all silently skips databases without amcheck extension, exit-0 doesn't mean "everything checked" (maybe)]`
- Patterns that match no relations are fatal **only if `--strict-names`** is
  on (which it is by default) [pg_amcheck.c:207-212, 666-671]. A user who
  passes `--no-strict-names` reverts to fail-open on the "did anything get
  checked?" axis — and an attacker who controls a fragment of a pattern
  could exploit this. But this is an explicit opt-out.
- `compile_database_list` filters out `datallowconn = false` and
  `datconnlimit = -2` databases [pg_amcheck.c:1641]. These are silently
  skipped from `--all`. This is correct (they can't be connected to) but
  contributes to the "what fraction of pg_database actually got walked" gap.

**Bottom line:** for the typical `pg_amcheck --all` invocation, pg_amcheck
is **fail-closed for per-relation issues** (any failure inside a check is
loud) but **fail-open for "this whole database wasn't checkable"** (missing
extension, datallowconn=false, datconnlimit=-2 are warnings, not failures).
A verifier-as-policy-gate should treat exit-0 as "everything I touched was
clean", not "the cluster is clean".

**3. `--all` reads `pg_database` server-side.** Same trust shape as
pg_dumpall (A3): datnames come from a `SELECT … FROM pg_catalog.pg_database`
on the maintenance DB [pg_amcheck.c:1636-1645]. Each name is then passed as
`cparams.override_dbname` to `connectDatabase`. libpq treats it as a
connection-string component; valid identifier rules apply server-side. A
hostile superuser who can plant a database with a weird name might get
pg_amcheck to print that name unescaped in the progress meter (line 1305) and
in corruption messages (line 1062), but cannot inject SQL into the per-DB
amcheck queries (the query uses `c.oid`, not relname).

**4. Connection re-use across databases.** Lines 536-541: if the next
database in the list differs from `PQdb(conn)`, the current connection is
torn down and a fresh one is opened. **The password obtained on first
connect is held by libpq via the connection string / env / .pgpass — there's
no `simple_prompt`-then-reuse here.** If `--password` was passed, `prompt_password
= TRI_YES` and libpq prompts on each reconnect (annoying). If `-w`,
re-auths fail loudly. This is the same shape as pg_dumpall but driven by
libpq, not by `simple_prompt`-stashing. `[verified-by-code]`

**5. Parallel scheduling.** `parallel_workers = min(opts.jobs, ntotal)`.
`ParallelSlotsSetup` allocates the slot pool [pg_amcheck.c:703]; relations are
sorted by `relpages DESC NULLS FIRST, oid` [pg_amcheck.c:2150] so the largest
relations get dispatched first — classic LPT scheduling, good for parallel
makespan. Each slot reconnects as needed when relations span databases. No
explicit signal handler beyond `setup_cancel_handler(NULL)` at line 481;
Ctrl-C sets `CancelRequested` which the main loop polls at line 719 to break.
`ParallelSlotsTerminate` at line 816 does the per-slot disconnect. Partial
output that already reached stdout via `printf` is left in stdio buffers and
should flush on exit. `[ISSUE-correctness: on Ctrl-C, in-flight slot queries are abandoned but their results aren't flushed to stdout (maybe)]`

**6. Integer-overflow on `--startblock` / `--endblock`.**
`strtoul` is used [pg_amcheck.c:408, 417], result is `unsigned long`, range-
checked against `MaxBlockNumber` (`0xFFFFFFFE`). Assignment into the `int64`
field `opts.startblock` is fine even on platforms where `unsigned long` is 32
bits. **Negative values:** `strtoul` accepts a leading `-` and silently
converts to a huge unsigned (POSIX-mandated, surprising). But the resulting
value would exceed `MaxBlockNumber` and be rejected at line 411 / 420.
Verified safe. `[verified-by-code]`

**7. `--install-missing[=schema]`.** The schema name is `PQescapeIdentifier`-
ed at line 556 and inlined into `CREATE EXTENSION IF NOT EXISTS amcheck WITH
SCHEMA %s`. Correctly escaped. `[verified-by-code]` But: pg_amcheck is
willing to issue DDL against an arbitrary database the operator can connect
to. If `--install-missing` is set and the operator is a superuser against
hostile DBs, this **changes a database's catalog state**. Worth noting
that the typical posture of "verifier == read-only" is broken when
`--install-missing` is given.

**8. `progress_report` truncation.** Line 1305: `datname + strlen(datname)
- VERBOSE_DATNAME_LENGTH + 3` — this is the leading-truncation pointer
math. It's correct provided `strlen(datname) > VERBOSE_DATNAME_LENGTH` (the
branch's guard). `[verified-by-code]`

**9. Result rendering uses unescaped `PQgetvalue` content.** As noted in
the output section, the `msg` column and any libpq error strings flow to
stdout/stderr via `printf("%s", …)` with no terminal-escape sanitisation.
Same shape as the rest of the bin/ family — the corpus-level convention
("server text is rendered as-is") applies. `[ISSUE-info-disclosure: corruption messages and libpq errors printed unescaped to stdout/stderr; control-char injection from amcheck.msg column or backend GUC log_min_messages text (low)]`

## Potential issues

- `[ISSUE-state-transition: --all silently skips databases without the amcheck extension installed; exit-0 does not mean "all databases verified" (maybe)]` — pg_amcheck.c:585-594. The warning is logged but the exit code is unaffected. A scheduled cron-based verifier that treats exit-0 as "clean" will miss the case where a new database was added without amcheck installed. Could be argued either way (the alternative — failing — would be obnoxious for `template0`-like edge cases) but it's currently undocumented in help.

- `[ISSUE-state-transition: --no-strict-names downgrades unmatched-pattern errors to warnings (maybe)]` — pg_amcheck.c:207-212, 1719-1724. A typo in `--table public.users` becomes a warning rather than an error, and pg_amcheck exits 0 having checked nothing. Documented in `--help`, but consumers of pg_amcheck-as-a-verifier should be aware.

- `[ISSUE-info-disclosure: server-supplied strings printed unescaped to terminal (low)]` — pg_amcheck.c:1062-1083, 1088-1097, 1156-1166, 1305. `verify_heapam.msg`, `PQerrorMessage` text, and `datname` in the progress meter all flow through `printf` / `fprintf` with no control-character filtering. Severity is low — a corrupted heap that yields attacker-controlled msg strings already implies a much bigger problem — but on shared terminals this is a vector for log-spoofing.

- `[ISSUE-correctness: on Ctrl-C, in-flight slot queries are abandoned without explicit stdout flush (maybe)]` — pg_amcheck.c:719-723, 816. The `break` from the dispatch loop and `ParallelSlotsTerminate` close connections; relying on stdio's atexit flush. If pg_amcheck is killed by `SIGKILL` rather than Ctrl-C, partial results will be lost — but that's expected. With Ctrl-C alone the buffers should drain via normal `exit(1)` path. Worth checking under heavy parallelism.

- `[ISSUE-stale-todo: --install-missing changes catalog state in a "verifier" (maybe)]` — pg_amcheck.c:547-564. Issuing `CREATE EXTENSION` from a tool whose advertised role is "checks objects for corruption" is a surprising posture. Documented in `--help`, but worth flagging because the tool's name does not suggest DDL side-effects.

- `[ISSUE-undocumented-invariant: should_processing_continue treats NULL severity as "stop" (verified)]` — pg_amcheck.c:978-980. `PQresultErrorField(res, PG_DIAG_SEVERITY_NONLOCALIZED)` returning NULL is interpreted as "libpq failure, probably lost connection" → return false → drain the slot. This is correct, but the comment-vs-code dance is subtle: a real `PGRES_FATAL_ERROR` without a severity field is treated identically to a libpq-internal failure. Probably fine, just opaque.

- `[ISSUE-dead-code: `bool		is_btree PG_USED_FOR_ASSERTS_ONLY` and `Assert((is_heap && !is_btree) || …)` (low)]` — pg_amcheck.c:2167, 2208. In non-assert builds, `is_btree` is set but never read. Standard PG idiom, just noting it.

- `[ISSUE-undocumented-invariant: `else if (PQresultStatus(res) != PGRES_TUPLES_OK)` after the `if (PQresultStatus(res) == PGRES_TUPLES_OK)` branch is tautologically true (low)]` — pg_amcheck.c:1086. The `else if` could just be `else`. Harmless, but the explicit re-check suggests an earlier refactor.

- `[ISSUE-correctness: parallel_workers calculation walks the relations list once just to cap at opts.jobs (low)]` — pg_amcheck.c:677-683. Loop counts reltotal and caps parallel_workers in one pass. Correct but unidiomatic — `parallel_workers = (opts.jobs < reltotal) ? opts.jobs : reltotal` after a `reltotal++`-only pass would be clearer. Cosmetic.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_amcheck`](../../../../issues/pg_amcheck.md)
<!-- issues:auto:end -->
