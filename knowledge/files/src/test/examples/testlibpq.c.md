---
path: src/test/examples/testlibpq.c
anchor_sha: e18b0cb7344
loc: 131
depth: read
---

# src/test/examples/testlibpq.c

## Purpose

The canonical "hello world" libpq client. Demonstrates the minimal flow
for a C frontend program: connect with `PQconnectdb`, check status with
`PQstatus`, run a sequence of queries with `PQexec`, walk the result set
with `PQntuples` / `PQnfields` / `PQfname` / `PQgetvalue`, free with
`PQclear`, disconnect with `PQfinish`. This is the reference example
quoted from the libpq documentation; it ships in source form so users
can build it directly. `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `static void exit_nicely(PGconn *conn)` | `testlibpq.c:13-18` | helper: `PQfinish` + `exit(1)` |
| `int main(int argc, char **argv)` | `testlibpq.c:20-130` | full demo flow |

## Internal landmarks

- Connection: `PQconnectdb(conninfo)` at `:41` — `conninfo` either from
  argv[1] or default `"dbname = postgres"`.
- Security hardening: explicit `SET search_path = ''` (`:51-58`) with a
  comment warning about malicious users. `[from-comment]`
- Cursor demo: BEGIN, `DECLARE myportal CURSOR FOR SELECT * FROM
  pg_database`, `FETCH ALL IN myportal`, CLOSE, COMMIT. Walks the
  result tuples printing field names + values.
- No NOTIFY, no parameters, no prepared statements — those live in
  testlibpq2/3/4 respectively.

## Invariants & gotchas

- This is a **shipped example**, not a test. The build system compiles
  it to validate that the libpq headers + library installed correctly
  expose the public API surface, but `meson test` does not execute
  it as part of a regression run.
- Every `PQexec` is followed by `PQclear` (`:64`, `:76`, `:104`, `:117`)
  — leaking `PGresult` is the canonical libpq beginner bug.
- Connection status is checked at `:44` with `PQstatus(conn) != CONNECTION_OK`.
  Real apps should ALSO call `PQerrorMessage` to surface the cause.

## Cross-refs

- `knowledge/files/src/test/examples/testlibpq2.c.md` — async NOTIFY/LISTEN.
- `knowledge/files/src/test/examples/testlibpq3.c.md` — parameterized + binary.
- `knowledge/files/src/test/examples/testlibpq4.c.md` — multiple connections.
- `doc/src/sgml/libpq.sgml` — the chapter this file is quoted into.
