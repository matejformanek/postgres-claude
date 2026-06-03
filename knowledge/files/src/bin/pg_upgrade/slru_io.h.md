# slru_io.h

## Purpose

Public interface of the small SLRU-segment reader/writer used by
pg_upgrade's multixact conversion. Mirrors a subset of the backend's
SLRU machinery but is single-threaded, single-fd, with a one-page
buffer.

## Role in pg_upgrade

Used only by `multixact_read_v18.c` (reader path) and
`multixact_rewrite.c` (writer path) when bridging the pre-v19 32-bit
`MultiXactOffset` format into the v19+ 64-bit format. Not used for
pg_xact / pg_commit_ts / pg_subtrans because those don't undergo a
format change.

## Public surface

- `SlruSegState` struct (lines 14-26): `writing`, `long_segment_names`,
  `dir`, `fn`, `fd`, `segno`, `pageno`, `buf` (PGAlignedBlock).
- Reader: `AllocSlruRead(dir, long_segment_names)`,
  `SlruReadSwitchPage(state, pageno)` inline + `_Slow`,
  `FreeSlruRead(state)`.
- Writer: `AllocSlruWrite(dir, long_segment_names)`,
  `SlruWriteSwitchPage(state, pageno)` inline + `_Slow`,
  `FreeSlruWrite(state)`.

## Invariants

- The inline `SlruReadSwitchPage` (line 33) returns the cached buffer
  if `state->segno != -1 && pageno == state->pageno`; otherwise calls
  the slow path. Caller must not retain pointers returned across
  calls.
- Reader path: `O_RDONLY`; writer path: `O_RDWR | O_CREAT | O_EXCL`
  (slru_io.c:218). Means re-running pg_upgrade after a partial failure
  needs the new pgdata cleaned.

## Phase D notes

[verified-by-code] No `O_NOFOLLOW`. If an attacker controls the new
cluster's pg_multixact/ directory and pre-creates a symlink, the
writer will follow it. New cluster's data dir should be from `initdb`
which sets mode 0700, mitigating this.
