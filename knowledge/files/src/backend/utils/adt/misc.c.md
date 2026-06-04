# src/backend/utils/adt/misc.c

## Purpose

Grab bag of small-to-medium "miscellaneous" SQL functions that don't
warrant their own file: null-count helpers, `current_database`,
`current_query`, `pg_tablespace_databases`, `pg_tablespace_location`,
`pg_sleep`, `pg_get_keywords`, `pg_get_catalog_foreign_keys`, `pg_typeof`,
`pg_basetype`, `pg_collation_for`, `pg_relation_is_updatable`,
`pg_column_is_updatable`, `pg_input_is_valid` / `pg_input_error_info`,
`parse_ident`, `pg_current_logfile`, `pg_get_replica_identity_index`,
`any_value_transfn`. Note: `pg_terminate_backend` / `pg_cancel_backend`
live in `signalfuncs.c`, **not here** — the orchestrator's notes call out
misc.c as the home for those, but as of pin 4b0bf078 they are split.

## Role in PG

Each function is wired through `pg_proc.dat`. Mostly low-privilege
PUBLIC-callable utilities; the privileged stuff is now elsewhere.

## Key functions

Null helpers:
- `pg_num_nulls(VARIADIC any)` / `pg_num_nonnulls(VARIADIC any)`
  (`misc.c:163-193`) — walk fcinfo args counting `PG_ARGISNULL`.
- `pg_error_on_null(any)` (`:195-?`) — raise if NULL else passthrough.

Context probes:
- `current_database()` (`:210-219`) — `get_database_name(MyDatabaseId)`.
- `current_query()` (`:227-235`) — returns `debug_query_string` or NULL.
  No privilege gate.

Tablespace introspection:
- `pg_tablespace_databases(tspOid)` (`:239-310`) — SRF returning DB OIDs
  found under that tablespace's version dir. Hard-codes "base" for
  default, `PG_TBLSPC_DIR/<oid>/<verdir>` for others. Skips empty
  subdirs (`directory_is_empty`). **No ACL gate** — discoverable by
  anyone.
- `pg_tablespace_location(tspOid)` (`:316-326`) — wraps
  `get_tablespace_location`. **No ACL gate** here; the underlying
  `get_tablespace_location` may have one.

Time / catalog:
- `pg_sleep(float8)` (`:332-?`) — converts seconds to int64 µs, caps at
  `PG_INT64_MAX/2` (~150 K years), uses `WaitLatch` in ≤10 minute
  chunks. Treats NaN and ≤0 as "no wait" (no error). `endtime` is
  computed once so SIGHUP-driven wakes don't shorten the sleep
  (`:357-361`).
- `pg_get_keywords()` (`:391-?`) — SRF dumping `ScanKeywords[]` with
  category and barelabel info.
- `pg_get_catalog_foreign_keys()` (`:468-?`) — synthetic FK relationships
  among system catalogs (not real FKs, hard-coded knowledge).

Type / collation:
- `pg_typeof(any)` (`:537-?`) — `fcinfo->flinfo->fn_expr` →
  `exprType()`.
- `pg_basetype(any)` (`:555-?`) — unwraps domain to base type.
- `pg_collation_for(any)` (`:592-?`) — `exprCollation()`.

Updatability:
- `pg_relation_is_updatable(reloid, include_triggers)` (`:620-?`).
- `pg_column_is_updatable(reloid, attnum, include_triggers)` (`:637-?`).

Input validation (PG 16+ soft-error surface):
- `pg_input_is_valid(textval, typename)` (`:668-?`) — calls
  `pg_input_is_valid_common` with ErrorSaveContext.
- `pg_input_error_info(textval, typename)` (`:688-?`) — returns
  message + detail + hint + sqlstate.

Identifier parsing:
- `parse_ident(qualname, strict)` (`:833-965`) — splits a
  dotted-quoted SQL identifier string into a `text[]`.
  - `is_ident_start` / `is_ident_cont` (`:800-826`) must match
    `scan.l`'s `{ident_cont}` class — comment is explicit
    (`:815-816`).
  - Handles doubled "" inside "" by memmove-shift (`:874-876`).
  - Does NOT truncate to NAMEDATALEN — the comment defends this by
    saying users wanting truncation can cast to `name[]`
    (`:904-909`).
  - Calls `downcase_identifier(curname, len, false, false)` for
    unquoted segments (`:910`) — important: respects the database
    encoding's case folding.

