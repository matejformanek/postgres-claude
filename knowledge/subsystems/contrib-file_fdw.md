# contrib-file_fdw (CSV / text file as foreign table)

- **Source path:** `source/contrib/file_fdw/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `file_fdw.control`)
- **Trusted:** no (foreign-data wrappers grant access to
  filesystem)

## 1. Purpose

Expose a file on the server's filesystem as a foreign table.
SELECT queries against the table parse the file (CSV / text /
binary) using COPY's underlying reader. The **reference
implementation** of the Foreign Data Wrapper (FDW) interface
for non-network sources — every FDW author looks here first
for "how is the API supposed to work?"

Use cases:
- Read CSVs into queries without a separate ETL step.
- Treat log files as queryable tables.
- Bridge between PG and tools that emit/consume CSV.

## 2. The FDW interface — 5 callbacks for read-only

[verified-by-code `file_fdw.c:186-191`]

```c
fdwroutine->GetForeignRelSize  = fileGetForeignRelSize;
fdwroutine->GetForeignPaths    = fileGetForeignPaths;
fdwroutine->GetForeignPlan     = fileGetForeignPlan;
fdwroutine->BeginForeignScan   = fileBeginForeignScan;
fdwroutine->IterateForeignScan = fileIterateForeignScan;
fdwroutine->EndForeignScan     = fileEndForeignScan;
fdwroutine->ReScanForeignScan  = fileReScanForeignScan;
```

The minimum read-only FDW needs these 7 (file_fdw has them
all). Write support (`AddForeignUpdateTargets`,
`PlanForeignModify`, etc.) is absent — file_fdw is
read-only.

## 3. The planner-time callbacks

[verified-by-code `file_fdw.c:131-145`]

- **`GetForeignRelSize`** — estimate row count + width.
  Reads the file metadata (stat for size) and estimates.
- **`GetForeignPaths`** — generate ForeignPath alternatives.
  file_fdw only generates one (no parallelism, no pushdown).
- **`GetForeignPlan`** — finalize the Path → Plan; serialize
  any state needed for execution.

For "what selectivity does this scan have?" the FDW returns
rough estimates; the planner uses them to decide if the
foreign scan is the cheapest path.

## 4. The executor-time callbacks

- **`BeginForeignScan`** — open the file, set up the parse
  state.
- **`IterateForeignScan`** — read one row, convert to
  TupleTableSlot, return it. Called per row by the executor.
- **`EndForeignScan`** — close the file, release resources.
- **`ReScanForeignScan`** — rewind to the start (for nested
  loop joins or similar).

The iterate function is where the COPY parser does the per-
row work. file_fdw shares parsing code with the `COPY FROM`
command.

## 5. SQL setup

```sql
CREATE EXTENSION file_fdw;
CREATE SERVER my_server FOREIGN DATA WRAPPER file_fdw;
CREATE FOREIGN TABLE logs (
    ts timestamp,
    level text,
    message text
) SERVER my_server
OPTIONS (filename '/var/log/myapp.log',
         format 'csv',
         header 'true');
```

Options recognized:
- `filename` — required, server-side file path.
- `program` — alternative; output of a shell command as
  input.
- `format` — `csv` (default) / `text` / `binary`.
- `header` — skip first row.
- `delimiter`, `null`, `quote`, `escape`, `encoding`,
  `force_not_null`, `force_null` — match COPY's options.

[validated by `file_fdw_validator` in file_fdw.c]

## 6. Security model

- **The path is server-side**, not client-side. The file
  must exist on the database server.
- **`pg_read_server_files`** role is required to create
  foreign tables with a `filename` option.
- **`pg_execute_server_program`** required for `program`
  option.
- Without these roles, only superusers can create file_fdw
  tables.

This is the "FDW with filesystem access requires server-
privilege" model.

## 7. Performance characteristics

- **No indexing.** Every query is a sequential scan of the
  entire file.
- **No row-count caching.** `GetForeignRelSize` estimates
  from file size, which may be inaccurate for variable-length
  rows.
- **No pushdown.** WHERE clauses are applied after rows are
  returned; the scan reads the whole file even for
  `WHERE id = 1`.
- **No parallel scan.** Single-process read.

For "treat a file as queryable," file_fdw is fine. For
"join a large file against a table," materialize the file
into a real table first.

## 8. Production-use guidance

- **Don't use for hot queries.** Every query re-parses the
  file.
- **Use for one-off ETL** — `INSERT INTO real_table SELECT *
  FROM file_table;`.
- **For non-CSV formats** (JSON, Parquet, Avro), use a
  dedicated FDW (e.g., `parquet_fdw`).
- **The `program` option is a security risk** if non-
  superusers can configure servers; restrict via the role
  grants above.

## 9. Invariants

- **[INV-1]** Read-only; no INSERT / UPDATE / DELETE.
- **[INV-2]** No pushdown; WHERE applied post-scan.
- **[INV-3]** Path is server-side; client filesystem
  irrelevant.
- **[INV-4]** Uses COPY's parsing code; same option set.
- **[INV-5]** Requires `pg_read_server_files` (or superuser)
  for filename option.

## 10. Useful greps

- The FDW callback registration:
  `grep -n 'fdwroutine->' source/contrib/file_fdw/file_fdw.c`
- The COPY parser integration:
  `grep -n 'BeginCopyFrom\|NextCopyFrom\|EndCopyFrom' source/contrib/file_fdw/file_fdw.c`
- The validator:
  `grep -n 'file_fdw_validator\|ProcessCopyOptions' source/contrib/file_fdw/file_fdw.c`

## 11. Cross-references

- `knowledge/subsystems/foreign.md` — the FDW subsystem at
  large.
- `knowledge/subsystems/contrib-postgres_fdw.md` — sister
  contrib for network-attached PG databases; uses the same
  FDW interface.
- `.claude/skills/executor-and-planner/SKILL.md` — Path → Plan
  + ForeignScanState integration.
- `source/src/include/foreign/fdwapi.h` — the FDW API.
- `source/src/backend/commands/copyfromparse.c` — the
  underlying CSV / text parser file_fdw uses.
- `source/contrib/file_fdw/file_fdw.c` — implementation
  (1340 LOC).

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/file_fdw/file_fdw.c`](../files/contrib/file_fdw/file_fdw.c.md) |

<!-- /files-owned:auto -->
