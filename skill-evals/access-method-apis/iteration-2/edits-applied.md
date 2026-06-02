# Edits applied to SKILL.md before iteration-2

All six minor-polish edits from `iteration-1/proposed-edits.md` were applied.
Specific values verified against `source/` before writing:

1. **`IndexBulkDeleteResult *` return type explicit** — added to `ambulkdelete`
   and `amvacuumcleanup` rows in the mandatory-callbacks table.
   Verified: `source/src/include/access/amapi.h:135-142` typedefs return
   `IndexBulkDeleteResult *` for both.

2. **`ambeginscan` rule promoted to GOTCHA block** — lifted from inline
   paragraph into a fenced blockquote so a skimming reader can't miss it.
   No source-value change; wording preserved.

3. **`amparallelvacuumoptions` opt-out one-liner** — added "set to
   `VACUUM_OPTION_NO_PARALLEL` (= 0) to opt out" with the three bit names.
   Verified: `source/src/include/commands/vacuum.h:41` defines
   `VACUUM_OPTION_NO_PARALLEL 0`, and 47/54/62 define the three bits.

4. **Table-AM mandatory-count reconciled** — old skill said "~45 callbacks"
   then "~30 Assert lines". Updated to "~45-callback struct;
   `tableamapi.c::GetTableAmRoutine` asserts 37 of them" in both the intro
   paragraph and the "All mandatory" subsection.
   Verified: `grep -c 'Assert(routine' source/src/backend/access/table/tableamapi.c` = 37.

5. **Autovacuum-statistics leakage explicit** — added paragraph under TID
   semantics naming `pg_stat_all_tables`, `n_dead_tup`/`n_live_tup`, and the
   `pgstat_count_heap_*` / `pgstat_report_vacuum` entry points a non-heap AM
   must call from inside its own tuple ops.

6. **Lifecycle diagram order fixed** — `aminsertcleanup` no longer reads as
   per-row. Build line now ends at `ambuild`. Insert/Update line says
   `(per row) aminsert → (once at end of statement) aminsertcleanup`.
   Verified: `aminsertcleanup_function` signature is `(Relation, IndexInfo)`
   in `source/src/include/access/amapi.h:131` — no `ItemPointer` arg, so
   per-statement not per-row.