Log file:
- `pg_current_logfile([fmt])` (`:972-?`) — reads
  `LOG_METAINFO_DATAFILE` (i.e. `current_logfiles` in pgdata),
  validates `fmt ∈ {stderr, csvlog, jsonlog}`, returns the matching
  log filename.

Replication:
- `pg_get_replica_identity_index(reloid)` (`:1073-1088`) —
  `AccessShareLock` on rel, `RelationGetReplicaIndex`, NULL if none.

Aggregate:
- `any_value_transfn(state, value)` (`:1093-1097`) — just returns
  state (ANY_VALUE picks "some" non-null arbitrarily).

## State / globals

None.

## Phase D notes

- **The orchestrator's brief assumed `pg_terminate_backend` /
  `pg_cancel_backend` / `set_config` / `current_setting` live in
  misc.c.** As of pin `4b0bf078` they do NOT:
  - `pg_terminate_backend`, `pg_cancel_backend`, `pg_reload_conf`,
    `pg_rotate_logfile`, `pg_promote` → `signalfuncs.c`.
  - `set_config`, `current_setting`, `pg_show_all_settings` →
    `guc_funcs.c`.
  - `pg_log_backend_memory_contexts` → `mcxtfuncs.c`.
- So the privileged-signal surface this batch was supposed to audit
  via misc.c is mostly elsewhere. The orchestrator question 5 (can a
  role kill another role's backend?) is answered by `signalfuncs.c`,
  not this file — see that doc when it lands. The answer there is:
  `pg_cancel_backend` requires same role membership OR
  `pg_signal_backend` role; `pg_terminate_backend` adds the further
  rule that you can't terminate a superuser unless you are one.
- **`current_query()`** returns `debug_query_string` to PUBLIC. In a
  pooler with many session-resetting connections, debug_query_string
  may leak the *previous* statement text to an unprivileged session —
  guaranteed reset at top of each statement (`exec_simple_query` sets
  it before processing), so the race window is tiny. [verified-by-code
  upstream, not in this file]
- **`pg_tablespace_databases` / `pg_tablespace_location`** — no ACL
  check. Information disclosure: any role learns which DBs occupy
  which tablespace and where the tablespace is symlinked. Mild.
- **`pg_sleep`** has no rate limit, no max duration cap that an admin
  can enforce. Idle-in-transaction risk: `SELECT pg_sleep(86400)`
  inside a long transaction holds locks/snapshots for a day. Mitigated
  by `idle_in_transaction_session_timeout` only if the surrounding
  txn is otherwise idle — but pg_sleep keeps the backend "active".
- **`pg_current_logfile`** — reads `current_logfiles` in pgdata.
  Default ACL (per pg_proc.dat) is `{=r/POSTGRES,POSTGRES=...}` —
  grants `pg_monitor` role. Anyone with that role sees the log path.

## Potential issues

- [ISSUE-info-disclosure: `pg_tablespace_databases` / `…_location`
  are PUBLIC and reveal cluster filesystem layout (low)]
- [ISSUE-dos: unbounded `pg_sleep` keeps backend "active",
  bypassing `idle_*_timeout` (low — well known)]
- [ISSUE-correctness: `pg_tablespace_databases` skips entries whose
  `atooid(de->d_name) == 0` (`:288-290`), which catches `.` and `..`
  but also any numeric 0 entry (which wouldn't exist as a valid DB
  OID). Comment self-flags as "awfully weak". (low)]
- [ISSUE-info-disclosure: `current_query()` exposes
  `debug_query_string` to any caller; in connection-pooled
  setups, edge cases around `RESET ALL` / pool handoff could
  leak prior session's last query (low — race is tiny)]
- [ISSUE-undocumented-invariant: `parse_ident` does NOT truncate to
  NAMEDATALEN by design (`:904-909`). Callers using the result as
  pg_class names will silently fail to find the truncated form —
  comment says cast to `name[]` to truncate. Footgun (low)]
- [ISSUE-stale-todo: comment on `current_query()` (`:225`) says
  "We might want to use ActivePortal->sourceText someday." Long-
  standing TODO. (low)]
