# plancat.c — system-catalog access for the planner

- **Source:** 2914 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read (this is the planner's catalog gateway)

## 1. Purpose

Every catalog lookup the planner needs for a baserel — `pg_class`,
`pg_index`, `pg_statistic`, `pg_constraint`, FK info, partition
descriptors, NOT-NULL bits — flows through this file. Output:
populated `RelOptInfo` fields ready for cost-model consumption.

## 2. Spine functions

| Line | Function | Role |
|---|---|---|
| 120 | `get_relation_info(root, oid, inhparent, rel)` | THE entry. Opens relation without locking (already locked by rewriter or `expand_inherited_rtentry`); fills indexlist, pages, tuples, allvisfrac, fkeylist, notnullattnums, etc. `inhparent=true` ⇒ only set up attr arrays (parent rel is the appendrel; partitioned table also gets indexlist for unique-proof use). [from-comment:110-119, verified-by-code:120-135] |
| 689 | `get_relation_notnullatts(root, relation)` | Cached NOT-NULL attnum bitmap (one entry per relation, hashed) |
| 801 | `infer_arbiter_indexes` | ON CONFLICT inference — no default-opclass dependency in the spec; any matching index is acceptable [from-comment:790-798] |
| 1304 | `estimate_rel_size(rel, attr_widths, pages, tuples, allvisfrac)` | Read pg_class.relpages/reltuples and adjust for actual file size when planning [verified-by-code] |
| 1429 | `get_rel_data_width(rel, attr_widths)` / 1471 `get_relation_data_width(relid, ...)` | Per-tuple width estimate; dropped cols treated as zero-width (wrong but harmless) [from-comment:1420-1428] |
| 1851 | `relation_excluded_by_constraints` | Examines `rel->relid`, `reloptkind`, `baserestrictinfo` only — callable before the RelOptInfo is fully populated [from-comment:1845-1850] |
| 2041 | `build_physical_tlist` | Whole-row tlist for SeqScan and select other scan kinds where a 1:1 with stored cols is preferred [from-comment:2030-2038] |
| 2224 | `restriction_selectivity` | Call the operator's restrict-selectivity proc |
| 2263 | `join_selectivity` | Call the operator's join-selectivity proc |
| 2303 | `function_selectivity` | Ask the function's support-fn for a boolean selectivity; -1 means "no support" [from-comment:2295-2301] |

## 3. Globals / GUCs

`constraint_exclusion` GUC (line 58, default `CONSTRAINT_EXCLUSION_PARTITION`)
controls aggression of `relation_excluded_by_constraints`. [verified-by-code]

## 4. Subtle points

- **No locks taken here.** The relation is assumed already locked by an
  earlier phase. Forgetting this would corrupt the lock pattern.
  [from-comment:128-132]
- **Inheritance parent shortcut.** `inhparent=true` skips index/page
  info gathering — except for partitioned tables, which still need
  `indexlist` for unique-proof exploitation. [from-comment:113-119]
- **Relations without a table AM** (views, composite types) are
  rejected; the check prevents a crash if a view's ON SELECT rule has
  vanished. [from-comment:135-141]

## 5. Tags
`[verified-by-code]` ×5, `[from-comment]` ×9
