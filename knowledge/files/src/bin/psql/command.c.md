---
path: src/bin/psql/command.c
anchor_sha: 4b0bf0788b0
loc: 6571
depth: deep
---

# command.c

- **Source path:** `source/src/bin/psql/command.c`
- **Lines:** 6571
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `command.h` (externs + `backslashResult` enum), `common.c::SendQuery / PSQLexec` (downstream), `describe.c` (the SQL-emitting `\d*` implementations), `large_obj.c` (`do_lo_*`), `copy.c::do_copy`.

## Purpose

Every backslash meta-command. ~70 `exec_command_*` static functions plus the dispatcher `HandleSlashCmds` plus the shared helpers (`do_connect`, `do_edit`, `do_shell`, `do_watch`, `do_pset`, `process_file`, `lookup_object_oid`, `get_create_object_cmd`, `minimal_error_message`, the `\restrict` machinery, the SyncVariables/UnsyncVariables variable lifecycle). [verified-by-code, command.c:1-6571]

## Role in psql

`MainLoop → HandleSlashCmds → exec_command → exec_command_<foo> → [do_pset|do_connect|do_edit|do_shell|do_watch|do_copy|do_lo_*|SendQuery|PSQLexec|process_file|...]`.

`startup.c::main` also calls `HandleSlashCmds` directly for `-c \foo` actions (with `query_buf`/`previous_buf == NULL`).

## Key functions

### Dispatcher: `HandleSlashCmds` (command.c:230)

