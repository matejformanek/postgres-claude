---
path: src/backend/access/rmgrdesc/clogdesc.c
anchor_sha: 4b0bf0788b0
loc: 59
depth: read
---

# clogdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/clogdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 59

## Purpose

rmgr descriptor routines for `RM_CLOG_ID` (`access/transam/clog.c`) —
the commit-log (transaction-status SLRU). Renders the two CLOG WAL
records: zero-a-new-page and truncate. [from-comment, clogdesc.c:1-17]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `clog_desc(buf, record)` | `clogdesc.c:20` | render `CLOG_ZEROPAGE` (page no) or `CLOG_TRUNCATE` (page + oldestXact) |
| `clog_identify(info)` | `clogdesc.c:43` | opcode → "ZEROPAGE"/"TRUNCATE" |

## Invariants & gotchas

- **`pageno` is `int64`** (clogdesc.c:28, `%PRId64`) — the CLOG page
  number widened to 64-bit with the 64-bit-xid groundwork; the
  `xl_clog_truncate` record carries both the page and the `oldestXact`
  bound used to drive segment removal.
- **Only two record types exist** — CLOG status-bit updates are *not*
  individually WAL-logged (they're protected by the commit record +
  the SLRU's own fsync); only page-zeroing and truncation are. A reader
  expecting per-xid CLOG WAL records is mistaken.

## Cross-refs

- Record struct: `src/include/access/clog.h` (`xl_clog_truncate`).
- Backend redo: `clog.c::clog_redo`.
- Sibling status-log: `commit_ts` (`committsdesc.c`), `multixact`
  (`mxactdesc.c`) — all SLRU-backed.
- SLRU subsystem: `knowledge/subsystems/access-transam.md`.

## Tally

`[verified-by-code]=2 [from-comment]=1 [inferred]=1`
