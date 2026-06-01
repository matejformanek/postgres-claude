# dbcommands.c

- **Source path:** `source/src/backend/commands/dbcommands.c`
- **Lines:** 3470
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `commands/dbcommands.h`, `commands/dbcommands_xlog.h`, `catalog/pg_database.h`, `storage/copydir.c`, `commands/tablespace.c`.

## Purpose

"Database management commands (create/drop database). … Database creation/destruction commands use **exclusive locks on the database objects** (`LockSharedObject`) to avoid stepping on each others' toes. Formerly we used table-level locks on pg_database, but that's too coarse-grained." [from-comment, dbcommands.c:3-9]

## Public surface

- `createdb` — CREATE DATABASE. Two strategies: **WAL_LOG** (default since PG 15; copies template DB block-by-block, emitting WAL for each block — recovery-safe, doesn't need a checkpoint) and **FILE_COPY** (the historical method; uses OS file copy after forcing a checkpoint so the template's dirty buffers are flushed, then issues `XLOG_DBASE_CREATE_FILE_COPY`). Strategy controlled by `STRATEGY = WAL_LOG | FILE_COPY`.
- `dropdb` (with `force`) — DROP DATABASE [WITH FORCE]; with FORCE, terminate other backends connected to the target DB via `TerminateOtherDBBackends` before unlinking files.
- `DropDatabase` — wrapper from utility.
- `RenameDatabase`, `AlterDatabase`, `AlterDatabaseRefreshColl`, `AlterDatabaseSet`, `AlterDatabaseOwner` — straightforward catalog mutators.
- `have_createdb_privilege` — the CREATEDB-role check.
- WAL redo: `dbase_redo` handles `XLOG_DBASE_CREATE_FILE_COPY`, `XLOG_DBASE_CREATE_WAL_LOG`, `XLOG_DBASE_DROP` (in `dbcommands_xlog.h`).

## Locking model [from-comment]

CREATE/DROP/RENAME take an exclusive `LockSharedObject(DatabaseRelationId, dboid, 0, AccessExclusiveLock)` on the database itself, NOT a table lock on `pg_database`. This means concurrent CREATEs of *different* DBs proceed in parallel; only operations targeting the same DB OID block. New connections to a DB take `LockSharedObject(..., RowExclusiveLock)` (in `InitPostgres`), so DROP must wait for them.

## Recovery & file-layout

The file-layout walker for CREATE DATABASE WAL_LOG (recursive `CreateDirAndVersionFile` + per-fork `RelationCopyStorageUsingBuffer`) is here; it walks every relation in the template DB and emits standard WAL records. Recovery on a standby is therefore identical to recovering normal DDL. The FILE_COPY path emits a single `xl_dbase_create_file_copy_rec` and the standby OS-copies the directory at redo time.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
