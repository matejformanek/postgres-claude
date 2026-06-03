---
path: src/bin/pg_dump/connectdb.h
anchor_sha: 4b0bf0788b0
loc: 26
depth: read
---

# connectdb.h

- **Source path:** `source/src/bin/pg_dump/connectdb.h`
- **Lines:** 26
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `connectdb.c` (the two implementations), `pg_backup.h` (`trivalue` enum), `pg_backup_utils.h` (declares `exit_nicely`, used implicitly via `pg_fatal`).

## Purpose

Declares the two extern functions implemented in `connectdb.c`. Twelve-line header with one prototype each. [verified-by-code, connectdb.h:14-26]

## Public surface

- `ConnectDatabase` — twelve arguments: `dbname`, `connection_string`, `pghost`, `pgport`, `pguser`, `prompt_password` (`trivalue`), `fail_on_error`, `progname`, `**connstr` (out, optional), `*server_version` (out, optional), `*password` (in/out, optional — initial password and where to stash a prompted one), `*override_dbname` (in, optional). [verified-by-code, connectdb.h:20-24]
- `executeQuery(conn, query)` — for read-only SELECT-style queries that should pg_fatal on failure. [verified-by-code, connectdb.h:25]

## Why a separate header

`pg_dumpall` connects to a sequence of databases without a full `ArchiveHandle`; the heavier `pg_backup_db.c::ConnectDatabase` family inside pg_dump proper would drag in the entire Archive machinery. This header keeps the dumpall-style flow in its own translation unit. [inferred, connectdb.c:1-12]

## Phase D — surfaces of concern

- **No `pg_attribute_format` annotation on `executeQuery`** — the query string is passed as `const char *` and `pg_fatal` is invoked on the result, but the format-string concern lives at every call site (callers must build the query with `appendPQExpBuffer(... %s ..., fmtId(...))`). [verified-by-code, connectdb.h:25] [no concern]
- **`*password` aliasing.** The signature lets the caller hand in a previously-prompted password by value; the implementation may write a freshly-prompted one back via the same pointer (see connectdb.c:53-56, 165). Callers that pass a NULL pointer for password but `prompt_password == TRI_YES` will get a fresh prompt every retry. [inferred] [maybe]

## Cross-references

- Implementation: `knowledge/files/src/bin/pg_dump/connectdb.c.md`.
- Direct includes: `pg_backup.h` for `trivalue`, `pg_backup_utils.h` (which brings in `common/logging.h`).

## Confidence tag tally
`[verified-by-code]=3 [inferred]=2 [maybe]=1`
