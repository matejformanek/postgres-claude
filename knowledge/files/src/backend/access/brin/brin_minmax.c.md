# brin_minmax.c

- **Source path:** `source/src/backend/access/brin/brin_minmax.c` (314 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Built-in **minmax** opclass for BRIN: each summary stores `(min, max)` of the page range. The simplest BRIN opclass; backs the default integer/numeric/date/text minmax classes. [from-comment, brin_minmax.c:1-10]

## Required procs

| Procnum | Function | Role |
|---|---|---|
| 1 (opcInfo) | `brin_minmax_opcinfo` | declares 2 stored columns (min, max), both of the indexed attno type |
| 2 (addValue) | `brin_minmax_add_value` | expand interval if new value < min or > max |
| 3 (consistent) | `brin_minmax_consistent` | dispatch on `BTLessStrategyNumber`/…/`BTEqualStrategyNumber` against min/max |
| 4 (union) | `brin_minmax_union` | combine two ranges by min/min, max/max |

Uses a small `MinmaxOpaque` per-attribute cache of fmgr lookups keyed by `(subtype, strategynum)`. [verified-by-code, brin_minmax.c:22-30]

## Notes

- The consistent function maps the SQL strategy to a btree strategy via `minmax_get_strategy_procinfo`, which looks up the `pg_amop` entry on the attribute's opclass to find the actual comparison function. Strategy mapping for `<` is "the max must be > value"; for `>` is "the min must be < value"; for `=` is both `min <= value` and `max >= value`. [inferred from standard minmax-semantics — code structure matches]
- Stored types are exact copies of the input type (procnum 1 returns `BrinOpcInfo` with `oi_typcache[i] = lookup_type_cache(...)`).

Tags: [from-comment, brin_minmax.c:1-10], [verified-by-code, brin_minmax.c:22-30].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
