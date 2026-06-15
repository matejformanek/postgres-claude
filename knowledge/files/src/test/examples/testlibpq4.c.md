---
path: src/test/examples/testlibpq4.c
anchor_sha: e18b0cb7344
loc: 163
depth: read
---

# src/test/examples/testlibpq4.c

## Purpose

Demonstrates how to hold **two concurrent libpq connections** open in a
single client process — e.g. for a copy-between-databases utility, a
diff tool, or any app that needs to interleave queries against two
servers. The program opens `conn1` (default `dbname=postgres`) and
`conn2` (database name from argv[1]), runs `SELECT * FROM pg_database`
on `conn1` while issuing other work on `conn2`. `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `static void exit_nicely(PGconn *conn1, PGconn *conn2)` | `testlibpq4.c:14-22` | finishes both, exits |
| `static void check_prepare_conn(PGconn *conn, const char *dbName)` | `testlibpq4.c:24-46` | checks status + sets safe search_path |
| `int main(int argc, char **argv)` | `testlibpq4.c:48-` | opens two conns |

## Internal landmarks

- `check_prepare_conn` (`:24`) is the per-connection guard: verify
  `CONNECTION_OK`, then run `SELECT pg_catalog.set_config('search_path',
  '', false)` to prevent search-path hijacks. Mirrors the same hardening
  in testlibpq.c. `[from-comment]`
- Both connections are independent — there is no shared transaction
  state, no two-phase commit, no atomic coordination. This is just two
  unrelated sessions held in one address space.

## Invariants & gotchas

- libpq is thread-safe per-PGconn but NOT across threads sharing one
  PGconn — each connection must be touched by at most one thread at a
  time. This file is single-threaded so the issue doesn't arise.
- Naming: the program is the conventional fourth example in a series
  (testlibpq, testlibpq2, testlibpq3, testlibpq4). It is the
  multi-connection example; despite the file's brief comment "this
  test program shows to use LIBPQ to make multiple backend
  connections", the title here is misleadingly close to a "prepared
  statement" demo elsewhere in old PG docs — that's covered by
  `PQprepare` / `PQexecPrepared` examples in the libpq SGML, not by
  this file.
- Shipped example, not a regression test.

## Cross-refs

- `knowledge/files/src/test/examples/testlibpq.c.md` — minimal client.
- `knowledge/files/src/test/examples/testlibpq2.c.md` — async LISTEN/NOTIFY.
- `knowledge/files/src/test/examples/testlibpq3.c.md` — parameterized + binary.
