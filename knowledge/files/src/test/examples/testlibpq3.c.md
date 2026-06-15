---
path: src/test/examples/testlibpq3.c
anchor_sha: e18b0cb7344
loc: 230
depth: read
---

# src/test/examples/testlibpq3.c

## Purpose

Demonstrates **out-of-line parameter binding and binary result format**
via `PQexecParams`. Shows how to pass `int4`, `text`, and `bytea`
values both as text-format parameters and as binary parameters, and
how to fetch results in binary mode with `PQfformat == 1`. The header
comment provides the SQL setup (`testlibpq3.test1` with `i int4 / t
text / b bytea`) and the expected output so users can validate.
`[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `static void exit_nicely(PGconn *conn)` | `testlibpq3.c:46-51` | standard helper |
| `static void show_binary_results(PGresult *res)` | `testlibpq3.c:58-` | walks binary tuples |
| `int main(int argc, char **argv)` | `testlibpq3.c` end | two-call demo |

## Internal landmarks

- Includes `<netinet/in.h>` + `<arpa/inet.h>` for `ntohl()`/`htonl()`
  — necessary because binary `int4` is sent network-byte-order
  (`:42`).
- Calls `PQexecParams` with `nParams=1`, `paramTypes=NULL`
  (server infers), `paramLengths` matching the binary representation,
  `paramFormats` = 1 for binary, `resultFormat` = 1 for binary.
- `show_binary_results` (`:58`) walks the result with `PQgetvalue` +
  `PQgetlength` and prints raw bytes for `bytea`.

## Invariants & gotchas

- Binary `int4` is **network byte order**: `htonl()` to send,
  `ntohl()` to receive. The expected output in the file's header
  reflects this. `[from-comment]`
- `paramTypes=NULL` works only because the server can infer the type
  from the textual SQL. For ambiguous cases pass actual `Oid` values
  (e.g. `INT4OID` from `pg_type.h`, though clients typically hard-
  code the numeric value).
- Shipped example, not a regression test.

## Cross-refs

- `knowledge/subsystems/libpq-frontend.md` — full libpq surface.
- `knowledge/files/src/test/examples/testlibpq.c.md` — minimal client.
- `knowledge/files/src/test/examples/testlibpq4.c.md` — multiple connections.
