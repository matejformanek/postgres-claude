# vacuum.h

- **Source path:** `source/src/include/commands/vacuum.h`
- **Lines:** 442
- **Last verified commit:** `ef6a95c7c64`

**Large, central header for the whole VACUUM/ANALYZE world.** Key definitions:

- `VAC_BULKDEL_AMVACUUM_OPTIONS` / `VAC_CLEANUP_AMVACUUM_OPTIONS` — flags for `amparallelvacuumoptions` controlling whether each index AM participates in parallel vacuum's bulkdelete / cleanup phases.
- `VacOptValue` enum (UNSPECIFIED, DISABLED, ENABLED, AUTO) — tri-state-plus-auto for options like `INDEX_CLEANUP` that can be left to the engine.
- `VacuumParams` struct — the bag of options threaded everywhere (`freeze_min_age`, `freeze_table_age`, `multixact_freeze_min_age`, etc., `index_cleanup`, `truncate`, `nworkers`, `ring_size`, `is_wraparound`, …).
- `VacuumCutoffs` struct — `OldestXmin`, `FreezeLimit`, `MultiXactCutoff`, `relfrozenxid_pre`, `relminmxid_pre`. Filled by `vacuum_get_cutoffs`.
- `VacAttrStats` — per-column ANALYZE workspace: input function, sample rows, compute_stats callback, output slots for pg_statistic.
- `AnalyzeAttrFetchFunc` / `AnalyzeAttrComputeStatsFunc` — callbacks each typanalyze plugs in.
- `ParallelVacuumState` — opaque struct for the parallel-vacuum coordinator.
- Prototypes: the public surface of vacuum.c (`vacuum`, `ExecVacuum`, `vac_open_indexes`, `vac_close_indexes`, `vacuum_xid_failsafe_check`, `vacuum_delay_point`, `vacuum_get_cutoffs`, `vac_update_relstats`, `vac_update_datfrozenxid`, `vac_truncate_clog`, `vacuum_is_permitted_for_relation`), analyze.c (`analyze_rel`, `std_typanalyze`), and the parallel-vacuum API (`parallel_vacuum_init`/`end`/`bulkdel_all_indexes`/`cleanup_all_indexes`).

## Synthesized by
<!-- backlinks:auto -->
- [idioms/analyze-mcv-histogram-correlation.md](../../../../idioms/analyze-mcv-histogram-correlation.md)
