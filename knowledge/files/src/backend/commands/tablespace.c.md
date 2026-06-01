# tablespace.c

- **Source path:** `source/src/backend/commands/tablespace.c`
- **Lines:** 1583
- **Last verified commit:** `ef6a95c7c64`

## Purpose

CREATE / DROP / RENAME / ALTER TABLESPACE plus the runtime helpers `default_tablespace` / `temp_tablespaces` GUC handling. The top-of-file comment is the **canonical authoritative explanation** of the symlink/path layout: [from-comment, tablespace.c:3-44]

- A tablespace = a directory on disk.
- Per-cluster `$PGDATA/pg_tblspc/<spcoid>` symlink points to the user-supplied location.
- Inside that, per-cluster version subdir `PG_<MAJOR>_<CATVER>` so multiple PG versions can share a tablespace mount.
- Inside that, per-DB subdir `<dboid>` containing relfilenodes.
- Full path: `$PGDATA/pg_tblspc/spcoid/PG_<MAJORVER>_<CATVER>/dboid/relfilenumber`.

The two initdb-time tablespaces `pg_global` (shared catalogs at `$PGDATA/global/`) and `pg_default` (`$PGDATA/base/dboid/`) are accessed specially — no `pg_tblspc` symlink, accessed at the listed paths directly, so a cluster works on platforms without symlinks if only the defaults are used.

## Public surface

- `CreateTableSpace` — validate target dir is empty, create the symlink, emit `xl_tblspc_create_rec` WAL.
- `DropTableSpace` — verify no objects remain via a catalog scan, then unlink files. The check is racy without an exclusive lock; that lock is taken on the tablespace OID.
- `RenameTableSpace` — pg_tablespace rename only; no file motion.
- `AlterTableSpaceOptions` — set `seq_page_cost`/`random_page_cost`/`effective_io_concurrency` per-tablespace overrides.
- `tblspc_redo` — WAL redo for create/drop.
- `PrepareTempTablespaces` — runtime: at session start, parse `temp_tablespaces` GUC into a usable Oid list.
- `GetDefaultTablespace` — runtime resolution of `default_tablespace` (returns InvalidOid → use database's default).

## In-place tablespaces

The dev-only `allow_in_place_tablespaces` GUC (PG 15+) creates a tablespace as a directory **inside** `$PGDATA/pg_tblspc/` rather than at an external location, which makes recovery / pg_rewind / pg_basebackup tests much simpler. Production users must not use this.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=2`
