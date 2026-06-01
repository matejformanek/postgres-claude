# initsplan.c — RelOptInfo + EC + SpecialJoinInfo construction

- **Source:** `source/src/backend/optimizer/plan/initsplan.c` (4297 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## 1. Purpose

Convert the Query (post-prep) into the data structures the join-search
phase consumes: baserel RelOptInfos with target lists and attr_needed,
PlaceHolderInfos for lateral/pulled-up vars, SpecialJoinInfo for outer
joins, EquivalenceClasses from `x = y` quals, and the per-rel
restriction/join clause lists. Tagline: "Target list, group by,
qualification, joininfo initialization routines". [from-comment:3-4]

## 2. Public entry points (called from planmain.c in this order)

| Line | Function | Role |
|---|---|---|
| 177 | `add_base_rels_to_query` | Recurse jointree → one baserel RelOptInfo per RTE [from-comment:170] |
| 215 | `add_other_rels_to_query` | Create appendrel child "otherrel" RelOptInfos *late* |
| 254 | `build_base_rel_tlists` | Pull tlist Vars into per-baserel tlists; PVC_RECURSE_AGG/WIN, PVC_INCLUDE_PLACEHOLDERS [verified:259] |
| 301 | `add_vars_to_targetlist` | Append vars; PHVs go to placeholder_list (single owning rel not safe) [from-comment:295] |
| 372 | `add_vars_to_attr_needed` | Like above but only updates attr_needed bits |
| 431 | `remove_useless_groupby_columns` | Drop GROUP BY cols functionally dependent on PK+NOT NULL |
| 693 | `setup_eager_aggregation` | Push aggregation below joins when safe (gated by `enable_eager_aggregate`) |
| 1095 | `find_lateral_references` | Must run *before* deconstruct_jointree because it can create PHIs [from-comment:1090] |
| 1244 | `rebuild_lateral_attr_needed` | After join removal, reconstruct lateral attr_needed |
| 1282 | `create_lateral_join_info` | Fill `direct_lateral_relids`, `lateral_relids`, `lateral_referencers` per baserel |
| 1521 | `deconstruct_jointree` | Returns joinlist; builds SpecialJoinInfos, distributes quals, freezes PHI creation [from-comment:1510-1530] |
| 3492 | `restriction_is_always_true` | NullTest-based qual-folding |
| 3557 | `restriction_is_always_false` | symmetric |
| 3628 | `distribute_restrictinfo_to_rels` | Final step of qual distribution; ECs may divert + feed back |
| 3960 | `rebuild_joinclause_attr_needed` | Post-join-removal fixup |
| 4032 | `match_foreign_keys_to_quals` | Annotate FK info with eclass/qual matches; discard irrelevant FKs |

## 3. Key invariants / surprises

- **PHI freeze:** "After this point, no more PlaceHolderInfos may be made"
  — the moment `deconstruct_jointree` starts. [from-comment:1530-ish, verified-by-code]
- **find_lateral_references must precede deconstruct_jointree** because
  LATERAL discovery may create PHIs. [from-comment:1090-1092]
- **add_other_rels_to_query is deliberately late** (called by planmain
  *after* join removal) so as much restriction info as possible is
  available for partition pruning. [from-comment in planmain.c:278-284]
- **"Relation 0" (`bms_make_singleton(0)`)** is the marker for vars
  needed at the top of the plan; ensures they propagate up through every
  join level. [from-comment:248-249]
- **Clone clauses caveat:** `restriction_is_always_{true,false}` refuses
  to draw NOT-NULL conclusions from "clone" RestrictInfos because their
  nullingrel bits may lie. [from-comment:3495-3499]
- **FK matching is the last step before path generation** in the
  planmain pipeline; the FK info is used by `joinpath.c` selectivity.

## 4. Tags
`[verified-by-code]` ×7, `[from-comment]` ×9

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
