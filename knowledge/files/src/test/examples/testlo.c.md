---
path: src/test/examples/testlo.c
anchor_sha: e18b0cb7344
loc: 270
depth: read
---

# src/test/examples/testlo.c

## Purpose

Demonstrates the libpq **large objects (LO) API** with 32-bit offsets:
`lo_creat`, `lo_open`, `lo_read`, `lo_write`, `lo_lseek`, `lo_close`,
`lo_unlink`, plus the import/export convenience wrappers `lo_import` /
`lo_export`. Reads an OS file into a Postgres large object, reads it
back out to another OS file, and unlinks the LO. The program is the
textbook reference quoted in the SGML chapter on large objects.
`[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `static Oid importFile(PGconn *conn, char *filename)` | `testlo.c:33-` | OS file → LO, returns OID |
| `static void pickout(PGconn *conn, Oid lobjId, int start, int len)` | later | random-access read demo |
| `static void overwrite(PGconn *conn, Oid lobjId, int start, int len)` | later | random-access write demo |
| `static void exportFile(PGconn *conn, Oid lobjId, char *filename)` | later | LO → OS file |
| `int main(int argc, char **argv)` | end | orchestrates demo |

## Internal landmarks

- Includes `<libpq/libpq-fs.h>` (`:24`) for `INV_READ` / `INV_WRITE`
  flag constants. Without these flags `lo_open` will fail.
- All LO operations must run inside a transaction. The driver wraps
  the demo work in BEGIN ... COMMIT.
- `BUFSIZE` = 1024 (`:26`) chunks I/O — LO read/write is byte-oriented
  but you choose the chunk size.

## Invariants & gotchas

- **Transaction required.** `lo_open` returns a handle valid only
  within the current transaction; using it after COMMIT is an error.
- Offsets in this file are 32-bit `int` (`lo_lseek`, etc.). For LOs
  larger than 2 GB use the 64-bit API in `testlo64.c`
  (`lo_lseek64`, `lo_tell64`, `lo_truncate64`).
- Shipped example, not a regression test. The `lo` contrib module
  exercises the API in tests; this file is for documentation.

## Cross-refs

- `knowledge/files/src/test/examples/testlo64.c.md` — 64-bit variant.
- `knowledge/subsystems/large-objects.md` — backend-side LO storage.
- `doc/src/sgml/lobj.sgml` — the chapter this is quoted in.
