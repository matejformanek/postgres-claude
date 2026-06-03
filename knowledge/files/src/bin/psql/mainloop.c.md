---
path: src/bin/psql/mainloop.c
anchor_sha: 4b0bf0788b0
loc: 662
depth: deep
---

# mainloop.c

- **Source path:** `source/src/bin/psql/mainloop.c`
- **Lines:** 662
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `mainloop.h`, `input.c` (`gets_interactive`, `gets_fromFile`, `pg_append_history`, `pg_send_history`), `command.c::HandleSlashCmds`.

## Purpose

The REPL. One function — `MainLoop(FILE *source)` — that reads lines, feeds them to the psqlscan flex lexer to find SQL statements vs backslash commands, accumulates SQL into a `query_buf`, and on each semicolon (or EOF) calls `SendQuery`. Re-entrant: `process_file` calls `MainLoop` recursively for `\i` and the initial `-f` action. [verified-by-code, mainloop.c:25-32]

## Role in psql

This is the second-from-top of the call graph: `main → MainLoop → SendQuery / HandleSlashCmds`. It owns the lexer (`PsqlScanState`), the `\if` stack (`ConditionalStack`), three `PQExpBuffer`s (`query_buf`, `previous_buf`, `history_buf`), the EOF count, the prompt status, and the per-source line counters.

## Key functions / structures

### `psqlscan_callbacks` (mainloop.c:20)

A `const PsqlScanCallbacks` with only one slot, `psql_get_variable`. Exported via `mainloop.h` and also used by `startup.c` for `-c` slash commands. [verified-by-code, mainloop.c:20-22]

### `MainLoop(source)` (mainloop.c:32)

Phases per iteration:

1. **Save/restore source state.** Stash old `pset.cur_cmd_source`, `cur_cmd_interactive`, `lineno`; install new (mainloop.c:57-67). `cur_cmd_interactive` is `(source == stdin) && !pset.notty`. [verified-by-code, mainloop.c:65]
2. **Create per-invocation state** — `psql_scan_create`, `conditional_stack_create`, three `PQExpBuffer`s. (mainloop.c:69-80)
3. **Establish SIGINT longjmp target.** `sigsetjmp(sigint_interrupt_jmp, 1)` at mainloop.c:107. On Ctrl-C the handler in common.c (`psql_cancel_callback`) longjmps here, which resets the lexer, query buffer, prompt, and — when interactive and inside `\if` — pops one `\if` level. Non-interactive sources just exit `EXIT_USER`. [verified-by-code, mainloop.c:107-142]
4. **Read one line.** Interactive: `gets_interactive(get_prompt(...), query_buf)` (mainloop.c:166). Non-interactive: `gets_fromFile(source)` (mainloop.c:171).
5. **EOF handling.** `IGNOREEOF` count mimics bash (mainloop.c:184-198).
6. **UTF-8 BOM strip** on line 1 only (mainloop.c:206-207).
7. **PGDMP detection** — if a script's first line begins `PGDMP`, refuse to run it as SQL and emit a "use pg_restore" message (mainloop.c:209-219). The PGDMP magic comes from `pg_dump`'s custom-format header. [verified-by-code]
8. **`help` / `quit` / `exit` / `\q` recognition** (interactive only, only at start-of-buffer) — mainloop.c:229-357. These are documented as undocumented compatibility shims for users coming from other CLIs.
9. **Echo line** if `ECHO=all` and non-interactive (mainloop.c:360-364).
10. **Lexer loop.** `psql_scan(scan_state, query_buf, &prompt_tmp)` repeatedly until it returns `PSCAN_INCOMPLETE`, `PSCAN_EOL`, or end. On `PSCAN_SEMICOLON` (or EOL in single-line mode), call `SendQuery`. On `PSCAN_BACKSLASH`, call `HandleSlashCmds`. (mainloop.c:386-559)
11. **History push.** On SQL execution OR backslash command in interactive mode, append the input line into `history_buf` and `pg_send_history` flushes it to readline when the query is complete (mainloop.c:429-434, 488-493).
12. **Buffer swap.** After `SendQuery`, swap `query_buf` and `previous_buf` by pointer so `\g`/`\p`/`\w` can reach the last-executed query (mainloop.c:443-449, 517-523). [verified-by-code]
13. **`PSQL_CMD_NEWEDIT` handling** (after `\e`/`\ef`/`\ev`) — copy `query_buf` to `line` and re-scan; trigger redisplay on next prompt (mainloop.c:529-550).

