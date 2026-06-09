---
path: src/backend/access/rmgrdesc/spgdesc.c
anchor_sha: 4b0bf0788b0
loc: 165
depth: deep
---

# spgdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/spgdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 165

## Purpose

rmgr descriptor routines for the SP-GiST resource manager
(`RM_SPGIST_ID`, records from `access/spgist/spgxlog.c` /
`access/spgxlog.h`). Renders the 8 SP-GiST WAL opcodes — add-leaf,
move-leafs, add-node, split-tuple, picksplit, and the three vacuum
variants — for `pg_waldump`. [from-comment, spgdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `spg_desc(buf, record)` | `spgdesc.c:19` | render one SP-GiST record |
| `spg_identify(info)` | `spgdesc.c:131` | opcode → short name |

## Internal landmarks

- Pure switch-on-`info`; each case prints offsets (`offnumLeaf`,
  `offnumParent`, `nodeI`, etc.) and appends parenthetical flag
  strings — `(newpage)`, `(nulls)`, `(replacedead)`,
  `(innerIsParent)`, `(isRootSplit)`, `(same)` — gated on the matching
  bool fields. The `VACUUM_REDIRECT` case (spgdesc.c:117) is the one
  carrying a `snapshotConflictHorizon` (standby conflict horizon for
  placeholder reclamation).

## Invariants & gotchas

- **Flag suffixes are append-only, order-fixed** — e.g. ADD_LEAF prints
  `(newpage)` before `(nulls)` (spgdesc.c:34-37). The text layout is a
  de-facto interface for anyone grepping `pg_waldump` output.
- **No `default:`** — unknown opcode → empty string; `spg_identify`
  returns `NULL` for unknowns.

## Cross-refs

- Record structs + `XLOG_SPGIST_*` opcodes:
  `[[src/include/access/spgxlog.h]]`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
