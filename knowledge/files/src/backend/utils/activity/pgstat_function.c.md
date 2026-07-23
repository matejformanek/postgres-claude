# `src/backend/utils/activity/pgstat_function.c`

- **Last verified commit:** `d774576f6f05`
- **Lines:** 249
- **Source:** `source/src/backend/utils/activity/pgstat_function.c`

Per-function call/time stats (`pg_stat_user_functions`). Variable-numbered
on (dboid, funcid). Gated by `track_functions` GUC = `none|pl|all`.

- `pgstat_init_function_usage(fcinfo, fcu)` (`:72`) — entry instrumentation,
  called from `fmgr_security_definer` and direct call paths. Saves
  start time + parent counters. **Concurrent-drop guard (`:110-120`,
  added by 850b9218c8e4):** when this call *creates* a brand-new shared
  stats entry, it `AcceptInvalidationMessages()` then re-checks
  `SearchSysCacheExists1(PROCOID, fn_oid)`; if the function was dropped
  concurrently it drops the just-created entry and raises
  `ERRCODE_UNDEFINED_FUNCTION`. Without this, a bare function call
  (which triggers no cache invalidation) could resurrect a stats entry
  for an already-dropped function and later PANIC on the dangling
  pgstats entry. Relations don't need this because emitting their stats
  already requires holding a relation lock. [verified-by-code, `:86-120`
  @ `d774576f6f05`; from-comment]
- `pgstat_end_function_usage(fcu, finalize)` — exit; adds elapsed time
  (with subtract-from-parent so nested calls don't double-count
  `self_time`), increments `numcalls` (`:181`).
- `pgstat_create_function` (`:44`) / `pgstat_drop_function` (`:59`) —
  register a transactional create/drop so the stats entry is dropped if
  the transaction aborts (create) or commits (drop). Reliable only
  because `pgstat_init_function_usage()` does the extra concurrent-drop
  work above. [from-comment, `:52-58`]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
