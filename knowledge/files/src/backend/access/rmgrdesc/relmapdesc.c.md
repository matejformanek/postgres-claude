---
path: src/backend/access/rmgrdesc/relmapdesc.c
anchor_sha: 4b0bf0788b0
loc: 47
depth: read
---

# relmapdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/relmapdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 47

## Purpose

rmgr descriptor routines for the relation-map resource manager
(`RM_RELMAP_ID`, records from `utils/cache/relmapper.c`). Renders the
single `XLOG_RELMAP_UPDATE` opcode — a rewrite of a database's (or the
shared) relation map file that tracks the physical filenode of
nailed/mapped catalogs — for `pg_waldump`. [from-comment, relmapdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `relmap_desc(buf, record)` | `relmapdesc.c:19` | render the relmap update |
| `relmap_identify(info)` | `relmapdesc.c:34` | opcode → `"UPDATE"` or `NULL` |

## Invariants & gotchas

- **One opcode only.** `relmap_desc` prints `database`, `tablespace`,
  and `size` (bytes) from `xl_relmap_update` (relmapdesc.c:29). The
  actual map payload trails the struct and is not rendered.
- **`dbid == 0` means the shared map** — not visible in the desc text
  (it just prints whatever `dbid` is), but a `database 0` line denotes
  the cluster-wide shared relation map. `[inferred]`

## Cross-refs

- `xl_relmap_update` + `XLOG_RELMAP_UPDATE`:
  `[[src/include/utils/relmapper.h]]`.
- The relmapper engine: `source/src/backend/utils/cache/relmapper.c`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
