# analyzejoins.c — post-initsplan join simplification

- **Source:** `source/src/backend/optimizer/plan/analyzejoins.c` (2668 lines)
- **Last verified commit:** `1863452a4bfe` (re-anchored 2026-07-14 pg-quality-auditor; +99 lines accumulated since ef6a95c7c64, incl. 9a60f295bcb1 PlaceHolderVar strip)
- **Depth:** read

## 1. Purpose

Performs join simplifications that need the data structures built by
`initsplan.c` (SpecialJoinInfo list, EquivalenceClasses, RelOptInfo lookup
tables). This is the *second* pass of join cleanup after
`prep/prepjointree.c`. [from-comment:6-12]

## 2. Public entry points

- `List *remove_useless_joins(PlannerInfo *root, List *joinlist)` —
  drops removable LEFT JOINs (line 95). Iterates `join_info_list`; the
  inner side must be a single baserel proven not to multiply rows and not
  referenced anywhere else. Mutates joinlist, RelOptInfos,
  EquivalenceClasses, RowMarks. [verified-by-code:95-133]
- `void reduce_unique_semijoins(PlannerInfo *root)` — turns SEMI joins
  into INNER joins when the inner side is provably unique for the join
  clauses. Implemented by deleting the SpecialJoinInfo entry; the jointree
  jointype is *not* fixed up because nothing reads it afterwards.
  [verified-by-code:974-995, from-comment:963-974]
- `bool query_supports_distinctness(Query *query)` — cheap pre-check for
  `query_is_distinct_for()`. Returns true only if the subquery has
  DISTINCT / GROUP BY / aggregate / HAVING / set-op. [verified-by-code:1213-1228]
- `bool query_is_distinct_for(...)` — full distinctness proof.
- `bool innerrel_is_unique(...)` — uniqueness check used by joinpath
  selection (Memoize, unique-paths). [verified-by-code]
- `List *remove_useless_self_joins(PlannerInfo *root, List *joinlist)` —
  Self-Join Elimination (SJE): merges two scans of the same baserel
  joined on PK = PK. Gated by `enable_self_join_elimination` GUC.
  [verified-by-code:2639-2653]

## 3. Correctness — join removal preconditions

`join_is_removable` requires (line ~160 onward): join is LEFT, inner is a
single baserel, inner rel is not referenced by the upper tlist /
remaining quals / placeholdervars, AND inner is provably unique for the
join clauses (delegates to `rel_is_distinct_for` → btree/unique-index
proofs in `rel_supports_distinctness`). [verified-by-code]

## 4. Mutation discipline

When a rel is removed, `remove_rel_from_query` rewrites:
- every `RestrictInfo` (`remove_rel_from_restrictinfo`)
- every `EquivalenceClass` (`remove_rel_from_eclass`)
- the join list (`remove_rel_from_joinlist`)
- `root->simple_rel_array`, `simple_rte_array`, row marks, etc.

The "Remember to keep the code in sync with PlannerInfo" comment at line
~1968 lists everything that has to be updated. [from-comment:1968]

## 5. Surprising

- **Self-join elimination is a separate, late pass.** Doesn't fold into
  `remove_useless_joins`; requires its own joinlist-recursive walker
  (`remove_self_joins_recurse`). [verified-by-code]
- `enable_self_join_elimination` is a `bool` extern (line 54), gating the
  whole SJE pipeline. [verified-by-code]

## 6. Tags
`[verified-by-code]` ×11, `[from-comment]` ×4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