1. `psql_scan_slash_command` reads the command name.
2. If `restricted && cmd != "unrestrict"` → error. (command.c:252-256)
3. Else `exec_command(cmd, ...)`.
4. After return, drain leftover args (with a transient inactive conditional stack push so backticks in the leftover args don't fire); on error, swallow whole-line via OT_WHOLE_LINE. (command.c:268-293)
5. `psql_scan_slash_command_end` swallows a trailing `\\`.
6. Final `fflush(pset.queryFout)`.

### Big switch: `exec_command` (command.c:314)

Chain of `strcmp` against ~60 command names plus `cmd[0] == 'd'` for the `\d*` family. Falls through to `PSQL_CMD_UNKNOWN` on no match. At the end, if status is `PSQL_CMD_SEND` and `query_buf` is empty, copy `previous_buf` into it (so `\g` repeats the prior query). [verified-by-code, command.c:482-490]

### Connection management: `do_connect` (command.c:3917)

The richest non-dispatcher routine. Parameters: `reuse_previous` (TRI_DEFAULT/YES/NO), and explicit `dbname/user/host/port` overrides.

- If `dbname` looks like a conninfo string (`recognized_connection_string`), it's parsed via `PQconninfoParse` and other args are rejected. (command.c:3932-3940)
- `reuse_previous` defaults to `!has_connection_string`. (command.c:3942-3953)
- If reusing, pull `PQconninfo(pset.db)` or `PQconninfo(pset.dead_conn)`; else `PQconndefaults`.
- `keep_password` tracks whether the old conn's password is still valid: any change in `user`/`host`/`hostaddr`/`port` clears it. dbname changes don't, since passwords aren't db-scoped. (command.c:3955-4124)
- Password prompt arms — `getPassword==TRI_YES` prompts up front (without echoing the user if it's a conninfo string, since user might be inside it); otherwise try once then prompt on `PQconnectionNeedsPassword`. (command.c:4143-4157, 4234-4247)
- Calls `PQconnectStartParams` + `wait_until_connected` loop with `PQsocketPoll` and per-iteration `cancel_pressed` check. (command.c:4221-4247, 4381-4440)
- On failure interactive: keep old conn. On failure non-interactive: `PQfinish` both old and dead_conn to prevent further reuse (the comment at command.c:4292-4299 explains: "so that a script cannot accidentally reuse parameters it did not expect to"). [from-comment]
- On success: `PQsetNoticeProcessor`, replace `pset.db`, `SyncVariables`, `connection_warnings`. (command.c:4319-4326)
- The `param_is_newly_set` test (command.c:3894) determines whether to print the verbose "now connected to … on host …" message or the short version.

### `do_edit` (command.c:4730) and `editFile` (command.c:4647)

- Editor pick order: `PSQL_EDITOR`, `EDITOR`, `VISUAL`, `DEFAULT_EDITOR` (a build-time constant). (command.c:4658-4664)
- Line-number argument: `PSQL_EDITOR_LINENUMBER_ARG` env or `DEFAULT_EDITOR_LINENUMBER_ARG` macro; missing means error if `lineno > 0`.
- Temp file: `${TMPDIR}/psql.edit.<pid>.sql` (Unix) created with `open(O_WRONLY|O_CREAT|O_EXCL, 0600)` then `fdopen`. (command.c:4779-4781) [verified-by-code]
- Detect modification by `(st_size != after.st_size || st_mtime != after.st_mtime)`. To avoid same-second false-negatives, `utime(fname, ...)` backdates the file by 2 seconds before opening the editor. (command.c:4820-4834)
- Shell-command construction (command.c:4688-4702): on Unix, `psprintf("exec %s '%s'", editorName, fname)` — the FILENAME is single-quoted, the EDITOR is not. A user-supplied filename containing `'` will break the command. Documented in the long comment at command.c:4683-4687.

### `do_shell` (command.c:5871)

- No command argument → spawn `$SHELL` (`$COMSPEC` on Win32, else `DEFAULT_SHELL=/bin/sh`).
- With command argument → `system(command)`. The argument is whatever the user passed after `\!` — psql_scan_slash_option with OT_WHOLE_LINE.
- Calls `SetShellResultVariables(result)` so `SHELL_ERROR`/`SHELL_EXIT_CODE` track the outcome.

### `do_watch` (command.c:5922)

Pseudo-event loop:
- Build `sigset_t`s, `sigprocmask` to block SIGALRM/SIGCHLD before starting the itimer (command.c:5948-5977).
- `PSQL_WATCH_PAGER` for pager (NOT `PSQL_PAGER`); only use if both stdin and stdout are ttys. (command.c:5988-6004)
- Loop: format the title with `strftime("%c", ...)`, call `PSQLexecWatch`, then `sigwait` on `{SIGALRM, SIGCHLD, SIGINT}` to either run the next iteration (SIGALRM) or exit (SIGINT/SIGCHLD). (command.c:6029-6126)
- On Windows: `pg_usleep` loop with periodic `cancel_pressed` check. (command.c:6073-6091)
- Tear down: `pclose` the pager (with `restore_sigpipe_trap`); print a `\n` if no pager so libreadline cursor isn't confused. (command.c:6128-6144)

### `do_pset` (command.c:5078)

Big strcmp ladder over ~40 pset names. Some accept an optional value; some toggle on bare invocation. Errors raise via `pg_log_error` with the list of allowed values.

### `process_file` (command.c:4924)

- `NULL` filename → stdin.
- `-` → stdin (with display name `<stdin>`).
- Otherwise `canonicalize_path_enc(filename)` then `fopen(filename, PG_BINARY_R)`.
- `\ir` (include-relative): if pset.inputfile is set and filename is relative, prepend the parent dir of the current script. (command.c:4947-4956)
- Set `pset.inputfile = filename`, call `MainLoop(fd)`, restore. [verified-by-code]

### `lookup_object_oid` (command.c:6195) and `get_create_object_cmd` (command.c:6257)

Used by `\sf` / `\sv` / `\ef` / `\ev`. `lookup_object_oid` builds a `SELECT '<desc>'::pg_catalog.regprocedure::oid` (or regproc/regclass) and runs via `PSQLexec` (with `echo_hidden_command`). `appendStringLiteralConn` escapes the user's `<desc>` argument. [verified-by-code, command.c:6213, 6227]

### `\restrict` machinery (command.c:199-200, 2784, 3194)

Two file-scope statics: `static bool restricted;` and `static char *restrict_key;`. Set by `\restrict <key>`; cleared by `\unrestrict <key>` if the keys match.

Once `restricted == true`, `HandleSlashCmds` rejects every backslash command except `\unrestrict` (command.c:252-256). The `restrict_key` is never used in SQL — it's purely a token to prove the unrestricting source authorised the unrestriction. This is the same `\restrict`/`\unrestrict` that `pg_dump` uses to seal dump scripts. [verified-by-code]

### `\password` (command.c:2543)

- If no username, `SELECT CURRENT_USER` via PSQLexec.
- Prompt twice with `simple_prompt_extended(prompt, false, &prompt_ctx)` where `false = no-echo` and `prompt_ctx` is wired to SIGINT (longjmp out on Ctrl-C).
- Compare pw1 / pw2; on match, call `PQchangePassword(pset.db, user, pw1)`.
- `PQchangePassword` is the libpq routine added precisely so psql does NOT have to SHA-encrypt and build the `ALTER ROLE ... PASSWORD '...'` SQL itself. [verified-by-code, command.c:2569-2602]

### `\conninfo` (command.c:788)

Builds a `printTableContent` of: Database, Client User, Host/HostAddr/Socket, Server Port, Options, Protocol Version, Password Used, GSSAPI Authenticated, Backend PID, SSL Connection, [SSL Library/Protocol/Key Bits/Cipher/Compression/ALPN], Superuser, Hot Standby. Everything comes from `PQ*` / `PQsslAttribute` / `PQparameterStatus`. [verified-by-code]

### `\copy` (command.c:963)

Trivial: take whole-line via OT_WHOLE_LINE, hand to `do_copy` in copy.c.

### `\lo_*` (command.c:2369)

Dispatches `\lo_import`, `\lo_export`, `\lo_list`/`\lo_list+`/`\lo_listx`, `\lo_unlink` to `do_lo_*` in large_obj.c. Both filename arguments go through `expand_tilde`. [verified-by-code, command.c:2393, 2407]

### `\g` / `\gx` (command.c:1740)

- Reads next option as `OT_FILEPIPE`. If it begins with `(`, parse `(pset-opt=val, ...)` via `process_command_g_options` (command.c:1801) and then re-scan for a filename. (command.c:1752-1761)
- If `pset.gfname == NULL` → results go to `pset.queryFout`; else `expand_tilde` and stash in `pset.gfname` for `SetupGOutput` to open later. (command.c:1773-1779)
- `\gx` also forces `expanded=on` for this query only. (command.c:1780-1786)

### `\setenv` (command.c:2930)

`setenv(envvar, envval, 1)` or `unsetenv(envvar)` if no value. Rejects names containing `=`. [verified-by-code, command.c:2947-2962]

### `\getenv` (command.c:1893)

Reads `getenv(name)` and `SetVariable(pset.vars, varname, value ?: "")`. [verified-by-code]

### `\w` write-buffer (command.c:3264)

- `OT_FILEPIPE`. `|prog` → `popen`; otherwise `canonicalize_path_enc` then `fopen(fname, "w")` — overwrites, NO append. (command.c:3292-3303)

### `\i` / `\ir` `exec_command_include` (command.c:2064)

`expand_tilde(&fname)` then `process_file(fname, include_relative)`. [verified-by-code]

### `\cd` (command.c:691)

Arg → that path. No arg → `$HOME` (Unix: getenv("HOME") fallback to `getpwuid(geteuid())->pw_dir`; Win32: "/"). Then `chdir`. [verified-by-code]

## State / globals it owns

- `static bool restricted;` (command.c:199) — `\restrict` mode flag.
- `static char *restrict_key;` (command.c:200) — the matching key string. Stored as pstrdup'd; freed by `\unrestrict`.

`pset` is read everywhere. `pset.gfname`, `pset.gsavepopt`, `pset.gset_prefix`, `pset.crosstab_flag`, `pset.gdesc_flag`, `pset.gexec_flag`, `pset.stmtName`, `pset.bind_*`, `pset.send_mode` are all set by `exec_command_*` and consumed by common.c::SendQuery cleanup.

## Concurrency / signal handling

- `\watch` uses `sigprocmask` + `sigwait` (POSIX) or `pg_usleep` + `cancel_pressed` poll (Win32).
- `\password` and `\prompt` set up a `PromptInterruptContext` so `simple_prompt_extended` can detect Ctrl-C without crashing.
- `do_edit`, `do_shell` call `fflush(NULL)` before `system(3)` so child sees flushed state.
- `\copy program`, `\w |prog`, `\o |prog`, `\g |prog`, `\watch pager`: every `popen` call is preceded by `disable_sigpipe_trap` and followed by `restore_sigpipe_trap` (in copy.c / common.c).

## Phase D notes

### Top-tier observations

- **`\!` shell escape (`exec_command_shell_escape` + `do_shell`)** — the user-supplied command line goes verbatim to `system(3)`. No `appendShellString` wrap, no argument splitting; this IS intentional: `\!` is documented as "run a shell command". Variable expansion happened earlier inside the psql_scan lexer via `psql_get_variable(PQUOTE_SHELL_ARG)` which does single-quote escape. So `\! foo :'bar'` ends up being `system("foo 'safely_quoted_value'")`. But `\!` with literal user-typed shell metacharacters is by design. [verified-by-code, command.c:5871-5909; common.c:246-266]
- **`\edit` editor command construction** — `psprintf("exec %s %s%d '%s'", editorName, editor_lineno_arg, lineno, fname)`. The filename is single-quoted; a filename literal containing `'` will break parsing. `editorName` is NOT quoted (per the comment at command.c:4683-4687 saying that's intentional to allow `EDITOR="pico -t"`). A malicious `$EDITOR` env value can absolutely run arbitrary commands — same trust model as other Unix tools. [verified-by-code, command.c:4690-4694] [ISSUE-shell-injection: \e with filename containing `'` breaks the shell command; documented constraint on EDITOR env var (nit, by-design)]
- **`do_edit` temp file at 0600** is correct (command.c:4779). Filename pattern `psql.edit.<pid>.sql` in `$TMPDIR` or `/tmp` is predictable but `O_EXCL` makes pre-creation by an attacker fail. The temp file is removed at command.c:4900-4907 — but only if no `filename_arg` was given. If the editor invocation errors out earlier (`fopen` failure, write failure), the cleanup at command.c:4806, 4814 fires. [verified-by-code]
- **`\copy` already analysed in copy.c.md.** The `PROGRAM 'cmd'` arm calls `popen` unsanitised — by design.
- **`\restrict` / `\unrestrict`** — added explicitly so a malicious server can't get a privileged restore script to run arbitrary backslash commands. `pg_dump` emits `\restrict <random>` at the top of dump scripts and `\unrestrict <same-random>` at the end; the random comes from `generate_restrict_key` in `dumputils.c:976`. Between them, all backslash commands except `\unrestrict` are blocked. The `restricted` and `restrict_key` are file-statics, so the protection survives `\i`/`\ir` recursion (`process_file → MainLoop → HandleSlashCmds`). [verified-by-code, command.c:199-200, 252-256, 2784-2807, 3194-3228; dumputils.c:976]
- **`\connect` keep-password logic** is subtle — any change in user/host/hostaddr/port clears the old password to avoid sending it to a wrong place. dbname change preserves it (passwords are not db-scoped). Conninfo strings carrying an explicit password reset `keep_password = true`. (command.c:4015-4031, 4101-4119) [verified-by-code]
- **`\password` does not echo the password** (uses `simple_prompt_extended(..., false, ...)`) and uses `PQchangePassword` so the password is SCRAM-hashed by libpq before transmission, never appearing in the wire-level SQL as a literal. The username COULD theoretically end up logged via `ECHO_HIDDEN` because the `SELECT CURRENT_USER` lookup uses `PSQLexec`. [verified-by-code, command.c:2561, 2577, 2593]
- **`\conninfo` displays "Password Used: true/false"** from `PQconnectionUsedPassword` (command.c:822). Doesn't reveal the password.
- **`\setenv` writes process env**; the comment at command.c:2947-2952 enforces "no `=` in name". `\getenv` reads. These are obvious self-modification surfaces but the user is in control. [verified-by-code]
- **`\w |prog`** uses `popen` with `disable_sigpipe_trap` (command.c:3296). Filename branch uses `fopen("w")` — overwrites. [verified-by-code]
- **`\o file`** truncates by `fopen("w")` via `openQueryOutputFile` (common.c:71). Same pattern.
- **`process_file` / `\i`**: `canonicalize_path_enc` then plain `fopen` — no permission/ownership check. Inside a malicious script, `\i /etc/something` will simply attempt the file. Same trust model as a shell `. file`. [verified-by-code]
- **`do_watch` uses `PSQL_WATCH_PAGER` separately from `PSQL_PAGER`/`PAGER`** (command.c:5988-5993) so a normal pager doesn't accidentally get used in a continuous-stream context. Empty/whitespace value disables the pager.
- **`\connect` `wait_until_connected`** comment (command.c:4407-4419) admits a race window: SIGINT between `cancel_pressed` check and `PQsocketPoll` may not be observed for up to 1 second. Documented limitation. [from-comment]
- **`\prompt`** uses `simple_prompt_extended` with `echo=true` (command.c:2659) so the typed input is shown — for a password prompt use `\password`. The prompt response is stored in a psql variable, not handled specially. [verified-by-code]

### Middle-tier observations

- **`HandleSlashCmds` error-arg-swallowing** (command.c:286-293) uses `OT_WHOLE_LINE` after an erroneous command — important so a typo on the first option doesn't leave the parser mid-line.
- **`exec_command` inactive-branch handling** (command.c:331-336) emits a warning in interactive mode when a non-branching command appears inside an inactive `\if`; the command still parses+discards its args so positional alignment matches the active case. Each `exec_command_*` is responsible for using `ignore_slash_*` to drain args.
- **`exec_command_print` `\p`** (command.c:2483) prints either `query_buf` or (fallback) `previous_buf`. Uses `puts` so the query text goes to stdout — if it contains literal control characters from a previous `\set` or variable expansion they're echoed unescaped. [verified-by-code]
- **`exec_command_password` PQchangePassword path**: if `PQchangePassword` returns non-OK, the password is wiped from pw1/pw2 via the `free(pw1)`/`free(pw2)` at command.c:2604-2607 — but **without `explicit_bzero`**. The string remains in heap memory until reuse. [verified-by-code] [ISSUE-secret-scrub: \password pw1/pw2 buffers not explicit_bzero'd before free (likely)]
- **`get_create_object_cmd`** (command.c:6257) builds `pg_get_functiondef(oid)` / `pg_get_viewdef(oid)` queries, runs via PSQLexec, and returns the server's text into `buf` — which is then either written to a temp file for `\ef`/`\ev` or printed for `\sf`/`\sv`. Server text is trusted but it IS server-trusted, not user-typed. [verified-by-code]
- **`gather_boolean_expression`** (command.c:3674) reads the rest of the line for `\if` / `\elif` — with the conditional stack temporarily flipped to allow variable expansion only in active branches. This is the documented mechanism that prevents an inactive branch from running expensive backtick expansion. [verified-by-code]
- **`save_query_text_state` / `discard_query_text`** (command.c:3801-3835) are the backstop that prevents `\if FALSE; SELECT ...; \endif` from appending the SELECT into `query_buf` and then accidentally sending it. The saved length is reset on `\endif`. [verified-by-code]

### Low-tier

- **`exec_command_t` `\t`** wraps `do_pset("tuples_only", opt, ...)`. The comment at command.c:498 ("This makes little sense but we keep it around") is about `\a`, which simply toggles aligned/unaligned. [from-comment]
- **`exec_command_C` `\C`** (command.c:605) sets the table title via `do_pset("title", value, ...)`.
- **`exec_command_C` and `\T` `\f`** are thin wrappers.
- **`exec_command_d`** (command.c:1021) decodes the `\d` suffix table (A, b, c, C, d, D, e, E, f, F, g, h, i, l, m, n, o, O, p, P, r, R, s, S, t, T, u, U, v, w, x, X, y), dispatches to functions in `describe.c`. The pattern is OT_NORMAL.

## Potential issues (compact)

- [ISSUE-secret-scrub: `\password` pw1/pw2 freed without explicit_bzero (likely)]
- [ISSUE-shell-injection: `\e` editor command uses single-quoted fname but unquoted EDITOR — env-controlled, by-design (nit)]
- [ISSUE-shell-injection: `\!` runs arbitrary user command via system(3) — by-design (nit, by-design)]
- [ISSUE-trust-boundary: `\restrict <key>` prevents backslash escape but does NOT prevent malicious SQL the dump still emits; psql trusts that the surrounding dump was generated locally (nit, by-design)]
- [ISSUE-undocumented-invariant: `restricted` and `restrict_key` are file-statics; they persist across `\i`/`process_file` recursion intentionally (nit)]
- [ISSUE-info-disclosure: ECHO_HIDDEN echoes internal queries including `SELECT CURRENT_USER` issued during `\password` (nit, by-design)]
- [ISSUE-dos: `do_watch` race comment at command.c:4407-4419 admits up to 1-second SIGINT-miss window in `wait_until_connected` (nit)]

## Cross-references

- `command.h` — externs.
- `common.c::SendQuery`, `PSQLexec` — every command that hits the server goes through them.
- `copy.c::do_copy` — `\copy` body.
- `describe.c` — every `\d`* / `\l` / `\z` / `\sf` body.
- `large_obj.c` — `do_lo_import/export/list/unlink`.
- `help.c::slashUsage`, `usage`, `helpVariables` — the three `\?` modes.
- `prompt.c::get_prompt` — `\set PROMPT1/2/3` consumers.
- `input.c::printHistory`, `pg_send_history` — `\s` and history flushing.
- `dumputils.c::generate_restrict_key` — produces the key `pg_dump` puts into a `\restrict <key>`.

## Confidence tally

`[verified-by-code]=40 [from-comment]=4 [inferred]=1`
