# `src/backend/utils/activity/pgstat_function.c`

- **Last verified commit:** `031904048aa2`
- **Lines:** 249
- **Source:** `source/src/backend/utils/activity/pgstat_function.c`

Per-function call/time stats (`pg_stat_user_functions`). Variable-numbered
on (dboid, funcid). Gated by `track_functions` GUC = `none|pl|all`.

- `pgstat_init_function_usage(fcinfo, fcu)` (`:72`) — entry instrumentation,
  called from `fmgr_security_definer` and direct call paths. Saves
  start time + parent counters. **Concurrent-drop guard (`:108-119`,
  added by 850b9218c8e4):** when this call *creates* a brand-new shared
  stats entry, it `AcceptInvalidationMessages()` then re-checks
  `SearchSysCacheExists1(PROCOID, fn_oid)`; if the function was dropped
  concurrently it drops the just-created entry and raises
  `ERRCODE_UNDEFINED_FUNCTION`. Without this, a bare function call
  (which triggers no cache invalidation) could resurrect a stats entry
  for an already-dropped function and later PANIC on the dangling
  pgstats entry. Relations don't need this because emitting their stats
  already requires holding a relation lock. [verified-by-code, `:90-119`
  @ `031904048aa2`; from-comment]
- `pgstat_end_function_usage(fcu, finalize)` — exit; adds elapsed time
  (with subtract-from-parent so nested calls don't double-count
  `self_time`), increments `f_numcalls`.
- `pgstat_create_function` / `pgstat_drop_function` — invalidate stats
  entry on DDL via syscache callback on `PROCOID`. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
