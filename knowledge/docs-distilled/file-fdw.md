---
source_url: https://www.postgresql.org/docs/current/file-fdw.html
fetched_at: 2026-07-13T20:50:00Z
anchor_sha: d92e98340fcb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.16 file_fdw — access external data files"
maps_to_skill: fdw-development
---

# Docs distilled — file_fdw (an FDW that is a thin skin over COPY FROM)

The smallest complete `FdwRoutine` implementation in the tree, and the reason
it's such a clean teaching example: it does not talk to a remote database at
all — it reuses PostgreSQL's own **COPY machinery** to read a local file (or a
program's stdout) as a read-only foreign table. Sits at the intersection of
`fdw-development` and `copy-family`.

## Non-obvious claims

- **It literally is COPY.** `FileFdwExecutionState` carries a
  `CopyFromState cstate` [[file_fdw.c:119]], the scan opens the file with
  `BeginCopyFrom(NULL, …)` [[file_fdw.c:702]], and every option below is a
  pass-through to the corresponding COPY option. The `FdwRoutine` wires only the
  read path: `GetForeignRelSize` / `GetForeignPaths` / `GetForeignPlan` /
  `BeginForeignScan` / `IterateForeignScan` / `ReScanForeignScan` /
  `EndForeignScan` [[file_fdw.c:186]] — no `ExecForeignInsert` etc. because it's
  read-only. [verified-by-code @ d92e98340fcb]
- **`filename` and `program` are mutually exclusive**, and each has a distinct
  privilege gate. Reading a `filename` requires membership in
  `pg_read_server_files` [[file_fdw.c:294]]; running a `program` requires
  `pg_execute_server_program` [[file_fdw.c:303]] (or superuser in both cases).
  The `program` string is handed to a shell — the docs warn to use fixed command
  strings and escape untrusted input. [from-docs] + [verified-by-code @ d92e98340fcb]
- **Table-level options map 1:1 to COPY options:** `format` (text/csv/binary),
  `header`, `delimiter`, `quote`, `escape`, `null`, `default`, `encoding`,
  `on_error`, `reject_limit`, `log_verbosity`. Boolean options (e.g. `header`)
  must be written with an explicit `'true'` in FDW option syntax. [from-docs]
- **Column-level options exist too:** `force_not_null` and `force_null`
  (→ COPY `FORCE_NOT_NULL` / `FORCE_NULL`). `FORCE_QUOTE` is *not* supported
  (it's a write-side option and file_fdw is read-only). [from-docs]
- **`EXPLAIN` surfaces the file size.** Because `fileGetForeignRelSize`
  [[file_fdw.c:519]] stats the file to cost the scan, `EXPLAIN` on a file_fdw
  table shows the file name/program and its size in bytes (suppressed by
  `COSTS OFF`). [from-docs]
- **Read-only, and non-owners cannot change options.** No DML; option changes by
  regular users are "not implemented". [from-docs]

## Links into corpus

- [[knowledge/subsystems/contrib-file_fdw.md]] — the source-side companion.
- [[knowledge/docs-distilled/fdwhandler.md]] — the `FdwRoutine` callback set
  file_fdw partially fills.
- [[knowledge/docs-distilled/fdw-callbacks.md]] — the scan-callback contract
  (`BeginForeignScan`/`IterateForeignScan`/`EndForeignScan`).
- [[knowledge/idioms/tablesync-initial-copy.md]] — another consumer of the same
  COPY-FROM machinery, useful contrast for how COPY is reused across subsystems.

## Confidence

The COPY-reuse (`CopyFromState`/`BeginCopyFrom`), the `FdwRoutine` wiring, and
the two privilege-role gates are [verified-by-code @ d92e98340fcb] against
`contrib/file_fdw/file_fdw.c`. The full option→COPY mapping table, the
column-level options, and the EXPLAIN-size behavior are [from-docs].
