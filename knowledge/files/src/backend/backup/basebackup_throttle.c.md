# `src/backend/backup/basebackup_throttle.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~170
- **Source:** `source/src/backend/backup/basebackup_throttle.c`

bbsink implementing `MAX_RATE` (`pg_basebackup -r`). Token-bucket-ish
throttling: each `archive_contents`/`manifest_contents` adds the chunk
size to a running tally; once `throttling_sample` bytes have crossed,
sleep until enough wall time has elapsed to match the target rate.

- `bbsink_throttle_new(next, maxrate)` — `throttling_sample` is
  computed as `maxrate * THROTTLING_SAMPLE_MIN` (~~~ a fraction of a
  second worth of data) so the sleep frequency is bounded.
- Sleep uses `WaitLatch` with `WAIT_EVENT_BASEBACKUP_THROTTLE` so
  `pg_stat_activity` clearly indicates throttling, and so signals
  (SIGTERM, query cancel) wake us up immediately rather than at the
  next chunk boundary.
- The throttle sink usually sits **before** compression in the chain so
  the rate applies to raw bytes (the user usually wants to bound disk
  I/O, not network bandwidth). [from-comment]
