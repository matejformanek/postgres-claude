---
source_url: https://www.postgresql.org/docs/current/wal-configuration.html
fetched_at: 2026-06-12T20:50:00Z
anchor_sha: e18b0cb
chapter: "30.5 WAL Configuration"
---

# WAL Configuration (docs §30.5)

Checkpoints, segment recycling, restartpoints, and the WAL-buffer/group-commit
internals behind the tuning GUCs. `[from-docs]`.

## Checkpoints

- **A checkpoint guarantees all pre-checkpoint changes are on the data files**;
  it flushes all dirty pages and writes a checkpoint record. Recovery starts
  REDO from the *redo record* named by the latest checkpoint; WAL segments
  before that can be recycled/removed (unless archiving). `[from-docs]`
- **The checkpointer fires on whichever comes first:** `checkpoint_timeout`
  (default 5 min) or `max_wal_size` (default 1 GB) about to be exceeded. **A
  checkpoint is skipped entirely if no WAL was written since the last one.**
  `CHECKPOINT` forces one. `[from-docs]`
- **`checkpoint_completion_target` (default 0.9)** spreads checkpoint I/O across
  that fraction of the interval. Set **no higher than 0.9** — 1.0 risks
  checkpoints not finishing on time. To checkpoint *more often* without changing
  the spread, lower `checkpoint_timeout`, not this. Prolonging checkpoints
  lengthens recovery (more WAL must be kept). `[from-docs]`
- **`checkpoint_flush_after`** (Linux/POSIX) forces OS pages flushed after N
  bytes so the end-of-checkpoint fsync doesn't stall; helps when the working set
  is larger than `shared_buffers` but smaller than OS page cache. `[from-docs]`
- **Shorter checkpoint intervals fight `full_page_writes`:** the first change to
  a page after each checkpoint logs the full page, so more-frequent checkpoints
  inflate WAL volume — partly negating the smaller-interval goal. `[from-docs]`
- **`checkpoint_warning`** logs "increase `max_wal_size`" when checkpoints come
  closer than its seconds; bulk `COPY` can trip it. `pg_stat_checkpointer`
  exposes counters (incl. `restartpoints_timed/req/done`). `[from-docs]`

## Segment recycling & sizing

- **Old segments are removed *or recycled*** (renamed into the future sequence).
  Below `max_wal_size`, the system keeps enough recycled files to cover a
  **moving average** of recent usage (the average jumps up immediately on a
  spike, not just gradually). `min_wal_size` is the floor of always-recycled
  files even when idle. `max_wal_size` is a *soft* limit — exceeded on peaks,
  then trimmed. `[from-docs]`
- **`wal_keep_size`** independently retains the most recent N MB (plus one file).
  Archiving, lagging replication slots, and pending WAL summarization can each
  pin old segments and make `pg_wal` grow without bound if they stall.
  `[from-docs]`

## Restartpoints (recovery / standby)

- **Restartpoints are checkpoint-equivalents during archive recovery / standby**:
  force state to disk, update `pg_control` so already-processed WAL isn't
  re-scanned, recycle old segments. **They can only occur at checkpoint records
  and no more often than checkpoints ran on the primary.** `[from-docs]`
- **`max_wal_size` is regularly exceeded during recovery by up to one checkpoint
  cycle** because of that timing limit — never treat it as a hard cap; leave
  headroom. A fast-growing primary can spike `restartpoints_req` on the standby
  (requests that can't yet be honored); only `restartpoints_done` reflects real
  resource use. `[from-docs]`

## WAL buffers & group commit

- **`XLogInsertRecord` runs on every low-level modification while page locks are
  held** — must be fast; if WAL buffers are full it has to write them itself
  (and maybe create a new segment, slower still). On high-WAL systems, raising
  **`wal_buffers`** prevents that, and smooths the post-checkpoint full-page-write
  burst. `XLogFlush` (mostly at commit) writes+syncs the buffers. `[from-docs]`
- **`commit_delay` µs sleep** by the group-commit leader inside `XLogFlush`, only
  when `fsync` is on *and* ≥ `commit_siblings` other sessions are in active
  transactions. Recommended start ≈ half the single-8 kB-flush time from
  `pg_test_fsync`. At high client counts the natural "gangway" group commit
  already helps, so explicit `commit_delay` adds less. `[from-docs]`
- **`wal_sync_method` options are reliability-equivalent except
  `fsync_writethrough`** (which may force a disk cache flush others don't);
  fastest is platform-specific (`pg_test_fsync`), and the whole setting is moot
  if `fsync=off`. With `open_datasync`/`open_sync` the *write* already syncs and
  `issue_xlog_fsync` is a no-op; with `fdatasync`/`fsync`/`fsync_writethrough`
  the write only reaches kernel cache and `issue_xlog_fsync` does the sync.
  `[from-docs]`
- **`track_wal_io_timing`** adds `write_time`/`fsync_time` to `pg_stat_io` for
  the `wal` object (counts always recorded). **`recovery_prefetch`** (default
  `try`) prefetches soon-needed blocks during recovery, bounded by
  `maintenance_io_concurrency` and `wal_decode_buffer_size`. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/wal-reliability.md]] — full-page-write / torn-page
  side of the checkpoint interaction.
- [[knowledge/docs-distilled/wal-async-commit.md]] — `commit_delay` vs. async
  commit distinction.
- [[knowledge/docs-distilled/runtime-config-wal.md]] — the full GUC catalog.
- [[knowledge/subsystems/access-transam.md]] — `XLogInsertRecord` / `XLogFlush` /
  `XLogWrite` / checkpoint machinery.
- Skill: `wal-and-xlog`, `gucs-bgworker-parallel` (checkpointer/walwriter).

## Citations

- All `[from-docs]`. Checkpoint logic in
  `source/src/backend/access/transam/xlog.c` + the checkpointer in
  `source/src/backend/postmaster/checkpointer.c`; WAL buffers/flush in
  `xlog.c` (`XLogInsertRecord`/`XLogFlush`/`XLogWrite`/`issue_xlog_fsync`).
  Verify line numbers at anchor e18b0cb.
