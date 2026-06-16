---
path: src/bin/psql/startup.c
anchor_sha: 4b0bf0788b0
loc: 1296
depth: deep
---

# startup.c

- **Source path:** `source/src/bin/psql/startup.c`
- **Lines:** 1296
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `command.c::do_connect` (the `\connect` equivalent of main's connect loop), `mainloop.c::MainLoop`, `help.c`.

## Purpose

`main()`, option parsing, initial connection, `.psqlrc` lookup, and the variable hook table that translates `\set FOO bar` into typed updates of fields in the global `pset`. [verified-by-code, startup.c:1-1296]

## Role in psql

Top of the call graph: `main` initialises `pset`, parses options into a `struct adhoc_opts`, opens the libpq connection (with a password-retry loop), installs SIGINT handling, runs `.psqlrc`, then dispatches either to `MainLoop(stdin)` (interactive) or to the action list (`-c query`, `-c \cmd`, `-f file`) — possibly wrapped in a `BEGIN`/`COMMIT` for `-1`.

## Key functions

### `main` (startup.c:127)

Sequence:

1. **Logging init** (startup.c:134-137). `pg_logging_set_pre_callback(log_pre_callback)` ensures any pending `pset.queryFout` data is flushed before a log line is printed. `log_locus_callback` makes `pg_log_error` annotate with the current `pset.inputfile:lineno` when set. [verified-by-code, startup.c:92-112]
2. **`-?` / `--version` short-circuit** (startup.c:139-151).
3. **Initialise `pset` defaults** (startup.c:153-191). `pset.encoding = PQenv2encoding()`. `pset.notty = (!isatty(stdin) || !isatty(stdout))`.
4. **`EstablishVariableSpace()`** (startup.c:191) — creates the variable space and installs hooks for ~22 special variables (`AUTOCOMMIT`, `ON_ERROR_STOP`, `QUIET`, `FETCH_COUNT`, `HISTFILE`, `HISTSIZE`, `IGNOREEOF`, `ECHO`, `ECHO_HIDDEN`, `ON_ERROR_ROLLBACK`, `COMP_KEYWORD_CASE`, `HISTCONTROL`, `PROMPT[1-3]`, `VERBOSITY`, `SHOW_ALL_RESULTS`, `SHOW_CONTEXT`, `HIDE_TOAST_COMPRESSION`, `HIDE_TABLEAM`, `WATCH_INTERVAL`, `SINGLELINE`, `SINGLESTEP`). [verified-by-code, startup.c:1222-1296]
5. **Pre-set VERSION variables** (startup.c:193-211) — `VERSION`, `VERSION_NAME`, `VERSION_NUM`, `LAST_ERROR_MESSAGE=""`, `LAST_ERROR_SQLSTATE="00000"`, plus pipeline counters.
6. **`parse_psql_options`** (startup.c:214) — see below.
7. **Connection retry loop** (startup.c:252-306). `PARAMS_ARRAY_SIZE = 8` keyword/value slots: `host port user password dbname fallback_application_name client_encoding NULL`. Calls `PQconnectdbParams`; on `CONNECTION_BAD && PQconnectionNeedsPassword` re-prompt with `simple_prompt("Password for user %s: ", false)`. The "false" means don't echo. [verified-by-code, startup.c:253-306]
8. **`psql_setup_cancel_handler()`** (startup.c:315).
9. **Empty SIGCHLD/SIGALRM handlers** on non-Windows (startup.c:317-327) — needed so `sigwait` in `do_watch` actually receives them on some platforms.
10. **`PQsetNoticeProcessor`** (startup.c:329) — route INFO/WARNING/NOTICE through `pg_log_info`.
11. **`SyncVariables()`** (startup.c:334) — pull connection state into psql vars.
12. **`-l` shortcut** (startup.c:336-346) — `listAllDbs` and exit.
13. **Logfile** (startup.c:348-354) — `fopen(filename, "a")`.
14. **`.psqlrc`** unless `-X` (startup.c:356-357).
15. **Actions or MainLoop** (startup.c:363-472).
16. **Cleanup** (startup.c:474-483) — close logfile, `PQfinish` both `pset.db` and `pset.dead_conn`.

### `parse_psql_options(argc, argv, options)` (startup.c:491)

`getopt_long` driven; ~40 option letters. Sets fields in `options` (`struct adhoc_opts`) or `pset.popt.topt` directly or `SetVariable`s into `pset.vars`. Note `-c` distinguishes between `-c \foo` (action `ACT_SINGLE_SLASH`) and `-c "SELECT ..."` (action `ACT_SINGLE_QUERY`) by checking `optarg[0] == '\\'` (startup.c:555-562). After options, trailing positional args are taken as `dbname` then `username` (startup.c:737-748).

### `process_psqlrc(argv0)` and `process_psqlrc_file` (startup.c:782, 816)

Two-tier lookup:
- `find_my_exec(argv0, ...)` to derive sysconfdir, then `${sysconfdir}/psqlrc` (system-wide). [verified-by-code, startup.c:791-797]
- `$PSQLRC` if set and non-empty (with `expand_tilde`). [verified-by-code, startup.c:799-806]
- Otherwise `${HOME}/.psqlrc`. [verified-by-code, startup.c:807-811]

For each, also try `<file>-<PG_VERSION>` then `<file>-<PG_MAJORVERSION>` then `<file>` (startup.c:826-835). The version-suffixed variants take precedence. `access(file, R_OK)` is the only permission check — `process_file` ultimately just `fopen`s it.

### Substitute / assign hooks (startup.c:858-1220)

For each tracked variable, a pair: a *substitute hook* that normalises the new value (e.g. `bool_substitute_hook` turns `NULL` into `"off"` and `""` into `"on"`) and an *assign hook* that pushes the new value into a `pset.*` field via `ParseVariableBool` / `ParseVariableNum` / `ParseVariableDouble` / enum lookup. Enum errors call `PsqlVarEnumError` (variables.c). [verified-by-code, startup.c:867-1220]

The comment at startup.c:861-865 spells out the policy: every special variable must have a hook so it stays in the variable list even when unset — so tab-completion knows about it.

## State / globals it owns

`PsqlSettings pset` is **defined** here at startup.c:33 — every other file references it as `extern`.

`enum _actions { ACT_SINGLE_QUERY, ACT_SINGLE_SLASH, ACT_FILE }` (startup.c:47) and the `SimpleActionList` linked list of `-c`/`-f` actions are private to startup.c. [verified-by-code]

## Concurrency / signal handling

Empty `SIGCHLD`/`SIGALRM` handlers installed on non-Windows (startup.c:115-119, 325-327) — purely to keep `sigwait` in `do_watch` happy on platforms where unhandled signals get masked.

`psql_setup_cancel_handler()` (startup.c:315) installs the real SIGINT handler — done AFTER the initial connection so a Ctrl-C during the first `PQconnectdbParams` is just a hard-kill, not a cancel-and-keep-going.

## Phase D notes

- **Password retrieval** — `simple_prompt("Password: ", false)` (startup.c:249, 302). The `false` is "don't echo". `password` is malloc'd by `simple_prompt`, passed to `PQconnectdbParams` via the `values[3]` slot, and **never explicitly zeroed before being freed**. The function lifetime keeps it live across the entire `do { } while(new_pass)` retry loop and then a `pg_free(password)` *does* happen at startup.c:4260... wait that's `do_connect`. In `main` the password is only freed implicitly at process exit via the libpq copy stored inside the PGconn. **`main` does not `explicit_bzero` the password buffer** before letting it leak to process exit. [verified-by-code, startup.c:249-302] [ISSUE-secret-scrub: connection password buffer not scrubbed before process exit in main() (likely)]
- **`-W` prompt before username known** (startup.c:241-250) — comment acknowledges this: "we can't be sure yet of the username that will be used, so don't offer a potentially wrong one." Also "since we've not yet set up our cancel handler, there's no need to use simple_prompt_extended." (startup.c:243-247). So the very first password prompt cannot be Ctrl-C cancelled cleanly — Ctrl-C will SIGINT-kill psql. Minor UX, documented. [from-comment]
- **Action `ACT_SINGLE_SLASH`** (startup.c:396-421) builds a transient `PsqlScanState`+`ConditionalStack` and calls `HandleSlashCmds(scan_state, cstack, NULL, NULL)`. The two NULLs are `query_buf` and `previous_buf` — meaning any backslash command that dereferences them in `-c \foo` mode would crash. The protocol is documented in `command.h:23`. [verified-by-code, command.h:23-24; startup.c:413-417]
- **`.psqlrc` lookup order** is deterministic and well-defined. `access(file, R_OK)` is checked but the file's ownership is NOT validated — anyone who can write to `$HOME` (e.g. inside a container or a shared `$HOME` over NFS) can inject psql commands. Same model as `.bashrc`. [verified-by-code, startup.c:830-835] [ISSUE-trust-boundary: .psqlrc lookup does not verify file ownership / mode like ssh does for config (nit, by-design)]
- **`PSQLRC` env var** is `expand_tilde`d (startup.c:804) and then `process_file`d — a user-controlled env var can include arbitrary SQL/backslash content. Documented; this is the intended use. [verified-by-code]
- **`log_pre_callback`** (startup.c:93-97) flushes `pset.queryFout` before each log message. If `queryFout` is a pipe to a hung pager, this can stall log output for the duration of the SIGPIPE handling. [inferred]
- **`pset.notty`** is determined ONCE at startup.c:187 (`!isatty(stdin) || !isatty(stdout)`). If a script later redirects either, `notty` does not update — interactive prompts may fire (or not fire) inconsistently. [inferred]
- **`client_encoding="auto"` only when both interactive AND `PGCLIENTENCODING` is unset** (startup.c:273; same logic for `\connect` at command.c:4164-4167). Non-interactive sessions default to whatever the server picks; this affects how multi-byte data in `\copy` lands. [verified-by-code]
- **Pre-existing comment** at startup.c:4139-4142 (in command.c::do_connect, but same trade-off applies here) admits "this behavior leads to spurious connection attempts recorded in the postmaster's log" because libpq has no way to know it will need a password without trying. Documented. [from-comment]

## Potential issues (compact)

- [ISSUE-secret-scrub: `password` buffer in main() not explicit_bzero'd (likely)]
- [ISSUE-trust-boundary: .psqlrc found via $HOME without ownership/mode check (nit, by-design)]
- [ISSUE-stale-todo: comment at startup.c:861-865 begins "This isn't an amazingly good place for them, but neither is anywhere else." — the assign-hook table is awkward but stable (nit)]

## Cross-references

- `mainloop.c::MainLoop` — invoked at startup.c:471.
- `command.c::HandleSlashCmds` — invoked at startup.c:413 for `-c \foo`.
- `command.c::do_connect` — mirrors much of the connection-retry logic; both paths share the password / keep_password / re-sync concerns.
- `common.c::SyncVariables` declarations actually live in `command.h`; `SyncVariables` itself in command.c:4565.
- `help.c::usage`, `slashUsage`, `helpVariables` — the three `--help` modes.
- `variables.c::SetVariable`, `SetVariableHooks`, `ParseVariableBool/Num/Double`.

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tally

`[verified-by-code]=23 [from-comment]=4 [inferred]=3`
