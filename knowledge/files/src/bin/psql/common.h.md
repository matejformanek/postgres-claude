---
path: src/bin/psql/common.h
anchor_sha: 4b0bf0788b0
loc: 49
depth: header
---

# common.h

- **Source path:** `source/src/bin/psql/common.h`
- **Lines:** 49
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common.c` (2710 lines; the SendQuery / cancel-handling / variable-callback core).

## Purpose

Declares the SendQuery / PSQLexec layer plus the SIGINT longjmp protocol that every interactive read loop participates in. [verified-by-code, common.h:1-49]

## Surface

### Query execution

- `PSQLexec(query)` (34) — "back-door" query path used by all internal lookups (`\d`, `\sf`, `\password`, etc.). Subject to `ECHO_HIDDEN` but not `ECHO_QUERIES`. [verified-by-code, common.c:656-699]
- `PSQLexecWatch(query, opt, fout, min_rows)` (35) — \watch-specific variant; returns 1 / 0 / -1 (success / interrupt / error). [verified-by-code, common.c:711-735]
- `SendQuery(query)` (37) — "front-door" path for user-entered queries. Implicit BEGIN, savepoint on ON_ERROR_ROLLBACK, single-step prompt, etc. [verified-by-code, common.c:1119-1340]

### Output sinks

- `openQueryOutputFile(fname, fout, is_pipe)` (18) — open `|prog`, file, or stdout. Caller manages SIGPIPE. [verified-by-code, common.c:55-82]
- `setQFout(fname)` (19) — `\o` / `-o` handler; replaces `pset.queryFout` and adjusts SIGPIPE state. [verified-by-code, common.c:143-170]

### Variable & notice plumbing

- `psql_get_variable(varname, quote, passthrough)` (21) — the flex-lexer callback that resolves `:foo` / `:'foo'` / `:"foo"` / `:{?foo}`-style references. The `passthrough` is the `ConditionalStack` for `\if`-suppression. [verified-by-code, common.c:187-272]
- `NoticeProcessor(arg, message)` (24) — libpq notice callback; routes to `pg_log_info`. [verified-by-code, common.c:278-283]

### SIGINT longjmp protocol

- `sigint_interrupt_enabled` (26) — `volatile sig_atomic_t`; readers must SET this true *before* a blocking read and clear it after. [verified-by-code, common.h:26; common.c:304]
- `sigint_interrupt_jmp` (28) — paired `sigjmp_buf`. The signal handler `psql_cancel_callback` longjmps through it only if `sigint_interrupt_enabled` was set. [verified-by-code, common.c:308-322]
- `psql_setup_cancel_handler` (30) — installs `psql_cancel_callback` via fe_utils `setup_cancel_handler`.
- Shell-result variables: `SetShellResultVariables(wait_result)` (32) — populates `SHELL_ERROR` / `SHELL_EXIT_CODE`. Used by `\!`, `\copy program`, `\g |prog`, `\o |prog`. [verified-by-code, common.c:517-526]

### Connection introspection

- `is_superuser` (39) — reads `is_superuser` parameter-status. [verified-by-code, common.c:2481-2495]
- `standard_strings` (40) — reads `standard_conforming_strings` parameter-status. [verified-by-code, common.c:2502-2515]
- `session_username` (41) — `session_authorization` falling back to `PQuser`. [verified-by-code, common.c:2522-2534]
- `get_conninfo_value(keyword)` (42) — copy a value out of `PQconninfo` (caller frees). [verified-by-code, common.c:2541-2570]

### Misc helpers

- `expand_tilde(filename)` (44) — substitute `~` / `~user`. No-op on WIN32. Used by virtually every file-taking backslash command. [verified-by-code, common.c:2578-2626]
- `clean_extended_state` (45) — release bind/parse parameter state between extended-protocol commands. [verified-by-code, common.c:2662-2695]
- `recognized_connection_string(connstr)` (47) — true if `connstr` looks parseable by libpq (URI prefix or contains `=`). Comment notes "duplicate of the eponymous libpq function". [verified-by-code, common.c:2706-2710]

## Phase D notes

- The SIGINT longjmp protocol (`sigint_interrupt_enabled` + `sigint_interrupt_jmp`) is the only "concurrency" boundary in psql. Every function that blocks on user input (`gets_interactive`, `simple_prompt_extended`, `handleCopyIn`) must SET the flag, perform `sigsetjmp` first (the *caller* sets it up), and CLEAR the flag on return. The protocol is fragile: if a future change forgets to reset `sigint_interrupt_enabled`, a later signal in the wrong context will siglongjmp into stale stack memory. [verified-by-code, common.c:287-322; mainloop.c:107; copy.c:521] [ISSUE-undocumented-invariant: SIGINT longjmp depends on every blocking-read caller resetting the flag; no static analyser enforces it (nit)]
- `recognized_connection_string` and `uri_prefix_length` (common.c:2636) are explicitly flagged as duplicates of libpq internals — the `XXX` comment is itself a documented gotcha. [from-comment, common.c:2634, 2704] [ISSUE-stale-todo: XXX duplicate of libpq function — could become out-of-sync if libpq's URI-prefix list grows (maybe)]

## Cross-references

- `common.c` — every declaration here.
- `mainloop.c` — uses `sigint_interrupt_jmp` via `sigsetjmp` (mainloop.c:107).
- `copy.c` — same, in `handleCopyIn` (copy.c:521).
- `startup.c` — calls `psql_setup_cancel_handler` (startup.c:315) and `NoticeProcessor`.

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tally

`[verified-by-code]=14 [from-comment]=1`
