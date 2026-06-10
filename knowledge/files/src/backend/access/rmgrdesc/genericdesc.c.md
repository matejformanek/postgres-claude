---
path: src/backend/access/rmgrdesc/genericdesc.c
anchor_sha: 4b0bf0788b0
loc: 55
depth: read
---

# genericdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/genericdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 55

## Purpose

rmgr descriptor routines for the Generic WAL resource manager
(`RM_GENERIC_ID`, records from `access/transam/generic_xlog.c`). Generic
WAL is the page-delta mechanism extensions use without a custom rmgr;
this descriptor renders the list of overwritten `(offset, length)`
regions for `pg_waldump`. [from-comment, genericdesc.c:3-4, 19-22]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `generic_desc(buf, record)` | `genericdesc.c:23` | render the delta region list |
| `generic_identify(info)` | `genericdesc.c:51` | always returns `"Generic"` |

## Invariants & gotchas

- **The record body is a self-delimiting stream of `(offset, length,
  payload)` triples.** `generic_desc` walks `ptr` from
  `XLogRecGetData` to `data + XLogRecGetDataLen`, reading an
  `OffsetNumber offset`, an `OffsetNumber length`, then skipping
  `length` payload bytes (genericdesc.c:29-38). It prints only the
  `offset`/`length` pair, not the payload. The trailing-separator logic
  (`; ` between, none after) keys on whether `ptr < end` after the skip.
- **`generic_identify` ignores `info` entirely** (genericdesc.c:51) —
  Generic WAL has no sub-opcodes, so every record identifies as
  `"Generic"`. This is the only descriptor that returns a constant.
  `[from-comment, genericdesc.c:47-49]`
- **Length math trusts the record.** A corrupt `length` larger than the
  remaining body would advance `ptr` past `end` and terminate the loop;
  no bounds check beyond the `ptr < end` loop guard. Benign for a
  read-only renderer over backend-written WAL.

## Cross-refs

- The Generic WAL writer + `MAX_GENERIC_XLOG_PAGES`:
  `[[src/include/access/generic_xlog.h]]`,
  `source/src/backend/access/transam/generic_xlog.c`.
- WAL skill §"Generic WAL — short form":
  `.claude/skills/wal-and-xlog/SKILL.md`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
