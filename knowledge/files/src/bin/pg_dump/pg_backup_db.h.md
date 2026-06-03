---
path: src/bin/pg_dump/pg_backup_db.h
anchor_sha: 4b0bf0788b0
loc: 26
depth: shallow
---

# pg_backup_db.h

- **Source path:** `source/src/bin/pg_dump/pg_backup_db.h`
- **Lines:** 26
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_backup_db.c` (implementation), `pg_backup.h` (the `Archive` it takes as receiver).

## Purpose

Tiny public header that exposes the wrapper SQL execution and transaction primitives used by pg_dump and pg_restore. Everything here takes `Archive *` (cast to `ArchiveHandle *` internally) so callers don't need the private header. [verified-by-code, pg_backup_db.h:14-25]

## Public surface

- `ExecuteSqlCommandBuf(Archive *, const char *buf, size_t bufLen)` — main entry from `ahwrite()` when restoring direct-to-DB; routes to ExecuteSqlCommand / ExecuteSimpleCommands / PQputCopyData depending on `AH->outputKind`. [verified-by-code, pg_backup_db.h:14; pg_backup_db.c:383-433]
- `ExecuteSqlStatement(Archive *, const char *query)` — exec + check PGRES_COMMAND_OK; pg_fatal otherwise. [verified-by-code, pg_backup_db.h:16]
- `ExecuteSqlQuery(Archive *, const char *query, ExecStatusType status)` — exec with caller-supplied expected status. [verified-by-code, pg_backup_db.h:17-18]
- `ExecuteSqlQueryForSingleRow(Archive *, const char *query)` — wraps `ExecuteSqlQuery(.., PGRES_TUPLES_OK)` and pg_fatals unless exactly one row. [verified-by-code, pg_backup_db.h:19]
- `EndDBCopyMode(Archive *, const char *tocEntryTag)` — sends PQputCopyEnd, drains any extra results, clears `pgCopyIn`. [verified-by-code, pg_backup_db.h:21]
- `StartTransaction(Archive *)` / `CommitTransaction(Archive *)` — both wrap `ExecuteSqlCommand(AH, "BEGIN"/"COMMIT", …)`. [verified-by-code, pg_backup_db.h:23-24]

## Phase D notes

No credential-bearing types here; the password lives in `ArchiveHandle.savedPassword` and `ConnParams.dbname`, both in `pg_backup_archiver.h` / `pg_backup.h`. This header is a clean SQL-execution boundary. `[fine]`

## Confidence tag tally
`[verified-by-code]=7 [fine]=1`
