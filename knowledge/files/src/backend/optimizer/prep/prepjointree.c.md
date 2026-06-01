# prepjointree.c — subquery flatten, OJ reduce, jointree manipulation

- **Source:** `source/src/backend/optimizer/prep/prepjointree.c` (4742 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

The first big planner preprocessing module — folds subqueries and
non-trivial join expressions into the parent's jointree where legal,
and simplifies outer joins. Many later optimizations (EC, FK matching,
join removal) work only because the structure is flattened here first.

## 2. Required invocation order (from top comment, lines 6-15)

```
preprocess_relation_rtes
replace_empty_jointree
pull_up_sublinks
preprocess_function_rtes
pull_up_subqueries
flatten_simple_union_all
[expression preprocessing — JOIN-alias-var expansion, qual canonicalization]
reduce_outer_joins
remove_useless_result_rtes
```

Every step depends on earlier steps; deviating from this order will
break invariants other modules rely on.

## 3. Key public entries

| Line | Function | Notes |
|---|---|---|
| 190 | `transform_MERGE_to_join(parse)` | MERGE source + target glued into one jointree |
| 420 | `preprocess_relation_rtes` | Expand virtual generated columns; **uses index-style iteration** so new RTEs added during the walk get visited too [from-comment:413-417] |
| 611 | `replace_empty_jointree(parse)` | Substitute RTE_RESULT when prep created an empty jointree; non-recursive (other passes call it on subqueries) [from-comment:601-607] |
| 669 | `pull_up_sublinks` | EXISTS / IN / NOT IN SubLinks → semi/anti joins; runs *before* qual canonicalization so traverses raw AND chains [from-comment:660-668] |
| 1172 | `preprocess_function_rtes` | Const-simplify FUNCTION RTE expressions so allpaths.c can recognize const args; scribbles on input [from-comment:1158-1170] |
| 1219 | `pull_up_subqueries` | The big one: subselect-in-FROM → parent jointree merge; also UNION ALL → appendrel [from-comment:1212-1217] |
| 3133 | `flatten_simple_union_all` | Top-level UNION ALL flatten path that complements pull_up_simple_union_all; handles ORDER-BY-bearing cases [from-comment:3120-3130] |
| 3255 | `reduce_outer_joins` | Detect strict quals above an outer-join nullable side → demote to inner / anti-join. Must run *after* expression preprocessing (qual canonicalization + JOIN alias expansion) [from-comment:3245-3253] |
| 3886 | `remove_useless_result_rtes` | Drop RTE_RESULT nodes left over from pullup. "We used to do this in pull_up_subqueries but it's simpler and more effective separately." [from-comment:3875-3884] |
| 4532 | `get_relids_in_jointree(jt, include_OJ, include_inner)` | Standard relid sets include OJ relids; `include_inner=true` is only for subquery flattening [from-comment:4520-4528] |
| 4593 | `get_relids_for_join` | base + OJ RT indexes covering a join node |

## 4. Notable

- **MERGE retrofit:** `transform_MERGE_to_join` is at the top of the file
  because MERGE was added late; its job is to fake-up a regular join so
  the rest of the planner is unaware. [verified-by-code:185-190]
- **The "must run after X" comments are the spec.** Several functions
  have comments stating exactly what preprocessing must have completed
  first; reading those is the only correct way to add a new pass.
- **Strict qual recognition** (`reduce_outer_joins`) is what enables
  many later EC and join-removal optimizations. [from-comment:3245-3253]

## 5. Tags
`[verified-by-code]` ×4, `[from-comment]` ×11
