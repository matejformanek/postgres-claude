---
source_url: https://www.postgresql.org/docs/current/pgwalinspect.html
fetched_at: 2026-06-23T00:00:00Z
anchor_sha: 9a60f295bcb1
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pg_walinspect (WAL inspection via SQL)

`pg_walinspect` is `pg_waldump` exposed as SQL functions — same `xlogreader` +
per-rmgr decode machinery, but queryable on a live server without shelling out.
The canonical use for a backend hacker: confirm exactly what WAL a code path
emits (resource manager, record type, FPI presence, block refs) right after
running a statement. Default access is **superuser or the `pg_read_server_files`
role**; superusers can `GRANT EXECUTE` to others. All functions decode against
the server's **current timeline ID**. `[from-docs]`

## Per-record / per-range info

- `pg_get_wal_record_info(in_lsn pg_lsn) returns record` — one record. If
  `in_lsn` is not exactly at a record boundary, it returns the **next** valid
  record (and errors if none exists). Columns: `start_lsn, end_lsn, prev_lsn,
  xid, resource_manager, record_type, record_length, main_data_length,
  fpi_length, description, block_ref`. `[from-docs]`
- `pg_get_wal_records_info(start_lsn pg_lsn, end_lsn pg_lsn) returns setof
  record` — all valid records in `[start_lsn, end_lsn]`, same columns, one row
  each. Errors if `start_lsn` is unavailable; **permissively accepts an
  `end_lsn` past the server's current LSN**. Idiom: pass
  `'FFFFFFFF/FFFFFFFF'` as `end_lsn` to mean "current LSN". `[from-docs]`
  (An older `*_till_end_of_wal` variant did exactly this; the
  `FFFFFFFF/FFFFFFFF` sentinel is the current spelling.)

## Per-block info — the unnested view

- `pg_get_wal_block_info(start_lsn, end_lsn, show_data boolean DEFAULT true)
  returns setof record` **unnests block references**: one row per
  `(record, block_id)`. Records with no registered blocks (e.g. `COMMIT`)
  produce **no rows** — so this can return *fewer* rows than
  `pg_get_wal_records_info` over the same range. Rows are unique on
  `(start_lsn, block_id)`. `[from-docs]`
- Block-locating columns map straight to catalogs:
  `reltablespace → pg_tablespace.oid`, `reldatabase → pg_database.oid`,
  `relfilenode → pg_class.relfilenode`, `relforknumber → ` fork number
  (`source/src/common/relpath.h`), plus `relblocknumber`. `[from-docs]`
- Payload columns: `block_data_length, block_fpi_length, block_fpi_info,
  block_data, block_fpi_data` (the full-page image, when one was logged).
  Passing `show_data = false` NULLs out `block_data`/`block_fpi_data` to avoid
  materializing the heavy bytea — use it when you only want the metadata.
  `[from-docs]`

## Aggregate stats

- `pg_get_wal_stats(start_lsn, end_lsn, per_record boolean DEFAULT false)
  returns setof record` — WAL volume breakdown. Default: one row per
  `resource_manager`. `per_record = true`: one row per `record_type`.
  Columns: a label column, `count, count_percentage, record_size,
  record_size_percentage, fpi_size, fpi_size_percentage, combined_size,
  combined_size_percentage`. This is the SQL way to answer "where is my WAL
  going — which rmgr, how much of it is FPIs?". `[from-docs]`

## Footguns worth knowing

- **LSN-after vs LSN-at**: functions expect the record *start* LSN, but several
  producers (e.g. `pg_logical_emit_message`) hand back the LSN *after* the
  insertion — feeding that straight in lands you on the next record. `[from-docs]`
- FPI accounting is the practical reason to reach for `pg_get_wal_stats`:
  `full_page_writes` + a checkpoint can balloon WAL with full-page images, and
  the `fpi_size_percentage` column makes that visible per rmgr. `[inferred]`

## Links into corpus

- WAL record structure / rmgr decode: [docs-distilled/wal-internals.md](./wal-internals.md)
- WAL intro + reliability: [docs-distilled/wal-intro.md](./wal-intro.md), [docs-distilled/wal-reliability.md](./wal-reliability.md)
- Custom resource managers (own `rm_desc`): [docs-distilled/custom-rmgr.md](./custom-rmgr.md)
- WAL for extensions / generic WAL: [docs-distilled/wal-for-extensions.md](./wal-for-extensions.md), [docs-distilled/generic-wal.md](./generic-wal.md)
- Relevant skills: `wal-and-xlog` (the XLogInsert/redo side this inspects),
  `debugging`. pg_walinspect is the SQL counterpart to the `pg_waldump` CLI the
  `wal-and-xlog` skill describes.
