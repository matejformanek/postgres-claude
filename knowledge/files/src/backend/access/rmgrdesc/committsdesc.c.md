---
path: src/backend/access/rmgrdesc/committsdesc.c
anchor_sha: 4b0bf0788b0
loc: 54
depth: read
---

# committsdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/committsdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 54

## Purpose

rmgr descriptor routines for the commit-timestamp resource manager
(`RM_COMMIT_TS_ID`, records from `access/transam/commit_ts.c`). Renders
the 2 commit_ts WAL opcodes — SLRU page zeroing and SLRU truncation —
for `pg_waldump`. [from-comment, committsdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `commit_ts_desc(buf, record)` | `committsdesc.c:20` | render one commit_ts record |
| `commit_ts_identify(info)` | `committsdesc.c:42` | opcode → short name |

## Invariants & gotchas

- **`ZEROPAGE` pageno is read by `memcpy` into `int64`**
  (committsdesc.c:28-31), not a struct cast — the record body is a bare
  64-bit page number. The `TRUNCATE` case casts to
  `xl_commit_ts_truncate` and prints `pageno` (`int64`/`PRId64`) +
  `oldestXid`. `[verified-by-code]`
- **`commit_ts_identify` switches on raw `info`** (committsdesc.c:45),
  *not* `info & ~XLR_INFO_MASK` like most siblings — harmless here
  because both opcode values fit below the masked bits, but it is the
  odd one out in this directory. Has an explicit `default: return NULL`.

## Cross-refs

- `xl_commit_ts_truncate`, `COMMIT_TS_ZEROPAGE` / `COMMIT_TS_TRUNCATE`:
  `[[src/include/access/commit_ts.h]]`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.

## Potential issues

- **[ISSUE-style: identify switches on unmasked info]**
  `committsdesc.c:45` — `commit_ts_identify` switches on `info`
  directly while every other descriptor in the directory masks with
  `~XLR_INFO_MASK` first. Currently correct (opcodes don't collide with
  the info bits) but inconsistent; a future opcode could break it.
  Severity `nit`. Mirrored to `knowledge/issues/access-rmgrdesc.md`.
