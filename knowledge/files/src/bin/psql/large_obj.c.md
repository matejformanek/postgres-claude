---
path: src/bin/psql/large_obj.c
anchor_sha: 4b0bf0788b0
loc: 264
depth: deep
---

# large_obj.c

- **Source path:** `source/src/bin/psql/large_obj.c`
- **Lines:** 264
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `large_obj.h`, `src/interfaces/libpq/fe-lobj.c` (the libpq side that talks the LO protocol — `lo_import`/`lo_export`/`lo_unlink`), `settings.h` (consumes `pset.db`, `pset.autocommit`, `pset.quiet`, `pset.queryFout`, `pset.popt.topt.format`, `pset.logfile`), `command.c` (slash-command dispatcher).

## Purpose

Backs three meta-commands: `\lo_import`, `\lo_export`, `\lo_unlink`. The bulk of the work is in libpq's `lo_import`/`lo_export`/`lo_unlink`; this file wraps them in transaction-management + result-reporting boilerplate.

## Public surface

- `do_lo_export(loid_arg, filename_arg)` (141) — write LOID's content to `filename_arg` on the **psql client's filesystem**. [verified-by-code, large_obj.c:141-167]
- `do_lo_import(filename_arg, comment_arg)` (175) — read `filename_arg` from the **psql client's filesystem** into a new LO. If `comment_arg` is given, run `COMMENT ON LARGE OBJECT <oid> IS '<escaped>'`. Sets `pset.vars["LASTOID"]` to the new OID. [verified-by-code, large_obj.c:175-230]
- `do_lo_unlink(loid_arg)` (238) — `DELETE` the LO. [verified-by-code, large_obj.c:238-264]

## Statics

- `print_lo_result(fmt, ...)` (18) — printf-attribute-tagged. Sends to `pset.queryFout` and `pset.logfile`. Wraps in `<p>...</p>` for HTML output format. [verified-by-code, large_obj.c:18-45]
- `start_lo_xact(operation, *own_transaction)` (55) — if `tstatus == IDLE`, `PSQLexec("BEGIN")` and set `*own_transaction = true`; if `INTRANS`, do nothing; if `INERROR`, fail. [verified-by-code, large_obj.c:55-92]
- `finish_lo_xact(operation, own_transaction)` (97) — `COMMIT` if we own the xact and autocommit; on COMMIT failure, ROLLBACK and return false. [verified-by-code, large_obj.c:97-115]
- `fail_lo_xact(operation, own_transaction)` (120) — `ROLLBACK` if we own the xact and autocommit; always returns false. [verified-by-code, large_obj.c:120-133]

## Filesystem semantics

**Client-side.** The filenames are interpreted on the psql machine, not the server. This matches the libpq `lo_import`/`lo_export` contract. The user running psql has whatever filesystem privileges the OS gives them; the server is not involved in pathname resolution. [verified-by-code via libpq contract] [from-comment, fe-lobj.c — not in this batch]

`\lo_import /etc/shadow` reads via psql's UID and uploads the bytes as a new LO.
`\lo_export 12345 /tmp/leak` writes via psql's UID — could clobber any file the psql user can write.

## State owned

- None. All state is in `pset` (consumed) or the server (the LO itself).
- Side effect: writes `LASTOID` into `pset.vars` after successful `\lo_import`.

## Cancel handling

Each operation does `SetCancelConn(NULL)` immediately before the libpq call and `ResetCancelConn()` after. **NULL means: don't try to cancel the operation if user hits Ctrl-C.** This is because `lo_import`/`lo_export` aren't issued via the normal query path; the cancel logic relies on a SQL query being in flight. [verified-by-code, large_obj.c:150-152, 186-188, 248-250] [inferred — based on common psql idiom]

## Comment-emission path

`do_lo_import` with a comment arg builds the `COMMENT ON LARGE OBJECT <oid> IS '...'` SQL into a `malloc`'d buffer sized `strlen(comment) * 2 + 256`. The literal is escaped via `PQescapeStringConn` directly into the buffer. The 2x multiplier covers the worst-case escaping expansion. [verified-by-code, large_obj.c:197-219]

