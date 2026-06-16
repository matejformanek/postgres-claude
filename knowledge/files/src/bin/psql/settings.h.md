---
path: src/bin/psql/settings.h
anchor_sha: 4b0bf0788b0
loc: 204
depth: read
---

# settings.h

- **Source path:** `source/src/bin/psql/settings.h`
- **Lines:** 204
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `startup.c` (where `pset` is defined and initialized), `variables.c` (the `vars` field's store), `command.c` (most assign hooks that mutate the non-`vars` fields).

## Purpose

The single-source-of-truth `PsqlSettings` struct definition plus its global instance `pset`. Every behavior knob in psql is either a field of `pset` or a name in `pset.vars`. The struct mixes connection state, output formatting, one-shot per-command flags, and cached copies of variable values that assign hooks have promoted into C scalars for hot-path access. [verified-by-code, settings.h:101-189]

## Compile-time constants

- `DEFAULT_CSV_FIELD_SEP`, `DEFAULT_FIELD_SEP`, `DEFAULT_RECORD_SEP` (14-16) — `\pset` defaults.
- `DEFAULT_EDITOR` (19/22) — `notepad.exe` on Win/Cygwin, `vi` elsewhere. Honors `EDITOR`/`PSQL_EDITOR` env at runtime — that override lives in `command.c::do_edit`. [verified-by-code, settings.h:18-24]
- `DEFAULT_PROMPT1`/`PROMPT2`/`PROMPT3` (26-28) — `"%/%R%x%# "`, `"%/%R%x%# "`, `">> "`.
- `DEFAULT_WATCH_INTERVAL` `"2"` (30) and `DEFAULT_WATCH_INTERVAL_MAX` `1_000_000` (35) — `\watch` polling, capped to stay safe for `setitimer`. [from-comment, settings.h:32-35]

## Enums (state machines tied to variables)

- `PSQL_ECHO` (41) — `none|queries|errors|all`. Driven by `ECHO`.
- `PSQL_ECHO_HIDDEN` (49) — `off|on|noexec`. Driven by `ECHO_HIDDEN`. The `noexec` value is the "show me what `\d` would run, but don't run it" mode.
- `PSQL_ERROR_ROLLBACK` (56) — `off|interactive|on`. Driven by `ON_ERROR_ROLLBACK`.
- `PSQL_COMP_CASE` (63) — tab-completion case behavior.
- `PSQL_SEND_MODE` (71) — picks between simple query and extended-protocol Parse/Bind/Execute, plus pipeline-mode actions. One-shot flag set by `\bind`, `\parse`, `\startpipeline`, etc.
- `HistControl` (86) — bitset: `ignorespace|ignoredups|ignoreboth`. Driven by `HISTCONTROL`. Consumed by `pg_send_history` to filter entries. [verified-by-code, input.c:150-153]
- `trivalue` (94) — `default|no|yes`. Used for `--no-password` etc.

[verified-by-code, settings.h:41-99]

## `PsqlSettings` field groups

**Connection / session state**
- `db` (103) — `PGconn *`. **Holds the live connection — including the password if libpq cached it internally.** [verified-by-code, settings.h:103]
- `encoding` (104) — `client_encoding`.
- `sversion` (141) — backend server version.
- `dead_conn` (158) — stashed `PGconn` after connection failure, kept ONLY for parameter extraction at `\connect` retry. The comment explicitly forbids any other use. [from-comment, settings.h:153-158]

**Output streams**
- `queryFout`/`queryFoutPipe` (105-106) — where `SELECT` results go; pipe flag means use `pclose`. Set by `\o`.
- `copyStream` (108) — for `\copy`.
- `logfile` (149) — `\o`-independent session log.
- `last_error_result` (110) — most recent error `PGresult`.

**Print options**
- `popt` (112) — the active `printQueryOpt`. Big nested struct from `fe_utils/print.h`.

**One-shot flags** (cleared after a single statement executes)
- `gfname`, `gsavepopt`, `gset_prefix`, `gdesc_flag`, `gexec_flag` (114-119) — `\g`/`\gset`/`\gdesc`/`\gexec` payloads.
- `send_mode`, `bind_nparams`, `bind_params`, `stmtName` (120-125) — extended-protocol payload for `\bind`/`\parse`/`\bind_named`.
- `piped_commands`, `piped_syncs`, `available_results`, `requested_results` (126-131) — pipeline accounting.
- `crosstab_flag`, `ctv_args[4]` (132-133) — `\crosstabview` arguments.

**I/O state**
- `notty` (135) — set at startup if stdin or stdout is not a tty.
- `getPassword` (137) — trivalue. `TRI_YES` means `-W` was given.
- `cur_cmd_source`, `cur_cmd_interactive` (138-140) — the current `\i`-style input stack frame.
- `progname`, `inputfile`, `lineno`, `stmt_lineno` (142-145) — error-reporting context.
- `timing` (147) — `\timing on`.

**The variable store**
- `vars` (151) — `VariableSpace`. Every `\set` lives here.

**Assign-hook-cached scalars** (162-186) — `autocommit`, `on_error_stop`, `quiet`, `singleline`, `singlestep`, `hide_compression`, `hide_tableam`, `fetch_count`, `histsize`, `ignoreeof`, `watch_interval`, `echo`, `echo_hidden`, `on_error_rollback`, `comp_case`, `histcontrol`, `prompt1`, `prompt2`, `prompt3`, `verbosity`, `show_all_results`, `show_context`. The struct comment at 160-163 says: "set by assign hooks ... should not be set directly except by those hook functions." [from-comment, settings.h:160-163]

## Exit codes

`EXIT_BADCONN = 2`, `EXIT_USER = 3` (200, 202). Standard `EXIT_SUCCESS`/`EXIT_FAILURE` if not already defined.

## Phase D notes

- **Credential-bearing field: `pset.db`.** A `PGconn` may hold a cached password (depending on libpq version + how the connection was made — `PQconninfo`-style URIs with `password=` get persisted in the internal conn struct, `~/.pgpass` lookups stash a copy). Any code that serializes or prints `pset.db`'s state must use libpq's redaction helpers, not raw struct walks. There's no plaintext password field on `PsqlSettings` itself. [inferred, settings.h:103] [ISSUE-info-leak: `pset.db` indirectly contains password material; any `\!` shell-out, core dump, or crash report could expose it (maybe)]
- **`pset.dead_conn` retention.** Comment says only `\connect` parameter extraction is permitted. A future patch that adds e.g. a `\diag dead_conn` debug command could inadvertently leak the credentials from a failed connection. [from-comment, settings.h:153-158] [ISSUE-info-leak: dead_conn retains credentials of failed connection (low)]
- **`pset.ctv_args[4]`** is set from raw user input via `\crosstabview` argument parsing and consumed by `crosstabview.c::indexOfColumn`. The `dequote_downcase_identifier` step there handles quoting. [verified-by-code, crosstabview.c:135-202, 657] [no concern]
- **Most "real" settings live in TWO places.** E.g. `AUTOCOMMIT` is in both `pset.vars` (as a string) and `pset.autocommit` (as a `bool`). The bool is the canonical one for fast lookups; the string is what `\echo :AUTOCOMMIT` shows. The assign hook keeps them in sync. If a future direct write to `pset.autocommit` is added (skipping the hook), the two diverge. [from-comment, settings.h:160-163] [ISSUE-correctness: direct writes to hook-managed fields bypass the variable store (low)]
- **`PSQL_SEND_MODE` one-shot.** Each meta-command that sets a non-default value MUST clear it after the next query executes, or the next plain query will be run via extended-protocol with stale bind params. The discipline is in `command.c`/`common.c`; this header just declares the enum. [inferred, settings.h:71-84] [ISSUE-correctness: one-shot flag leakage between commands (maybe)]
- **No max length on `prompt1`/`2`/`3`.** They're `const char *` pointers into the variable store's string. `prompt.c::get_prompt` caps output at 256 bytes via local buf, so a multi-megabyte PROMPT setting just gets truncated rather than crashing. [verified-by-code, prompt.c:73-74, 104] [no concern]

## Confidence tag tally
`[verified-by-code]=10 [from-comment]=5 [inferred]=2 [no concern]=2 [ISSUE]=4`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->
