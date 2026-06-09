---
path: src/backend/access/rmgrdesc/xactdesc.c
anchor_sha: 4b0bf0788b0
loc: 517
depth: deep
---

# xactdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/xactdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 517

## Purpose

rmgr descriptor routines for `RM_XACT_ID` — but more importantly the
**canonical parsers for the variable-length commit / abort / prepare
WAL records**. `ParseCommitRecord` / `ParseAbortRecord` /
`ParsePrepareRecord` deserialize the chained, optional sub-structures
of an xact record into a flat `xl_xact_parsed_*`. These live here
(rather than `xact.c`) precisely because they're needed by **both
backend redo and frontend `pg_waldump`**, and are too intricate to
duplicate. [from-comment, xactdesc.c:24-32]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `ParseCommitRecord(info, xlrec, parsed)` | `xactdesc.c:34` | decode `xl_xact_commit` → `xl_xact_parsed_commit` |
| `ParseAbortRecord(info, xlrec, parsed)` | `xactdesc.c:140` | decode `xl_xact_abort` → `xl_xact_parsed_abort` |
| `ParsePrepareRecord(info, xlrec, parsed)` | `xactdesc.c:238` | decode `xl_xact_prepare` → `xl_xact_parsed_prepare` |
| `xact_desc(buf, record)` | `xactdesc.c:438` | render a commit/abort/prepare/assignment/inval record |
| `xact_identify(info)` | `xactdesc.c:486` | opcode → name (uses `XLOG_XACT_OPMASK`) |

## The commit-record wire format (the reason this file matters)

`ParseCommitRecord` (xactdesc.c:34) walks a sequence of **optional**
sub-records, each gated by an `xinfo` flag, in a fixed order
(xactdesc.c:46-137):

1. `xl_xact_xinfo` (if `XLOG_XACT_HAS_INFO`) — carries the `xinfo` mask.
2. `xl_xact_dbinfo` (`XACT_XINFO_HAS_DBINFO`) — db/ts OID.
3. `xl_xact_subxacts` (`HAS_SUBXACTS`) — subxact xid array.
4. `xl_xact_relfilelocators` (`HAS_RELFILELOCATORS`) — files to drop at
   commit.
5. `xl_xact_stats_items` (`HAS_DROPPED_STATS`) — pgstat entries to drop.
6. `xl_xact_invals` (`HAS_INVALS`) — shared-inval messages.
7. `xl_xact_twophase` (`HAS_TWOPHASE`) + optional GID (`HAS_GID`).
8. `xl_xact_origin` (`HAS_ORIGIN`) — replication origin LSN/timestamp.

Abort mirrors this (xactdesc.c:140). Prepare is laid out differently —
a fixed `xl_xact_prepare` header followed by **`MAXALIGN`ed** arrays
(xactdesc.c:238-279), unlike commit/abort where only the leading
sub-records are aligned.

## Invariants & gotchas

- **"No alignment is guaranteed after this point"** — after the
  two-phase section, the origin sub-record is `memcpy`'d to a stack
  struct rather than cast in place (xactdesc.c:124-137, 219-232),
  because the preceding GID string is byte-length, not aligned. A patch
  that casts `data` directly to `xl_xact_origin *` here is a
  misaligned-access bug on strict-alignment platforms.
- **Commit/abort use `XLOG_XACT_OPMASK`, not `~XLR_INFO_MASK`**
  (xactdesc.c:442, 491) — the xact rmgr packs both an opcode *and*
  status bits into `info`, so the opmask is narrower. The full
  `XLogRecGetInfo` (with the extra bits) is passed to the parsers,
  which need `XLOG_XACT_HAS_INFO`.
- **`COMMIT_PREPARED`/`ABORT_PREPARED` reuse the same structs** as plain
  commit/abort (xactdesc.c:444-457); the two-phase xid in the parsed
  result is what distinguishes them, shown as a `%u:` prefix.
- **`xact_desc_commit` reuses `standby_desc_invalidations`** from
  `standbydesc.c` (xactdesc.c:350) — the inval-message rendering is
  shared, so commit records and standby `XLOG_INVALIDATIONS` print
  invals identically.
- **Dropped-stats objid is split hi/lo across the wire** and
  reassembled `(hi << 32) | lo` (xactdesc.c:322-323) — a 64-bit value
  stored as two 32-bit fields to avoid alignment padding.

## Cross-refs

- Record structs + `xinfo` flags: `src/include/access/xact.h`.
- Backend redo consumer: `xact.c::xact_redo`.
- Frontend consumer: `pg_waldump`.
- Shared inval renderer: `standbydesc.c.md`.
- Two-phase: `knowledge/files/src/backend/access/transam/twophase.c.md`.

## Tally

`[verified-by-code]=6 [from-comment]=2 [inferred]=0`