## Phase D notes

- **`\lo_export` writes to ARBITRARY client-side paths under psql's UID.** No path validation, no chroot, no `realpath`. `\lo_export 12345 /etc/passwd` will attempt the write (and probably fail on permissions). For a sudoed psql, this is the trivial "write any file" primitive. This is by design — psql runs as you, you can already write those files — but it's the kind of footgun that bites when psql is exposed via setuid wrapper or when someone naively pipes user input into psql. [verified-by-code, large_obj.c:151] [ISSUE-path-traversal: `\lo_export` accepts arbitrary client-side filename with no normalization; sudoed-psql or scripted-psql contexts can have a write-any-file primitive (high in those contexts, by-design otherwise)]
- **`\lo_import` reads ARBITRARY client-side paths under psql's UID** then uploads. Same story: trivial read-any-file primitive in contexts where psql is reachable via a privilege boundary. [verified-by-code, large_obj.c:187] [ISSUE-path-traversal: `\lo_import` accepts arbitrary client-side filename for reading; ditto setuid/scripted contexts (high in those contexts, by-design otherwise)]
- **`atooid(loid_arg)` for OID parsing.** `atooid` accepts non-numeric prefixes silently (uses `strtoul` returning 0 on no digits). A typo `\lo_export "garbage" /tmp/x` resolves OID to 0; libpq will then reject as invalid. Not a security issue but a UX papercut. [verified-by-code, large_obj.c:151, 242] [no concern]
- **`COMMENT ON LARGE OBJECT` escaping.** Comment goes through `PQescapeStringConn` (208) so SQL injection through `comment_arg` is correctly defended. [verified-by-code, large_obj.c:208] [no concern]
- **Transaction wrapping correctness.** If the user is inside an explicit `BEGIN`, `start_lo_xact` sees `INTRANS` and joins; `finish_lo_xact` notes `!own_transaction` and skips COMMIT, leaving the user's xact open as expected. If autocommit is OFF and the user is idle, `start_lo_xact` opens a transaction but `finish_lo_xact`'s `pset.autocommit` check skips the COMMIT — so the user is left in an open transaction. This is the documented behavior (autocommit off ⇒ user manages COMMIT) but **`do_lo_import`'s `LASTOID` write happens before `finish_lo_xact`** — and writes to a psql variable, not the server — so it commits visibility-wise even if the user later ROLLBACKs. Surprising but probably correct. [verified-by-code, large_obj.c:102-115, 220-228] [no concern]
- **`SetCancelConn(NULL)` window.** During the libpq call, Ctrl-C is effectively ignored (the SIGINT handler has no conn to cancel). On a giant `\lo_import /huge.bin`, the user can't interrupt cleanly. Documented psql limitation. [verified-by-code, large_obj.c:150-152] [no concern]
- **`pg_malloc_extended(MCXT_ALLOC_NO_OOM)` for the comment buffer.** Returns NULL on allocation failure rather than aborting — so a giant comment is gracefully refused via `fail_lo_xact`. [verified-by-code, large_obj.c:203-205] [no concern]
- **No size limit on `\lo_import`.** A multi-GB file is happily uploaded. RAM pressure is on libpq's chunked LO read; psql doesn't slurp the whole thing. [inferred — libpq lo_import chunks via lo_read loop] [no concern]
- **Error reporting via `pg_log_info`** (not `pg_log_error`) for libpq errors. The `print_lo_result` call sends success info to `queryFout`/`logfile`; failures go to stderr via `pg_log_info` only. Inconsistent logging level. [verified-by-code, large_obj.c:157, 192, 254] [no concern]

## Cross-references

- libpq side: `src/interfaces/libpq/fe-lobj.c` (not in this batch).
- Cancel infrastructure: `fe_utils/cancel.c` (not in this batch).
- `PSQLexec`: `common.c` (not in this batch).

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=1 [inferred]=2 [no concern]=7 [ISSUE]=2`
