---
path: src/backend/access/rmgrdesc/mxactdesc.c
anchor_sha: 4b0bf0788b0
loc: 104
depth: deep
---

# mxactdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/mxactdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 104

## Purpose

rmgr descriptor routines for the MultiXact resource manager
(`RM_MULTIXACT_ID`, records from `access/transam/multixact.c`). Renders
the 4 multixact WAL opcodes — SLRU page zeroing (offsets/members),
multixact creation with its member list, and truncation — for
`pg_waldump`. [from-comment, mxactdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `multixact_desc(buf, record)` | `mxactdesc.c:49` | render one multixact record |
| `multixact_identify(info)` | `mxactdesc.c:82` | opcode → short name |

## Internal landmarks

- **`out_member` (mxactdesc.c:19)** — static helper printing one
  `MultiXactMember` as `xid (status)`, decoding the lock/update status
  enum (`MultiXactStatusForKeyShare` … `MultiXactStatusUpdate`) into the
  short tags `(keysh)`, `(sh)`, `(fornokeyupd)`, `(forupd)`,
  `(nokeyupd)`, `(upd)`. A `default:` prints `(unk)`.
- **`XLOG_MULTIXACT_CREATE_ID` (mxactdesc.c:63)** loops over
  `xlrec->nmembers`, calling `out_member` per entry — the only
  variable-length rendering here.

## Invariants & gotchas

- **Page numbers are 64-bit.** Both the ZERO_*_PAGE case (mxactdesc.c:58)
  and the offset field use `int64` / `PRIu64` — multixact offsets and
  SLRU page numbers widened to 64 bits; the desc reads `pageno` via
  `memcpy` (not a struct cast) because the record body is a bare
  `int64`. `[verified-by-code]`
- **`out_member` has a real `default:`** (unlike the desc/identify
  switches) — an unrecognized member status renders `(unk)` rather than
  silently dropping, since a corrupt status byte should still be visible
  in `pg_waldump`.
- **`multixact_desc` uses an `if/else if` chain with no final else** —
  unknown opcode → empty string; `multixact_identify` returns `NULL`.

## Cross-refs

- `MultiXactMember`, `MultiXactStatus`, `xl_multixact_*` records +
  `XLOG_MULTIXACT_*` opcodes: `[[src/include/access/multixact.h]]`.
- Subsystem doc: the multixact engine itself —
  `[[src/backend/access/transam/multixact.c]]` (already covered).
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
