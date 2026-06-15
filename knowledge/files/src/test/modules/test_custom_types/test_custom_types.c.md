---
path: src/test/modules/test_custom_types/test_custom_types.c
anchor_sha: e18b0cb7344
loc: 182
depth: read
---

# src/test/modules/test_custom_types/test_custom_types.c

## Purpose

Skeleton custom type for testing the `typanalyze` extension point — the
optional `pg_type.typanalyze` function that lets a custom data type plug into
ANALYZE to compute its own statistics. The custom type is just `int4` under
the hood; the two interesting `typanalyze` wrappers cover (a) returning
`false` (type opts out of analysis) and (b) returning `true` but supplying a
compute_stats callback that sets `stats_valid=false` (i.e. simulating "I
tried but couldn't produce valid stats"). `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int_custom_in` / `int_custom_out` | `test_custom_types.c:44`, `:57` | Input/output functions; delegate to `pg_strtoint32_safe` / `pg_ltoa` |
| `int_custom_typanalyze_false` | `:72` | Returns `false` — declines to analyze |
| `int_custom_typanalyze_invalid` | `:95` | Sets up the `VacAttrStats` with a `compute_stats` callback that marks stats invalid |
| `int_custom_invalid_stats` (static) | `:81` | The callback for the invalid-stats path |
| `int_custom_eq` / `_ne` / `_lt` / `_le` / `_gt` / `_ge` / `_cmp` | `:117-180` | Comparison operators (just int32 ops) |

## Internal landmarks

- `typanalyze_invalid` sets `stats->attstattarget = default_statistics_target`
  when negative (`:101-102`) and `stats->minrows = 300` (`:105`) before
  installing the callback. The comment "Buggy number, no need to care as
  long as it is positive" (`:104`) flags that the goal is to test the
  invalid-stats reporting path, not correctness.
- `int_custom_in` passes `fcinfo->context` to `pg_strtoint32_safe`
  (`:49`) so it participates in the soft-error machinery — invalid input
  can be captured rather than ereport'd.

## Invariants & gotchas

- **Test module — never load in production.**
- The "custom type" is `int4` with a different name; the operator class is
  the interesting part, not the type representation.
- `int_custom_typanalyze_false` returning `false` is the documented signal
  that this column should be skipped during ANALYZE. `_invalid` returning
  `true` but setting `stats_valid=false` exercises the "tried but no
  useful stats" path — `pg_statistic` shouldn't get a row for this
  column.

## Cross-refs

- `source/src/backend/commands/analyze.c` — calls `typanalyze`.
- `source/src/include/commands/vacuum.h` — `VacAttrStats`,
  `AnalyzeAttrFetchFunc`.
- `source/src/include/catalog/pg_type.h` — `typanalyze` column.
