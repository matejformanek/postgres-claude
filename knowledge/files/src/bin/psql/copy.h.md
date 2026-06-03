---
path: src/bin/psql/copy.h
anchor_sha: 4b0bf0788b0
loc: 24
depth: header
---

# copy.h

- **Source path:** `source/src/bin/psql/copy.h`
- **Lines:** 24
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `copy.c` (736 lines).

## Purpose

Three-function interface: `do_copy` (the `\copy` meta-command top-level) and the two `handleCopy{In,Out}` helpers that the server-side `COPY` protocol code in common.c calls when a regular SQL `COPY ... FROM STDIN` / `TO STDOUT` lands. [verified-by-code, copy.h:14-23]

## Surface

- `do_copy(args)` (15) — parse and execute `\copy`. Calls `parse_slash_copy`, opens the file or `popen`s the program, runs `SendQuery("COPY ... FROM STDIN" / "TO STDOUT")`. [verified-by-code, copy.c:267-408]
- `handleCopyOut(conn, copystream, **res)` (19) — drain `PQgetCopyData` to a `FILE*` (may be NULL to discard). Used both for `\copy ... TO` and for plain server-driven `COPY TO STDOUT`. [verified-by-code, copy.c:433-491]
- `handleCopyIn(conn, copystream, isbinary, **res)` (21) — push file contents through `PQputCopyData`. Respects `\.` end-marker in text mode (for inlined SQL scripts) but NOT in CSV mode. Establishes `sigsetjmp` so SIGINT cancels the transfer cleanly. [verified-by-code, copy.c:510-736]

## Phase D notes

- `do_copy` is the supported "client can read arbitrary files via the database session" surface; `parse_slash_copy` accepts `PROGRAM 'cmd'` which goes straight to `popen` (copy.c:293, 312) with no sanitisation beyond quote stripping. This is documented psql behavior; restricting it requires server-level GUCs, not psql changes. [verified-by-code, copy.c:202-223] [ISSUE-shell-injection: \copy PROGRAM passes the quoted command literally to popen(3) — by design but worth documenting (nit, by-design)]
- The `\.` end-marker is recognised in text mode only (copy.c:633) so a CSV input containing a literal line `\.\n` will be sent through and interpreted as data, which is correct but easy to forget. [from-comment, copy.c:585-590]

## Cross-references

- `copy.c` — the implementation.
- `common.c::HandleCopyResult` (common.c:938) — dispatches PGRES_COPY_IN / PGRES_COPY_OUT to these two functions.

## Confidence tally

`[verified-by-code]=4 [from-comment]=1`
