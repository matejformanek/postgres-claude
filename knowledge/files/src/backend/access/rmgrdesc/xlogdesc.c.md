---
path: src/backend/access/rmgrdesc/xlogdesc.c
anchor_sha: 4b0bf0788b0
loc: 425
depth: deep
---

# xlogdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/xlogdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 425

## Purpose

rmgr descriptor routines for the `RM_XLOG_ID` resource manager
(`access/transam/xlog.c`): renders checkpoint, parameter-change,
FPI, restore-point, end-of-recovery and related WAL records to text.
Also the **canonical home of two things the rest of the tree depends
on**: the `wal_level_options` GUC enum table, and
`XLogRecGetBlockRefInfo` — the shared block-reference renderer used by
`pg_waldump`. [from-comment, xlogdesc.c:1-23]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `wal_level_options[]` | `xlogdesc.c:28` | `config_enum_entry` table for the `wal_level` GUC |
| `get_checksum_state_string(state)` | `xlogdesc.c:58` | `PG_DATA_CHECKSUM_*` → "on"/"off"/"inprogress-*" |
| `xlog_desc(buf, record)` | `xlogdesc.c:92` | render an `RM_XLOG_ID` record |
| `xlog2_desc(buf, record)` | `xlogdesc.c:77` | render `XLOG2_CHECKSUMS` (the second xlog rmgr) |
| `xlog_identify(info)` / `xlog2_identify(info)` | `xlogdesc.c:223,283` | opcode → name |
| `XLogRecGetBlockRefInfo(record, pretty, detailed, buf, *fpi_len)` | `xlogdesc.c:302` | render all block refs + FPI info; sums FPI bytes |

## Internal landmarks

- **`xlog_desc` is the checkpoint decoder** (xlogdesc.c:98-128): a
  `XLOG_CHECKPOINT_{SHUTDOWN,ONLINE}` record dumps the entire
  `CheckPoint` struct — redo LSN, TLIs, `fullPageWrites`, `wal_level`,
  logical-decoding flag, next xid/oid/multi, oldest xid/multi/commitTs,
  oldest running/active xid, data-checksum state. This is the single
  best in-tree reference for the on-disk `CheckPoint` field set.
- **`XLOG_PARAMETER_CHANGE`** (xlogdesc.c:154-174) dumps the
  recovery-relevant GUCs (`max_connections`, `max_wal_senders`,
  `max_locks_per_xact`, `wal_level`, …) — these are the parameters a
  standby must have ≥ the primary's.
- **`XLogRecGetBlockRefInfo` (xlogdesc.c:302)** walks every block_id,
  prints `rel s/d/r fork blk`, and for FPIs prints the hole offset/
  length, compression method (`pglz`/`lz4`/`zstd`) and bytes saved; it
  accumulates `*fpi_len` for waldump's FPI accounting.

## Invariants & gotchas

- **`"archive"` and `"hot_standby"` are deprecated aliases for
  `replica`** in `wal_level_options` (xlogdesc.c:31-32, `hidden=true`) —
  they still parse but map to `WAL_LEVEL_REPLICA`. Code reading the GUC
  string back must go through `get_wal_level_string`, which only ever
  emits the canonical names.
- **FPI "for WAL verification" vs applied** — `XLogRecBlockImageApply`
  distinguishes a real full-page image from one stored only for
  `wal_consistency_checking`; the renderer labels the latter explicitly
  (xlogdesc.c:364-365, 415-418). Don't read "FPW" as "this page was
  restored" without checking apply.
- **`xlog_desc` switches on `info & ~XLR_INFO_MASK`**, the rmgr-specific
  opcode bits; the `XLR_INFO_MASK` high bits are reserved by the WAL
  framework and must be stripped first (pattern shared by every
  rmgrdesc).

## Cross-refs

- WAL framework + record format: `knowledge/idioms/`-level `wal-and-xlog`
  skill; `knowledge/subsystems/access-transam.md`.
- `CheckPoint` struct: `src/include/catalog/pg_control.h`.
- Consumer: `pg_waldump` (`src/bin/pg_waldump/`), `xlogreader.c`.
- Sibling commit/abort decoder: `xactdesc.c.md`.

## Tally

`[verified-by-code]=5 [from-comment]=3 [inferred]=0`
