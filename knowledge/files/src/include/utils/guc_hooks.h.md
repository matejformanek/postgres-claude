# `utils/guc_hooks.h` — central declarations of per-variable GUC hooks

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/guc_hooks.h`)

## Role

Single header collecting `extern` declarations for every `check_xxx` /
`assign_xxx` / `show_xxx` callback referenced by the core GUC tables. The
hook implementations live in their natural home modules
(`postmaster.c`, `pg_locale.c`, `varsup.c`, `bgwriter.c`, `walsender.c`,
`xlog.c`, `tcop/*`, …), but pulling all the externs here avoids cluttering
`guc_tables.c` with includes from every subsystem.

## Public API

Every declaration matches one of the typedefs in `guc.h:183-195`:

- `bool check_xxx(<T> *newval, void **extra, GucSource source)` — return
  `false` to refuse the value; may set `*newval` to a normalised form;
  may allocate `*extra` with `guc_malloc` for the assign hook.
- `void assign_xxx(<T> newval, void *extra)` — must not fail; runs after
  the value has been chosen.
- `const char *show_xxx(void)` — returns a display string when the raw
  value isn't quite right (e.g. `show_timezone` returns the IANA name).

Across `source/src/include/utils/guc_hooks.h:28-186` (~165 entries),
grouped by GUC name. Highlights touching trust boundaries:

- `check_application_name` / `assign_application_name` — `:28-30`. The
  client-controlled GUC; assign hook can update PS title.
- `check_canonical_path` — `:40`. Normalises file paths; used by several
  filesystem GUCs.
- `check_client_encoding` / `assign_client_encoding` — `:44-45`.
- `check_cluster_name` — `:46`. Used in pg_stat_activity and PS title.
- `check_log_connections` / `assign_log_connections` — `:54-55`.
- `check_default_table_access_method` — `:56-57`. Validates an AM name.
- `check_default_tablespace` — `:58-59`. Tablespace name → OID.
- `check_default_text_search_config` — `:60`. ts_config name → OID.
- `check_locale_messages/monetary/numeric/time` — `:69-76`.
- `check_log_destination` — `:77`. Validates list of `stderr`/`csvlog`/`syslog`/`jsonlog`.
- `check_max_stack_depth` — `:89`. Validates against rlimit.
- `check_role` / `assign_role` / `show_role` — `:122-124`. The SET ROLE
  validator — load-bearing for security.
- `check_restrict_nonsystem_relation_kind` — `:125-126`. CVE-related.
- `check_search_path` / `assign_search_path` — `:128-129`. SET search_path.
- `check_session_authorization` / `assign_session_authorization` —
  `:131-132`. SET SESSION AUTHORIZATION.
- `check_ssl` / `check_ssl_sni` — `:135-136`.
- `check_synchronous_standby_names` / `assign_synchronous_standby_names`
  — `:142-144`.
- `check_timezone` / `assign_timezone` / `show_timezone` — `:160-162`.
- `check_timezone_abbreviations` / `assign_timezone_abbreviations` —
  `:163-165`.
- `check_wal_consistency_checking` — `:176-178`.
- `check_log_min_messages` / `assign_log_min_messages` — `:184-185`.

## Invariants

- Every `extern` in this file is the canonical declaration; the implementing
  .c must match exactly. `guc_tables.c` references these via function name.
  [from-comment, `:6-9`]
- Declarations are required to be kept in alphabetical order by GUC name.
  [from-comment, `:25`]
- `check_*` returning `false` MUST NOT have caused a `*extra` leak.
  Callers `set_config_option` will free `*extra` only on success.
  [inferred from typedef semantics in guc.h]

## Notable internals

This is a flat declaration file — no logic. The interesting fact is what's
absent: there's no declaration for `check_<extension_guc>` because extension
GUCs register their hooks directly through `DefineCustomXxxVariable`.

## Trust-boundary / Phase D surface

- **Every `check_*` here is a validation choke point.** If any one of them
  has a bug (NAME→OID race, length check, encoding validation, etc.) the
  attacker controls the post-SET state. The header gives no quick way to
  audit which ones touch the filesystem, the catalog, or the network. A
  flag in `guc_tables.c` would help. [ISSUE-audit-gap: no taxonomy of
  check hooks by trust surface; auditing requires opening 50 .c files
  (likely)]
- `check_role` / `check_session_authorization` (`:122,131`) are the
  identity-switching choke points. A check_role bug = privilege
  escalation. [ISSUE-security: check_role / check_session_authorization
  are critical-trust check hooks; no header documentation flags them as
  such (likely)]
- `check_search_path` (`:128`) only syntactically validates the list;
  schema EXISTENCE is checked at lookup time (lazy). This means a
  search_path SET succeeds even pointing at a dropped schema — common
  bug source. [ISSUE-correctness: check_search_path does syntactic-only
  validation; schema existence is lazy (likely)]
- `check_default_table_access_method` (`:56`) validates the AM name
  string but defers OID lookup; in `PGC_S_TEST` (e.g. ALTER DATABASE
  SET) it deliberately doesn't error on missing AM. An attacker who
  controls the AM name in a future role/database SET clause can pin to
  an AM that gets dropped/recreated. [ISSUE-correctness: AM/tablespace/
  ts_config check hooks are PGC_S_TEST-forgiving — NAME-vs-OID echo of
  A3/A6+ cluster (likely)]
- `check_application_name` (`:28`) sets a value that ends up in
  `pg_stat_activity.application_name` AND in `update_process_title` —
  attacker-controlled, free-form text appearing in admin-visible
  surfaces. Documented; the question is what truncation / escaping
  happens. [ISSUE-audit-gap: application_name flows to logs and
  pg_stat_activity without sanitisation in this header (nit)]
- `check_backtrace_functions` (`:36-38`) accepts a comma-separated list
  of function names; the assign hook installs the list and the elog
  path consults it. Header gives no docs on size limit. [ISSUE-resource:
  backtrace_functions list size uncapped in header docs (nit)]
- `check_wal_consistency_checking` (`:176-178`) — invalid rmgr names
  in the GUC are caught here; a future custom rmgr that fails to register
  could silently drop wal-consistency checks. [ISSUE-correctness: WAL
  consistency-check GUC names are validated only against built-in rmgrs;
  custom rmgrs treated separately (maybe)]

## Cross-refs

- `knowledge/files/src/include/utils/guc.h.md` — typedefs the hooks match.
- `knowledge/files/src/include/utils/guc_tables.h.md` — `config_generic`
  carries the function pointers.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-audit-gap: no per-hook taxonomy of trust surface; auditing
   check hooks requires reading every .c (likely)] —
   `source/src/include/utils/guc_hooks.h:28-186`.
2. [ISSUE-security: `check_role` / `check_session_authorization` are
   critical-trust hooks; header doesn't flag them (likely)] —
   `source/src/include/utils/guc_hooks.h:122,131`.
3. [ISSUE-correctness: `check_search_path` is syntactic-only; schema
   existence is lazy (likely)] —
   `source/src/include/utils/guc_hooks.h:128`.
4. [ISSUE-correctness: AM/tablespace/ts_config check hooks are
   PGC_S_TEST-forgiving — NAME-vs-OID race echo (likely)] —
   `source/src/include/utils/guc_hooks.h:56-60`.
5. [ISSUE-audit-gap: `application_name` flows to logs / pg_stat_activity
   without sanitisation visible at header level (nit)] —
   `source/src/include/utils/guc_hooks.h:28`.
6. [ISSUE-resource: `backtrace_functions` list size uncapped in header
   docs (nit)] — `source/src/include/utils/guc_hooks.h:36`.
7. [ISSUE-correctness: `check_wal_consistency_checking` validates only
   built-in rmgrs (maybe)] —
   `source/src/include/utils/guc_hooks.h:176`.
