---
name: extended-statistics
description: PostgreSQL's extended statistics — `CREATE STATISTICS`, `pg_statistic_ext`, `pg_statistic_ext_data` — the 4 stat kinds (dependencies / ndistinct / mcv / expressions) that help the planner handle correlated columns, multi-column NDVs, and expression cardinality. Covers `src/backend/statistics/extended_stats.c` + `dependencies.c` + `mcv.c` + `mvdistinct.c`. Loads when the user asks about extended stats syntax, when to `CREATE STATISTICS`, why a query has bad estimates on correlated columns, ndistinct for GROUP BY estimation, MCV lists in the extended-stats context, or the planner's `clauselist_selectivity_ext` selectivity path. Skip when the ask is about `pg_statistic` (single-column stats — the sibling; see `analyze-block-and-reservoir-sampling` idiom) or about ANALYZE mechanics (that's `analyze.c` — different code path).
when_to_load: Debug wrong planner estimates on correlated columns; add a new extended-stats kind; touch selectivity code that consults extended stats; understand mcv/dependencies/ndistinct semantics.
companion_skills:
  - executor-and-planner
  - catalog-conventions
  - vacuum-autovacuum
---

# extended-statistics — CREATE STATISTICS + planner integration

Column stats live in `pg_statistic` (one row per column). But real queries often have correlated columns (`state = 'CA' AND city = 'SF'` — where `state` and `city` aren't independent) or expression predicates (`WHERE lower(name) = 'alice'`) that per-column stats can't estimate accurately.

**Extended statistics** let the user create statistics OVER MULTIPLE COLUMNS OR EXPRESSIONS. The planner then consults them during selectivity estimation.

## The file map

| File | Role |
|---|---|
| `src/backend/statistics/extended_stats.c` | Umbrella — ANALYZE-time computation dispatcher + `BuildRelationExtStatistics` + fetching. |
| `src/backend/statistics/dependencies.c` | Functional-dependency stat kind: "column A determines column B (mostly)". |
| `src/backend/statistics/mcv.c` | Multi-column MCV list — Most-Common Value lists for combinations of columns. |
| `src/backend/statistics/mvdistinct.c` | Multi-column ndistinct — the N-distinct count of multi-column groupings. |
| `src/backend/optimizer/path/clausesel.c` | Planner-side consumer — `clauselist_selectivity` calls into extended stats when applicable. |
| `src/include/statistics/statistics.h` | Public API. |
| `pg_statistic_ext.h` + `pg_statistic_ext_data.h` | Catalog definitions. Two catalogs: `pg_statistic_ext` (the DEFINITION — CREATE STATISTICS entry) + `pg_statistic_ext_data` (the ACTUAL SAMPLED STATS — populated by ANALYZE). |

## The 4 stat kinds

Set via `CREATE STATISTICS ... (kind1, kind2, ...) ON col1, col2, ...`:

| Kind | Answers |
|---|---|
| **`dependencies`** | "How often does knowing column A's value determine column B's value?" Emitted as (A→B, frequency) pairs. |
| **`ndistinct`** | "How many distinct combinations exist across these columns?" One value per subset. |
| **`mcv`** | Most-common combinations — list of the top-N (col1, col2, ...) tuples + their frequencies. |
| **`expressions`** | (PG 14+) Statistics on an EXPRESSION rather than a column. Enables stats on `LOWER(name)` etc. |

Default when kind list is omitted: all four.

## The dependencies stat

For each ordered pair (A → B) among the covered columns, compute the "functional dependency degree": how often does A = a1 imply B = b1?

- Perfectly dependent (A → B is 1.0): every A value has a unique B value → knowing A tells you B exactly.
- Fully independent (0.0): A doesn't help predict B.

Planner uses this to correct multi-clause selectivity. Instead of `sel(A=x) × sel(B=y)` (which assumes independence), it does `sel(A=x) × sel(B=y | A=x)` — using the dependency degree as the conditional probability estimator.

Storage: sorted by degree, most-dependent first. Only pairs with degree > `STATS_DEPENDENCY_MIN_THRESHOLD` are kept.

## The mcv stat

Multi-column analog of the per-column MCV list. Stores the top-N combined tuples (col1, col2, ...) with their frequencies:

- `[('CA', 'SF'), 0.15]`
- `[('CA', 'LA'), 0.20]`
- `[('NY', 'NYC'), 0.10]`

For a query `WHERE state = 'CA' AND city = 'SF'`, the planner can consult the MCV list directly for a much more accurate estimate than multiplying independent selectivities.

Size cap: `default_statistics_target * 100` entries (adjustable per-stat).

## The ndistinct stat

For every non-empty subset of the covered columns, records the estimated NDV (Number of Distinct Values). Improves GROUP BY row-count estimates + hash-aggregate sizing.

`pg_stats_ext.n_distinct` shows this in a readable form.

## The expressions stat (PG 14+)

`CREATE STATISTICS s ON (lower(name)), (age % 10) FROM users;` — captures stats on those expressions as if they were columns. The planner uses them for `WHERE lower(name) = 'alice'` estimates.

Interesting: the expression itself is stored in `pg_statistic_ext.stxexprs`; ANALYZE evaluates the expression on the sample and produces regular per-column stats keyed to it.

## The planner consultation flow

```
clauselist_selectivity(rel, quals, ...):
    ↓
statext_clauselist_selectivity(rel, quals):
    ↓
For each pg_statistic_ext_data row on this rel:
    ↓
    Apply MCV, then dependencies, then remaining independence assumption.
    ↓
Return combined selectivity.
```

The order of application matters — MCV catches specific-combination queries; dependencies improve remaining independence estimates.

## Common patch shapes

### Add a new extended-stats kind

- Add the 3-char kind code in `include/statistics/statistics.h` (STATS_EXT_*).
- New ANALYZE-time computation function under `src/backend/statistics/`.
- Dispatch case in `extended_stats.c`'s `BuildRelationExtStatistics`.
- Planner-side consumer — new selectivity path in `clausesel.c`.
- Catalog: extended `pg_statistic_ext.stxkind` char[] to include the new code.
- Regress in `src/test/regress/sql/stats_ext.sql`.

### Debug "extended stats aren't helping my query"

- Are they created? `SELECT * FROM pg_statistic_ext WHERE stxrelid = 't'::regclass`.
- Are they populated? `SELECT * FROM pg_stats_ext WHERE tablename = 't'` — this view combines definition + data + column names.
- Was ANALYZE run since creation? Extended stats are populated at ANALYZE time, not at CREATE STATISTICS.
- Is the planner using them? EXPLAIN + set `enable_stat_ext = false` for a comparison.
- Are the applicable clauses in the query? Extended stats only apply when all columns/expressions of the stat appear in the WHERE clause.

### Extend a specific kind (add a new attribute)

- Add field to the on-disk format for that kind (in dependencies.c / mcv.c / mvdistinct.c).
- Bump `PG_STAT_EXT_FORMAT_ID` if the change breaks format compatibility.
- Update pg_stats_ext view.

## Pitfalls

- **Extended stats need ANALYZE to be populated** — CREATE STATISTICS is DDL only; without ANALYZE, `pg_statistic_ext_data` has no row. Common surprise: "I created the stats but the estimate is still wrong".
- **`default_statistics_target` × 100 MCV cap** — a table with 10k+ high-cardinality combinations can exceed this. Set higher via `ALTER STATISTICS ... SET STATISTICS N;`.
- **Autovacuum's ANALYZE decides when to update extended stats** — the threshold is the same as regular ANALYZE. On a table with static distribution, this may be infrequent.
- **Cross-schema extended stats have permission gotchas** — the stat is owned by the user who ran CREATE STATISTICS. Ownership matters for OWNED BY relationships on drop.
- **Only applies when all clauses match the stat definition** — a stat `ON (a, b, c)` doesn't help a query `WHERE a = x AND b = y` (missing c) unless subset support is added.
- **Expressions must be immutable** — `WHERE lower(name) = ?` benefits from expression stats; `WHERE random() < ?` doesn't (volatile).
- **Storage cost** — MCV lists for wide-columns tables can be large. Stored in `pg_statistic_ext_data.stxdmcv` (bytea).
- **Backup/restore preserves data but recomputes on RESTORE** — extended stats are dumped by pg_dump; the ANALYZE-produced data may or may not be included depending on version.

## Related corpus

- **Idiom**: `analyze-mcv-histogram-correlation` (single-column stats side), `extended-statistics-statext` (this exists).
- **Subsystems**: `optimizer` (consumer via clausesel.c), `access-heap` (VACUUM interaction — ANALYZE triggers stat update).
- **Related planning**: none directly, but many "wrong plan" investigations end at extended stats.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --idiom extended-statistics-statext
python3 scripts/corpus-chain.py --file src/backend/statistics/extended_stats.c
```

## Boundary

**Use this skill** for `CREATE STATISTICS` + extended-stats kinds + planner consumption.

**Don't use** for:
- **Single-column `pg_statistic` stats** — sibling but different code path. See `analyze-mcv-histogram-correlation` idiom.
- **ANALYZE sampling mechanics** — that's `analyze.c` and `analyze-block-and-reservoir-sampling` idiom.
- **`pg_stat_*` cumulative-statistics views** — completely different system. See `pgstat-framework` skill.
- **PostgreSQL 17+ MERGE stat clause** — DDL only, not extended-stats internals.
<!-- T9 triaged 2026-07-13: an earlier draft of this skill cited a
"pg_get_row_estimate_hints (PG 18+)" API as an out-of-scope sibling.
That API does not exist in the source — verified via
`git grep pg_get_row_estimate_hints` returning zero matches on
master.  The claim was a harvester hallucination, now removed.
If a query-hint mechanism does land in a future PG version, it will
likely be in the planner's cost/selectivity path, not in
extended-stats. -->

