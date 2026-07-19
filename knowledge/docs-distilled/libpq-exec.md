---
source_url: https://www.postgresql.org/docs/current/libpq-exec.html
fetched_at: 2026-07-19T19:56:59Z
anchor_sha: dde9a87d4d02
title: "libpq §34.3 — Main Command Execution (simple vs extended protocol, param binding, prepared statements, binary results)"
maps_to_skill: wire-protocol
---

# libpq §34.3 — Main Command Execution Functions

The synchronous execution surface, and — more importantly — the protocol split:
`PQexec` rides the *simple* query protocol, `PQexecParams`/`PQexecPrepared` ride
the *extended* one (Parse/Bind/Execute). That single distinction drives
injection-safety, multi-statement rules, binary results, and prepared plans.

## Non-obvious claims

- **`PQexecParams` accepts at most ONE command; `PQexec` accepts many.** "allows
  at most one SQL command in the given string. (There can be semicolons in it,
  but not more than one nonempty command.) This is a limitation of the underlying
  protocol, but has some usefulness as an extra defense against SQL-injection
  attacks." `PQexec` at `source/src/interfaces/libpq/fe-exec.c:2279`,
  `PQexecParams` at `:2293`. [verified-by-code]
- **`PQexec` reports only the LAST command's result and stops on first failure.**
  "`PGresult` describes only the result of the last command executed" and "Should
  one of the commands fail, processing of the string stops with it." (The async
  path is the only way to see every statement — see `libpq-async.md`.) [from-docs]
- **A NULL `paramValues[i]` means SQL NULL.** "A null pointer in this array means
  the corresponding parameter is null; otherwise the pointer points to a
  zero-terminated text string (for text format) or binary data." [from-docs]
- **`paramTypes[i] == 0` (or `paramTypes == NULL`) defers type inference to the
  server** — "the server infers a data type for the parameter symbol in the same
  way it would do for an untyped literal string." Forcing the type via a cast
  (`$1::bigint`) "is strongly recommended when sending parameter values in binary
  format." [from-docs]
- **`paramLengths` is consulted only for binary, non-NULL params** — "ignored for
  null parameters and text-format parameters." `paramFormats[i]` is 0=text /
  1=binary *per parameter*; binary values need internal representation ("integers
  must be passed in network byte order"). [from-docs]
- **`resultFormat` is a single int applied to ALL columns.** 0=text, 1=binary,
  and "There is not currently a provision to obtain different result columns in
  different formats, although that is possible in the underlying protocol." [from-docs]
- **Prepared statements: empty name = unnamed slot that auto-replaces.**
  `PQprepare(conn, stmtName, query, nParams, paramTypes)`: "`stmtName` can be `""`
  to create an unnamed statement, in which case any pre-existing unnamed statement
  is automatically replaced; otherwise it is an error if the statement name is
  already defined." `PQexecPrepared` takes **no** `paramTypes` (fixed at prepare
  time). `PQprepare` at `fe-exec.c:2323`, `PQexecPrepared` at `:2340`,
  async `PQsendPrepare` at `:1553`. [verified-by-code]
- **`PGRES_COMMAND_OK` vs `PGRES_TUPLES_OK` is about *can-ever-return-rows*, not
  actual row count.** "A `SELECT` command that happens to retrieve zero rows still
  shows `PGRES_TUPLES_OK`. `PGRES_COMMAND_OK` is for commands that can never
  return rows (`INSERT` or `UPDATE` without a `RETURNING` clause, etc.)." Statuses
  at `libpq-fe.h:131` / `:134`; `PGRES_FATAL_ERROR` at `:142`. [verified-by-code]
- **Parameters bind DATA VALUES only — never identifiers or keywords.** "it is
  neither necessary nor correct to do escaping when a data value is passed as a
  separate parameter"; but table/column names still need `PQescapeIdentifier`.
  This is the injection-safety boundary. [from-docs]

## Links into corpus

- Simple vs extended protocol on the wire: [[knowledge/docs-distilled/protocol-flow.md]],
  [[knowledge/docs-distilled/protocol-message-formats.md]].
- Async siblings (same protocol, non-blocking): [[knowledge/docs-distilled/libpq-async.md]].
- Pipeline mode requires these extended-protocol calls: [[knowledge/docs-distilled/libpq-pipeline-mode.md]].
- Source: [[knowledge/files/src/interfaces/libpq/fe-exec.c.md]],
  [[knowledge/files/src/interfaces/libpq/libpq-fe.h.md]].
