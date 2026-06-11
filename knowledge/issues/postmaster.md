# Issues — `postmaster`

Per-subsystem issue register for `src/backend/postmaster/` — the
postmaster, auxiliary processes, dynamic background-worker registry,
and PG18 online-checksum machinery.

**Parent subsystem docs:**
- `knowledge/subsystems/postmaster.md`
- `knowledge/files/src/backend/postmaster/*.c.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | postmaster/datachecksum_state.c:685-690 | stale-todo | likely | "TODO: investigate if this could be avoided if the checksum is calculated to be correct and wal_level is set to 'minimal'." Every dirtied page during online enable forces a full-page WAL even when checksum already matches | open | knowledge/files/src/backend/postmaster/datachecksum_state.c.md §Potential issues |
| 2026-06-11 | postmaster/datachecksum_state.c:149-176 | stale-todo | nit | Header comment lists ~5 "Future opportunities for optimizations" (restart-from-startup, skip-unchanged-checksum, pg_checksums resume, restartability, skip-DBs-created-during-inprogress, CREATE DATABASE checksum inheritance) — none scheduled | open | knowledge/files/src/backend/postmaster/datachecksum_state.c.md §Potential issues |
| 2026-06-11 | postmaster/datachecksum_state.c:316-318 | undocumented-invariant | maybe | "If multiple workers, or dynamic cost parameters, are supported at some point then this would need to be revisited." Lock-free read of cost params is safe only for single-worker world | open | knowledge/files/src/backend/postmaster/datachecksum_state.c.md §Potential issues |
| 2026-06-11 | postmaster/datachecksum_state.c:711 | style | nit | `Assert(operation == ENABLE_DATACHECKSUMS)` inside `ProcessSingleRelationFork` — release builds silently do the right-ish thing if invoked from a disable path. Should be a hard runtime check | open | knowledge/files/src/backend/postmaster/datachecksum_state.c.md §Potential issues |
| 2026-06-11 | postmaster/datachecksum_state.c | style | nit | Triple-check of `launch_operation != operation` under three separate `LWLockAcquire/Release` pairs in `DataChecksumsWorkerLauncherMain` — could be one helper | open | knowledge/files/src/backend/postmaster/datachecksum_state.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- `datachecksum_state.c` is the PG18 online-checksum-enable/disable
  feature; the header is an unusually-long English-prose proof of
  the synchronization model and `checksum_barriers[9]` is the
  authoritative transition table. Every barrier transition not in
  that table is rejected by `AbsorbDataChecksumsBarrier`.
- All-or-nothing semantics: a single per-DB failure during enable
  triggers `SetDataChecksumsOff()` + ERROR. Recovery state is not
  persisted, so a launcher killed mid-enable leaves the cluster in
  `off` after restart (the operator must re-run
  `pg_enable_data_checksums()`).
- Cost-delay reuses `vacuum_delay_point` — the comment explains
  "Processing is re-using the vacuum cost delay for process
  throttling, hence why we call vacuum APIs here."
