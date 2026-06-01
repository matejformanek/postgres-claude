# statscmds.c

- **Source path:** `source/src/backend/commands/statscmds.c`
- **Lines:** 973
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Commands for creating and altering extended statistics objects." [from-comment, statscmds.c:3-4] CREATE STATISTICS, ALTER STATISTICS, DROP STATISTICS. The actual stats-collection code is in `statistics/extended_stats.c` and is called from `analyze.c`.

## Public surface

- `CreateStatistics` — parse the kind list (`ndistinct`, `dependencies`, `mcv`, `expressions`), the column list (or expression list for PG 14+ expression statistics), insert into `pg_statistic_ext` and (lazily, at first ANALYZE) `pg_statistic_ext_data`.
- `AlterStatistics` — `ALTER STATISTICS … SET STATISTICS n` (per-stats statistics_target override).
- `RemoveStatisticsById`, `RemoveStatisticsDataById` — DROP plus pg_depend cascade.
- `UpdateStatisticsForTypeChange` — when an ALTER TABLE changes a column type, rebuild the dependent extended stats.

## Three kinds, one object

A single `CREATE STATISTICS` can request multiple kinds at once (`(ndistinct, dependencies) ON c1, c2, c3 FROM tbl`). Each kind has its own data slot in `pg_statistic_ext_data`. The planner picks which kind to use for which estimation problem at plan time (extended_stats.c).

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
