---
path: src/backend/access/rmgrdesc/replorigindesc.c
anchor_sha: 4b0bf0788b0
loc: 62
depth: read
---

# replorigindesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/replorigindesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 62

## Purpose

rmgr descriptor routines for the replication-origin resource manager
(`RM_REPLORIGIN_ID`, records from `replication/logical/origin.c`).
Renders the 2 replication-origin WAL opcodes — SET (advance an origin's
remote LSN) and DROP — for `pg_waldump`. [from-comment, replorigindesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `replorigin_desc(buf, record)` | `replorigindesc.c:18` | render one replorigin record |
| `replorigin_identify(info)` | `replorigindesc.c:50` | opcode → short name |

## Invariants & gotchas

- **`XLOG_REPLORIGIN_SET` prints the LSN via `LSN_FORMAT_ARGS`**
  (replorigindesc.c:32) in the canonical `%X/%08X` form, plus the
  `node_id` and `force` flag. `XLOG_REPLORIGIN_DROP` prints just the
  `node_id`.
- **`replorigin_identify` switches on raw `info`** (replorigindesc.c:53),
  *not* `info & ~XLR_INFO_MASK` — shared with `committsdesc.c`'s
  identify. Harmless because the opcode values don't overlap the info
  bits, but inconsistent with the masked-form majority in this
  directory. Has an explicit `default: return NULL`.

## Cross-refs

- `xl_replorigin_set` / `xl_replorigin_drop` + `XLOG_REPLORIGIN_*`:
  `[[src/include/replication/origin.h]]`.
- Replication overview: `.claude/skills/replication-overview/SKILL.md`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
