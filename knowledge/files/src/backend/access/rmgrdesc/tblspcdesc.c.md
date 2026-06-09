---
path: src/backend/access/rmgrdesc/tblspcdesc.c
anchor_sha: 4b0bf0788b0
loc: 56
depth: read
---

# tblspcdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/tblspcdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 56

## Purpose

rmgr descriptor routines for the tablespace resource manager
(`RM_TBLSPC_ID`, records from `commands/tablespace.c`). Renders the 2
tablespace WAL opcodes — CREATE (with its symlink target path) and DROP
— for `pg_waldump`. [from-comment, tblspcdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `tblspc_desc(buf, record)` | `tblspcdesc.c:20` | render one tablespace record |
| `tblspc_identify(info)` | `tblspcdesc.c:40` | opcode → short name |

## Invariants & gotchas

- **CREATE prints the tablespace OID + the on-disk path string**
  (tblspcdesc.c:30) — `ts_path` is the directory the tablespace symlink
  points at, rendered via `%s`. It is a superuser-supplied
  `CREATE TABLESPACE ... LOCATION '...'` path stored in the WAL record;
  rendered into `pg_waldump` text, not re-executed. DROP prints just the
  OID.
- **`tblspc_desc` is an `if/else if` chain, no final else** — unknown
  opcode → empty string; `tblspc_identify` returns `NULL` for unknowns.

## Cross-refs

- `xl_tblspc_create_rec` / `xl_tblspc_drop_rec` + `XLOG_TBLSPC_*`:
  `[[src/include/commands/tablespace.h]]`.
- The tablespace engine: `source/src/backend/commands/tablespace.c`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
