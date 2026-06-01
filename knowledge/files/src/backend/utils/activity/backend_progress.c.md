# `src/backend/utils/activity/backend_progress.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~140
- **Source:** `source/src/backend/utils/activity/backend_progress.c`

Backs the `pg_stat_progress_*` views (vacuum, analyze, cluster,
create_index, copy, basebackup, …). Generic infrastructure; the actual
field semantics are owned by the command.

API for command implementations:
- `pgstat_progress_start_command(cmdtype, relid)` — sets
  `MyBEEntry->st_progress_command` and zeros `st_progress_param[]`.
- `pgstat_progress_update_param(index, val)` — one of
  `PGSTAT_NUM_PROGRESS_PARAM = 20` slots.
- `pgstat_progress_update_multi_param(nparam, indexes[], vals[])`.
- `pgstat_progress_incr_param(index, incr)`.
- `pgstat_progress_end_command()` — clears the state.

Parallel-worker side: `pgstat_progress_parallel_incr_param` writes to
the leader's BEEntry via a shared spinlocked counter so the leader's
view of "tuples scanned by all workers" is consistent. [from-comment]
