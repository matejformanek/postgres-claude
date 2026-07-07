# contrib-pg_walinspect (inspect WAL contents from SQL)

- **Source path:** `source/contrib/pg_walinspect/`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Extension version:** `1.1` (per `pg_walinspect.control`)
- **Trusted:** no (reads WAL directly; needs `pg_read_server_files`
  membership or equivalent)
- **Main file:** `pg_walinspect.c` (single C file + install SQL)

## 1. Purpose

A SQL surface for inspecting Write-Ahead Log contents — record-by-record
metadata, per-record block data, aggregate per-rmgr / per-record-type
statistics. Lets a DBA or replication tool examine WAL ranges from
within an active backend, without shelling out to the `pg_waldump`
CLI. Added in PG 15; actively maintained. Sister tool of `pg_waldump`
(per the header comment: "For any code change or issue fix here, it
is highly recommended to give a thought about doing the same in
pg_waldump tool as well." [verified-by-code `pg_walinspect.c:31-33`]).

## 2. Mental model

- **A single-file extension.** Everything lives in
  `pg_walinspect.c`. Six SRFs + a couple of helper functions for LSN
  validation + `XLogReaderState` lifecycle.
- **Reads via `XLogReaderState`.** Same machinery as `pg_waldump`
  and the replay path. `xlogreader.h` is the interface; rmgr-specific
  decoding is in `xlogstats.h` + per-rmgr `*_desc` functions.
- **No shared state, no shmem, no GUCs.** Each function opens a
  fresh `XLogReaderState` for the call duration. Caller-visible
  parameters: a start LSN, an optional end LSN, sometimes a wait flag.
- **LSN validation is strict.** `ValidateInputLSNs` rejects ranges
  that:
  - Start before WAL start.
  - End past the current LSN (unless the caller opted into
    "till-end-of-wal" behavior via the dedicated `*_till_end_of_wal`
    variants).
  - Have `end_lsn < start_lsn`.

## 3. Key files

- `pg_walinspect.c` (~600 LOC) — the entire implementation. Sections:
  - `_PG_init` is implicit (no module init function; module loads
    on first function call via fmgr).
  - `ValidateInputLSNs` — bounds-check the caller's range.
  - `GetCurrentLSN` — wrapper around `GetFlushRecPtr` /
    `GetInsertRecPtr`; chooses based on the current recovery state.
  - `InitXLogReaderState` / `ReadNextXLogRecord` — XLogReaderState
    lifecycle helpers shared by all SRFs.
  - SRFs (6): `pg_get_wal_block_info`, `pg_get_wal_record_info`,
    `pg_get_wal_records_info`,
    `pg_get_wal_records_info_till_end_of_wal`, `pg_get_wal_stats`,
    `pg_get_wal_stats_till_end_of_wal`.
- `pg_walinspect--1.0.sql`, `pg_walinspect--1.0--1.1.sql` — install
  + upgrade SQL declaring the SRFs.
- `walinspect.conf` — per-test configuration for the in-tree TAP /
  regression tests.

## 4. Key data structures

- **`XLogReaderState`** (from `xlogreader.h`) — the canonical PG
  WAL reader state. Holds: current decoded record, read-page
  callback, decoded-block tuples, segment-open state, error buffer.
- **`DecodedXLogRecord`** — what each SRF row is derived from:
  rmgr id, record length, FPI length, lsn, prev-lsn, info byte +
  flags, per-block records.
- **`XLogStats`** (from `xlogstats.h`) — the per-rmgr +
  per-record-type accumulator for the aggregate SRFs.

## 5. SQL surface

All functions are SRFs returning rowsets. From
`pg_walinspect--1.0.sql` + the 1.1 upgrade:

- **`pg_get_wal_record_info(in_lsn pg_lsn) → record`** — one row
  with the record at `in_lsn`.
- **`pg_get_wal_records_info(start_lsn, end_lsn) → setof record`** —
  every record in `[start, end]`.
- **`pg_get_wal_records_info_till_end_of_wal(start_lsn) → setof record`** —
  same but reads to current LSN.
- **`pg_get_wal_block_info(start_lsn, end_lsn[, show_data]) → setof record`** —
  block-level info for every record's referenced blocks.
- **`pg_get_wal_stats(start_lsn, end_lsn[, per_record]) → setof record`** —
  aggregate statistics per rmgr or per record type.
- **`pg_get_wal_stats_till_end_of_wal(start_lsn[, per_record]) → setof record`** —
  same but reads to current LSN.

## 6. Invariants and gotchas

- **[INV-1]** All functions are `STABLE` (not `IMMUTABLE`) — they
  read WAL whose state can change between calls. Don't downgrade
  to `IMMUTABLE` in the install SQL.
- **[INV-2]** The `*_till_end_of_wal` variants have a different
  contract from the bounded variants: they pick up the *current*
  end LSN at call time. Don't fold the two surfaces into one —
  they're SQL-level distinct for caller-clarity reasons.
- **[INV-3]** **Mirror changes in `pg_waldump`.** The file header
  is explicit: any decoding fix here usually wants a parallel fix
  in `src/bin/pg_waldump/pg_waldump.c`. Skipping the parallel
  change is the classic post-merge cleanup task.
- **[INV-4]** Caller must have the role granted by the SQL install
  script (`pg_read_server_files`, since 1.1). Don't expand the
  SQL surface to expose this to less-privileged roles without an
  explicit security review.
- **[INV-5]** Reading WAL during recovery is fine for the
  `pg_get_*` SRFs as long as the requested LSN is within
  consistent state; bounds-checking handles the rest.

## 7. Owners (as of 2026-06-12)

- Original author: Bharath Rupireddy (per `git log`, PG 15
  introduction).
- Active maintainer: Bharath Rupireddy, Michael Paquier (per the
  recent commit history on this file).
- Persona drivers: similar reflexes to `pg_waldump` — Michael
  Paquier's interest in WAL inspection tooling.

## 8. Local reviewer reflexes

- Any new SRF: confirm `pg_proc.dat` (or the extension SQL)
  marks it `STABLE`, not `IMMUTABLE`.
- Any decoding change: cross-check `pg_waldump` for the parallel
  fix; flag if absent.
- Any LSN-range change: walk `ValidateInputLSNs` for the new
  contract; the validation is the security boundary.
- Any new rmgr-aware function: confirm it goes through
  `xlogstats.h` helpers, not a parallel decoder.
- Any change to the role-grant surface in the install SQL:
  security review required (this is a WAL-reading extension —
  privilege creep here means information disclosure of any
  arbitrary table's WAL records).

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/pg_walinspect/pg_walinspect.c`](../files/contrib/pg_walinspect/pg_walinspect.c.md) |

<!-- /files-owned:auto -->
## Cross-references

- `.claude/skills/wal-and-xlog/SKILL.md` — `XLogReaderState`,
  rmgr design, `*_desc` functions.
- `.claude/skills/fmgr-and-spi/SKILL.md` — SRF conventions
  (Materialize mode is what this extension uses).
- `.claude/skills/extension-development/SKILL.md` — `.control`
  file, install + upgrade SQL.
- `.claude/skills/error-handling/SKILL.md` — `ValidateInputLSNs`'s
  `ereport(ERROR, ...)` contract for invalid ranges.
- `knowledge/architecture/wal.md` — WAL design overview.
- `source/src/bin/pg_waldump/` — the sister CLI; keep them in
  sync per the `[INV-3]` rule.
- `doc/src/sgml/pgwalinspect.sgml` — user-facing reference.
