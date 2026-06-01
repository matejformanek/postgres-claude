# `src/backend/utils/activity/pgstat_function.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~230
- **Source:** `source/src/backend/utils/activity/pgstat_function.c`

Per-function call/time stats (`pg_stat_user_functions`). Variable-numbered
on (dboid, funcid). Gated by `track_functions` GUC = `none|pl|all`.

- `pgstat_init_function_usage(fcinfo, fcu)` — entry instrumentation,
  called from `fmgr_security_definer` and direct call paths. Saves
  start time + parent counters.
- `pgstat_end_function_usage(fcu, finalize)` — exit; adds elapsed time
  (with subtract-from-parent so nested calls don't double-count
  `self_time`), increments `f_numcalls`.
- `pgstat_create_function` / `pgstat_drop_function` — invalidate stats
  entry on DDL via syscache callback on `PROCOID`. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
