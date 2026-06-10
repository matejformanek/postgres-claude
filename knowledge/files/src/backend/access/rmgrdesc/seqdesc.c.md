---
path: src/backend/access/rmgrdesc/seqdesc.c
anchor_sha: 4b0bf0788b0
loc: 46
depth: read
---

# seqdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/seqdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 46

## Purpose

rmgr descriptor routines for the sequence resource manager
(`RM_SEQ_ID`, records from `commands/sequence.c`). Renders the single
`XLOG_SEQ_LOG` opcode — a sequence's pre-logged value cache flush — for
`pg_waldump`. [from-comment, seqdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `seq_desc(buf, record)` | `seqdesc.c:20` | render the sequence record |
| `seq_identify(info)` | `seqdesc.c:33` | opcode → `"LOG"` or `NULL` |

## Invariants & gotchas

- **One opcode.** `seq_desc` prints the relation locator
  `spcOid/dbOid/relNumber` from `xl_seq_rec` (seqdesc.c:28). The
  sequence tuple itself trails the struct and isn't rendered.
- **`xlrec` is cast before the opcode check** (seqdesc.c:25) — the cast
  happens unconditionally, then `appendStringInfo` runs only
  `if (info == XLOG_SEQ_LOG)`. Harmless (no deref before the guard) but
  slightly unusual ordering. `[from-code]`

## Cross-refs

- `xl_seq_rec` + `XLOG_SEQ_LOG`:
  `[[src/include/commands/sequence_xlog.h]]`.
- The sequence engine: `source/src/backend/commands/sequence.c`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
