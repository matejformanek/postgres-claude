---
path: src/backend/access/rmgrdesc/dbasedesc.c
anchor_sha: 4b0bf0788b0
loc: 75
depth: read
---

# dbasedesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/dbasedesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 75

## Purpose

rmgr descriptor routines for the database resource manager
(`RM_DBASE_ID`, records from `commands/dbcommands.c`). Renders the 3
`CREATE DATABASE` / `DROP DATABASE` WAL opcodes — the two create
strategies (file-copy vs WAL-log) and drop — for `pg_waldump`.
[from-comment, dbasedesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `dbase_desc(buf, record)` | `dbasedesc.c:21` | render one dbase record |
| `dbase_identify(info)` | `dbasedesc.c:56` | opcode → short name |

## Invariants & gotchas

- **Two create opcodes mirror the two `CREATE DATABASE` strategies:**
  `XLOG_DBASE_CREATE_FILE_COPY` (the `STRATEGY = file_copy` path, prints
  `copy dir src→dst`) and `XLOG_DBASE_CREATE_WAL_LOG` (the
  `STRATEGY = wal_log` default, prints `create dir`). `[from-code]`
- **`XLOG_DBASE_DROP` loops over `ntablespaces`** (dbasedesc.c:50),
  printing one `tablespace/db` pair per tablespace the dropped database
  occupied — a database can have storage in multiple tablespaces.
- **`dbase_desc` is an `if/else if` chain, no final else** — unknown
  opcode → empty string; `dbase_identify` returns `NULL` for unknowns.

## Cross-refs

- `xl_dbase_create_*` / `xl_dbase_drop_rec` records + `XLOG_DBASE_*`:
  `[[src/include/commands/dbcommands_xlog.h]]`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
