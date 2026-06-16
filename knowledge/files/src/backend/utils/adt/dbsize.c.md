# src/backend/utils/adt/dbsize.c

## Purpose

Size-reporting SQL functions: `pg_database_size`, `pg_tablespace_size`,
`pg_relation_size`, `pg_table_size`, `pg_indexes_size`,
`pg_total_relation_size`, plus formatting helpers `pg_size_pretty`,
`pg_size_bytes`. All implemented by walking the on-disk directory tree with
`AllocateDir`/`stat(2)` rather than catalog metadata, so they include
TOAST, FSM, VM, init-fork files.

## Role in PG

- Pure SRF/scalar Datum entry points. Each accepts an OID (or name) and
  walks the data directory.
- File-by-file `stat` accumulation, treating `ENOENT` as zero (concurrent
  drop) and other errors as `ereport(ERROR, …)`.

## Key functions

Database/tablespace:
- `db_dir_size(path)` (`dbsize.c:73-112`) — sum of `st_size` over one dir;
  `AllocateDir` returning NULL → 0; `ENOENT` on individual stat → continue.
- `calculate_database_size(dbOid)` (`:117-165`) — **ACL gate** at
  `:131-137`: `object_aclcheck(DatabaseRelationId, dbOid, GetUserId(),
  ACL_CONNECT)` OR `has_privs_of_role(GetUserId(), ROLE_PG_READ_ALL_STATS)`.
  Sums `base/<dboid>` plus every `PG_TBLSPC_DIR/<sym>/<verdir>/<dboid>`.
  Comment notes "Shared storage in pg_global is not counted" (`:139`).
- `pg_database_size_oid` / `pg_database_size_name` (`:167-203`).
- `calculate_tablespace_size(tblspcOid)` (`:210-?`) — **ACL gate** at
  `:225-232`: bypassed if `tblspcOid == MyDatabaseTableSpace`,
  otherwise requires `ROLE_PG_READ_ALL_STATS` OR
  `object_aclcheck(TableSpaceRelationId, tblspcOid, GetUserId(),
  ACL_CREATE)`. Hardcoded paths for DEFAULTTABLESPACE_OID ("base"),
  GLOBALTABLESPACE_OID ("global").
- `pg_tablespace_size_oid` / `pg_tablespace_size_name` (`:280-323`).

Relation:
- `calculate_relation_size(rfn, backend, forknum)` (`:325-361`) — loops
  over segments `<path>`, `<path>.1`, `<path>.2`, … breaking on first
  ENOENT (`:350-351`).
- `pg_relation_size(oid, fork_text)` (`:363-394`) — `try_relation_open`
  with `AccessShareLock`; NULL return on already-dropped (`:380-381`).
  **Privilege gate is the relation lock** — `try_relation_open` does
  the standard ACL check.
- `calculate_toast_table_size` (`:395-?`).
- `calculate_table_size(rel)` (`:441`) and `calculate_indexes_size(rel)`
  (`:468`) — wrap `calculate_relation_size` over forks/indexes.
- `pg_table_size` / `pg_indexes_size` / `pg_total_relation_size`
  (`:503-585`).

Formatters:
- `pg_size_pretty(int8)` and `pg_size_pretty(numeric)` (`:587`) —
  walk a table of size-unit thresholds (`size_pretty_units[]`).
- `pg_size_bytes(text)` — parse `"4 kB"` and friends.

## State / globals

- Static const tables: `size_pretty_units[]` (`:49`), `size_bytes_aliases[]`
  (`:67`). No mutable state.

## Phase D notes

- **Three privilege models**:
  1. `pg_database_size` → CONNECT on database OR `pg_read_all_stats`
     membership. Caller can size *any* database they can CONNECT to.
  2. `pg_tablespace_size` → CREATE on tablespace OR `pg_read_all_stats`,
     with bypass for `MyDatabaseTableSpace` (anyone in this DB can
     size their default tablespace). Subtle: CREATE is a write
     privilege but here it's repurposed as "you have a stake in this
     tablespace, you can see its size".
  3. `pg_relation_size` / `pg_table_size` / etc. → standard relation
     ACL via `try_relation_open(AccessShareLock)` — caller must have
     SELECT (or some other privilege the lock implies).
- **stat-based**: never opens the file, so a permission error at the
  FS layer would surface as "could not stat" not "permission denied
  to read". stat(2) requires search on the directory chain — if
  postgres uid loses permission on a tablespace's directory mid-stat,
  caller sees a backend error. [from-comment + inferred]
- **Concurrent drop / segment removal**: ENOENT on individual files
  silently truncates the size at the boundary; per-segment loop
  breaks on first missing segment number (`:350-351`). A vacuum that
  drops trailing segments mid-walk under-counts but doesn't error.
- **Symlinks**: tablespaces live under `pg_tblspc/<oid>` as symlinks
  to the actual storage dir. `db_dir_size` follows them transparently
  via `stat(2)`.

## Potential issues

- [ISSUE-info-disclosure: `pg_database_size` gated on ACL_CONNECT —
  weak. Any role with login + CONNECT can size every database they
  can connect to, leaking growth-rate intel. (low, by design)]
- [ISSUE-correctness: `pg_relation_size` returns NULL for dropped
  relations (`:380-381`) but `pg_database_size` returns NULL only
  when size == 0 (`:184-185`). Inconsistent — a non-existent DB
  silently passes the SearchSysCacheExists1 gate only at OID
  variant; the name variant calls `get_database_oid(false)` which
  errors. Documented quirk (low)]
- [ISSUE-dos: `calculate_tablespace_size` walks the entire tablespace
  dir tree synchronously inside a backend; on a 100 TB tablespace
  this is many minutes of `stat()` traffic. No timeout / chunking.
  (low)]
- [ISSUE-trust-boundary: `ACL_CREATE` repurposed as "can read size of
  tablespace" feels semantically off — a role might be granted CREATE
  on a tablespace for one purpose and inadvertently leak its total
  size. Documented in comment `:220-223` (low, by design)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