End-of-file handling: if `query_buf` has unsent content and we're non-interactive, run it (mainloop.c:600-626). Then check for unbalanced `\if` (mainloop.c:632-639).

Final cleanup (mainloop.c:640-661): clear `sigint_interrupt_enabled`, destroy buffers / scan state, restore the outer source's `pset.cur_cmd_source`.

## State / globals it owns

Local to one `MainLoop` invocation: `scan_state`, `cond_stack`, `query_buf`, `previous_buf`, `history_buf`, `line`. Reads/writes the global `pset.cur_cmd_source`, `pset.cur_cmd_interactive`, `pset.lineno`, `pset.stmt_lineno`, `pset.inputfile` (indirectly via the caller `process_file`).

The global `cancel_pressed` (from fe_utils/cancel) is read at the top of the loop and cleared. [verified-by-code, mainloop.c:88-100]

## Concurrency / signal handling

`sigsetjmp(sigint_interrupt_jmp, 1)` on every iteration (mainloop.c:107). The Ctrl-C handler longjmps here. The function header comment notes that the jmpbuf "might get changed during command execution" so re-setting it every loop is mandatory (mainloop.c:103-106). [from-comment]

`sigint_interrupt_enabled` is left FALSE by mainloop. It is `gets_interactive` / `gets_fromFile` (in `input.c`) that flips it on around the blocking read. [inferred from common.h:26-28]

## Phase D notes

- **PGDMP detection trusts only the first line.** A hostile script that puts garbage on the first non-empty line and `PGDMP` on the second won't trip the check (mainloop.c:210). Not a security issue — `\copy` / `COPY` from a malformed file is the same risk anyway — but worth knowing. [verified-by-code]
- **`help` / `exit` / `quit` as commands** (mainloop.c:243-356) only fire when `cur_cmd_interactive` is true. A script that contains a bare `help;` line on its own goes straight to the server (which will likely error). This is the intended behavior to avoid surprising users running scripts that happen to use these words. [verified-by-code]
- **History contents.** `pg_append_history(line, history_buf)` (mainloop.c:431, 488, 571) is called on every input line in interactive mode — **including** `\password ...` and `CREATE USER ... PASSWORD '...'` text. `pg_send_history` (input.c) then calls libreadline's `add_history`. psql has NO secret-scrubbing pass between the user typing a password into a SQL statement and that statement being written to `~/.psql_history` at session end. The `\password` meta-command (command.c:2543) is the supported way around this: it prompts via `simple_prompt_extended` and the prompt response never enters `line`. [verified-by-code, mainloop.c:431-433] [ISSUE-secret-scrub: PSQL_HISTORY captures literal CREATE USER … PASSWORD '…' / ALTER ROLE … PASSWORD … lines (likely)]
- **HISTCONTROL `ignorespace`** (mainloop.c references `pset.histcontrol` via input.c) — a user can suppress logging of one statement by prefixing it with whitespace, much like bash. Documented escape hatch.
- **Stale-TODO area NOT_USED.** Block at mainloop.c:605-608 is gated by `#ifdef NOT_USED` with a "currently unneeded" comment. Hasn't been touched but is harmless. [from-comment, mainloop.c:603-608] [ISSUE-dead-code: NOT_USED block at mainloop.c:605-608 (nit)]
- **`pset.stmt_lineno` increment heuristic** — see comment at mainloop.c:402-412: psql counts newlines that psql_scan injected from readline-history multi-line entries. This is fragile if `psql_scan`'s newline policy ever changes. [from-comment]

## Potential issues (compact)

- [ISSUE-secret-scrub: queries containing PASSWORD literals land in PSQL_HISTORY verbatim; only `\password` avoids it (likely)]
- [ISSUE-dead-code: `#ifdef NOT_USED` block at mainloop.c:605 (nit)]

## Cross-references

- `command.c::HandleSlashCmds` — called for every `\`-command.
- `common.c::SendQuery` — called for every semicolon-terminated SQL statement.
- `common.c::sigint_interrupt_jmp` — the longjmp target.
- `input.c` — `gets_interactive`, `gets_fromFile`, `pg_append_history`, `pg_send_history`, `printHistory`.
- `prompt.c::get_prompt` — produces the `%/`, `%~`, etc. prompt text.

## Confidence tally

`[verified-by-code]=18 [from-comment]=4 [inferred]=1`
