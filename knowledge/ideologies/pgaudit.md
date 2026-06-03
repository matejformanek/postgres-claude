# pgAudit — audit logging by tapping the permission-check + object-access hooks

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgaudit/pgaudit` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-03 (see Sources footer).

## Domain & purpose

pgAudit produces detailed, auditor-grade session and object audit logs. Its
thesis (`README.md:11-39`) `[from-README]` is that `log_statement = all`
records *what the user requested* but not *what actually happened*: a
`DO $$ ... EXECUTE 'CREATE TABLE import'||'ant_table' ... $$` block hides the
real DDL from a `grep`, whereas pgAudit emits a structured
`AUDIT: SESSION,33,2,DDL,CREATE TABLE,TABLE,public.important_table,...` line
with command type, object type, and fully-qualified name. It is the worked
answer to: *how do you observe the post-parse, post-rewrite truth of every
statement — including substatements and the relations each touches — from an
extension?* The answer is to hook the **executor's permission-check** and the
**object-access** callbacks, not the statement logger.

## How it hooks into PG

pgAudit **requires** `shared_preload_libraries` and errors hard if loaded any
other way — `_PG_init` checks `process_shared_preload_libraries_in_progress`
and `ereport(ERROR, ...)` otherwise (`pgaudit.c:2117-2120`)
`[verified-by-code]`. It uses the modern `PG_MODULE_MAGIC_EXT(.name="pgaudit",
.version="18.0")` (`pgaudit.c:45`). `_PG_init` is idempotent via a `static
bool inited` guard (`pgaudit.c:2112-2115`).

It chains **five** hooks, saving the prior pointer each time (`pgaudit.c:2309-2322`):

| Hook | Audit role |
|---|---|
| `ExecutorStart_hook` | Stand up the per-statement audit-event stack item before execution; the stack item is needed by the CheckPerms hook fired *during* `standard_ExecutorStart` (`pgaudit.c:1415-1476`). |
| **`ExecutorCheckPerms_hook`** | The load-bearing one: PG calls this with the statement's `rangeTabls` + `permInfos` so the backend can verify privileges — pgAudit reuses that exact callback to enumerate every relation a SELECT/DML touches and decide what to log (`pgaudit.c:1493-1542`). |
| `ProcessUtility_hook` | Session auditing for DDL and utility commands; logs `DO` blocks before chaining (`pgaudit.c:1595-1692`). |
| `object_access_hook` | Function-execute auditing: on `OAT_FUNCTION_EXECUTE` it logs the function call with a fully-qualified name (`pgaudit.c:1722-1735`). |
| `ExecutorEnd_hook` | Finalize per-statement state and capture row counts (`pgaudit.c:1553-1588`). |

Plus **two SQL event triggers** registered by the install script
(`pgaudit_ddl_command_end` on `ddl_command_end`, and an `sql_drop` handler)
that call back into C to deparse object identities (`pgaudit.c:1747-1804`).

Nine `PGC_SUSET` GUCs, all `GUC_NOT_IN_SAMPLE`: `pgaudit.log` (class bitmap
with `+`/`-` syntax and check/assign hooks), `pgaudit.log_catalog`,
`pgaudit.log_client`, `pgaudit.log_level`, `pgaudit.log_parameter`,
`pgaudit.log_parameter_max_size`, `pgaudit.log_relation`, `pgaudit.log_rows`,
… `pgaudit.role` (`pgaudit.c:2123-2303`). Cross-ref
`[[knowledge/idioms/guc-variables]]`.

## Where it diverges from core idioms

### 1. It repurposes `ExecutorCheckPerms_hook` — a *security* callback — as an audit tap

The single most idiom-divergent choice. `ExecutorCheckPerms_hook` exists so an
extension can *grant or deny* access (return `false` → permission denied); core
calls it once per statement with the full range-table + per-relation
`RTEPermissionInfo`. pgAudit hooks it not to make a decision but to **read** the
list of relations and their requested permission bits (`pgaudit.c:1493-1542`),
because this is the one place that has the post-rewrite, fully-resolved set of
relations *with* the SELECT/INSERT/UPDATE/DELETE intent attached — exactly what
object audit logging needs. It still honors the chain: it calls
`next_ExecutorCheckPerms_hook` and respects a `false` return
(`pgaudit.c:1541-1542`). Using a permission-enforcement hook as an
introspection point is the inversion that makes pgAudit's per-relation logging
possible without re-parsing. Cross-ref `[[knowledge/architecture/executor]]`,
`[[knowledge/subsystems/tcop]]`.

### 2. Object auditing is configured through the GRANT system, not a config table

pgAudit does not keep its own "which tables to audit" catalog. Instead
`pgaudit.role` names a master role, and *a relation is audited when that role
holds the matching privilege on it* (`README.md:251-262`) `[from-README]`. To
audit SELECT+DELETE on `account`, you `GRANT select, delete ON account TO
auditor`. The CheckPerms hook then compares the statement's requested
permissions against what the audit role has been granted on each relation
(`pgaudit.c:1493-1542`). This deliberately overloads core's privilege system as
the audit-policy store — column-level grants even give column-granularity audit
scope (`README.md:264-266`). No extension catalog, no `pg_dist_*`-style mirror:
the policy *is* the grant graph. Cross-ref
`[[knowledge/idioms/catalog-conventions]]` (the catalog it chose *not* to build).

### 3. A per-statement audit-event *stack*, because statements nest

Core logs one line per statement. pgAudit must handle nesting: a `DO` block runs
a function that runs DDL; a query calls a function that runs a query. It keeps
`auditEventStack` — a push/pop stack of `AuditEventStackItem`
(`pgaudit.c:245-249`, guarded throughout, e.g. `pgaudit.c:1730`,
`:1763`) — so each substatement gets its own numbered audit entry
(`SESSION,33,1,...` then `SESSION,33,2,...` in the README example,
`README.md:31-36`). The `ExecutorStart` hook pushes; `ExecutorEnd` pops. This
explicit substatement model is something core's statement logger has no notion
of. Cross-ref `[[knowledge/idioms/memory-contexts]]` (stack items are
context-scoped).

### 4. Event trigger + SPI + `pg_event_trigger_ddl_commands()` to get deparsed object identities

For DDL, the CheckPerms hook is no help (DDL doesn't go through the executor's
relation permission path), so pgAudit registers a `ddl_command_end` event
trigger whose C body (`pgaudit_ddl_command_end`, `pgaudit.c:1747-1804`) opens
SPI and runs `SELECT upper(object_type), object_identity,
upper(command_tag) FROM pg_catalog.pg_event_trigger_ddl_commands()` to obtain
the *server-deparsed*, fully-qualified identity of every object the DDL touched
(`pgaudit.c:1792-1804`). It marks `internalStatement = true` so this internal
SPI query isn't itself audited (`pgaudit.c:1768`), and runs in a private
`AllocSetContext` (`pgaudit.c:1775-1779`). Reaching back into core through SQL
event triggers + SPI from a C extension — to leverage core's own DDL deparse —
is well outside the plain-hook idiom. Cross-ref `[[knowledge/idioms/spi]]`,
`[[knowledge/subsystems/tcop]]` (event triggers).

### 5. `log_level` carries a documented security caveat in its own help text

`pgaudit.log_level` lets the audit line be emitted at a chosen elevation, but
its description warns it "is not intended to be used in a production
environment as it may leak which statements are being logged to the user"
(`pgaudit.c:2175-2180`). Likewise `pgaudit.log_client` is documented as
"should generally be left disabled" (`pgaudit.c:2160-2162`). Shipping the
threat model *inside* the GUC long-description — rather than only in docs — is a
notable discipline for a security-sensitive extension.

## Notable design decisions (cited)

- **`pgaudit.log` is a subtractive class bitmap.** Comma-separated classes
  (READ, WRITE, FUNCTION, ROLE, DDL, MISC, …) with `-` to subtract, parsed by
  `check_pgaudit_log`/`assign_pgaudit_log` into `auditLogBitmap`
  (`pgaudit.c:2123-2138`). The hooks gate on bits, e.g. `LOG_FUNCTION`
  (`pgaudit.c:1729`), `LOG_DDL`/`LOG_ROLE` (`pgaudit.c:1759`).
- **`log_catalog` defaults true but exists to cut noise.** Disabling it stops
  auditing statements where *all* relations are in `pg_catalog`, taming psql /
  pgAdmin catalog chatter (`pgaudit.c:2141-2154`).
- **Bounded parameter logging.** `log_parameter_max_size` (0 = unbounded, max
  `(1<<30)-1`) replaces oversized variable-length parameters with a placeholder
  so a single huge bind value can't blow up the log (`pgaudit.c:2206-2223`).
- **Honest about cost.** The README repeatedly warns audit logging "can
  generate an enormous volume" and to "assess the performance impact"
  (`README.md:43-47`) — and steers heavy cases to object auditing precisely
  because the CheckPerms-hook path lets it log per-relation rather than
  per-statement (`README.md:47`).
- **EXEC_BACKEND-aware init log.** The "extension initialized" line is `LOG`
  normally but `DEBUG1` under `EXEC_BACKEND` (Windows / forced-exec), since
  every backend re-runs `_PG_init` there (`pgaudit.c:2324-2329`).

## Links into corpus

- `[[knowledge/architecture/executor]]` — `ExecutorStart`/`CheckPerms`/`End`
  hook points; the range-table + permission-info pgAudit reads.
- `[[knowledge/subsystems/tcop]]` — `ProcessUtility_hook` for DDL/utility and
  the event-trigger machinery pgAudit fires SPI from.
- `[[knowledge/idioms/spi]]` — the `pg_event_trigger_ddl_commands()` SPI query
  used to deparse DDL object identities.
- `[[knowledge/idioms/catalog-conventions]]` — the privilege/GRANT system
  pgAudit overloads as its object-audit policy store *instead of* a catalog.
- `[[knowledge/idioms/guc-variables]]` — nine `PGC_SUSET` GUCs with
  check/assign hooks and the subtractive-bitmap class parser.
- `[[knowledge/idioms/memory-contexts]]` — per-statement audit-stack item
  contexts + the private DDL-deparse context.
- `[[knowledge/idioms/error-handling]]` — the `ereport(ERROR)` preload guard
  and the `LOG`/`DEBUG1` EXEC_BACKEND split.
- `.claude/skills/extension-development/SKILL.md` — five-hook chaining,
  `shared_preload_libraries` enforcement, `PG_MODULE_MAGIC_EXT`, GUC patterns.

## Sources

Fetched 2026-06-03 (branch `main`; queue manifest said `master`, the repo's
default branch is `main` — fetched accordingly):

- `https://raw.githubusercontent.com/pgaudit/pgaudit/main/README.md`
  @ 2026-06-03T23:08Z → HTTP 200 (376 lines).
- `https://raw.githubusercontent.com/pgaudit/pgaudit/main/pgaudit.c`
  @ 2026-06-03T23:08Z → HTTP 200 (2332 lines).
- `https://raw.githubusercontent.com/pgaudit/pgaudit/main/pgaudit.control`
  @ 2026-06-03T23:08Z → HTTP 200 (5 lines).
- Tree listing
  `https://api.github.com/repos/pgaudit/pgaudit/git/trees/main?recursive=1`
  @ 2026-06-03T23:08Z → HTTP 200 (21 entries).

All `.c`/control cites are `[verified-by-code]` against the fetched
`pgaudit.c` (hook installs, the CheckPerms repurposing, the event-trigger SPI
deparse, GUC definitions). The auditor-rationale and object-audit-via-GRANT
narrative is `[from-README]`. The audit-line *format* details
(`AUDIT: SESSION,...`) are quoted from the README's worked example, not
re-derived from the formatting code in `pgaudit.c` (which was present in the
fetched file but not exhaustively traced).
</content>
