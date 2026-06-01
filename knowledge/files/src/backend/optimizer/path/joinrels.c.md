# joinrels.c — DP level construction and joinrel materialization

- **Source:** `source/src/backend/optimizer/path/joinrels.c` (2114 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

Implements the bottom-up dynamic-programming sweep that
`standard_join_search` runs per level, and the per-pair "is this join
even legal?" / "build the joinrel" plumbing. [verified-by-code]

## 2. Public entries

| Line | Function | Notes |
|---|---|---|
| 77 | `join_search_one_level(root, level)` | One DP level. Reads `join_rel_level[1..level-1]`, populates `join_rel_level[level]`. [from-comment:65-71] |
| 663 | `init_dummy_sjinfo(sjinfo, left, right)` | Synthesize a SpecialJoinInfo for inner joins (which don't have one) so downstream code can take a uniform pointer [from-comment:649-657] |
| 698 | `make_join_rel(root, rel1, rel2)` | Attempt to build the joinrel of these two rels and add paths via `add_paths_to_joinrel` (joinpath.c). May return NULL when the attempted ordering is illegal (outer-join restrictions, IN/EXISTS-converted joins). [from-comment:687-694] |
| 799 | `add_outer_joins_to_relids(root, input, sjinfo, pushed_down_joins)` | Apply outer-join identity 3 (pushdown): output relids include any outer joins completed by this step; if `pushed_down_joins` non-NIL, append their SpecialJoinInfos. [from-comment:783-790] |
| 1253 | `have_join_order_restriction(root, rel1, rel2)` | Is *some* SpecialJoinInfo forcing us to join these two now? Used by `join_search_one_level`'s "last ditch" / restriction-honoring passes. [from-comment:1238-1249] |
| 1463 | `is_dummy_rel(rel)` | True if a baserel has been proven empty (single dummy path attached) |
| 1512 | `mark_dummy_rel(rel)` | Replace pathlist with a single empty-rel path. **Subtle:** must allocate in the same MemoryContext the RelOptInfo lives in, to survive GEQO cycle teardown when marking a baserel. [from-comment:1495-1505] |

## 3. join_search_one_level: the three passes

At level k, three sources of joinrels are tried, in order:
1. **Pair from level k-1 with level 1** (parameterized by `joinrels[k-1]`
   and `joinrels[1]`) — left-deep extension.
2. **Bushy combinations**: `joinrels[i]` × `joinrels[k-i]` for
   `i ∈ [2, k/2]`.
3. **"Last ditch"** for jointree restrictions and clauseless joins that
   the first two passes missed. [verified-by-code]

`have_join_order_restriction` exists specifically because pass 3 must
not be triggered for ordinary clauseless cases (which would explode
search space) — it's only invoked when an SJI says "must join now".
[from-comment:1238-1249]

## 4. GEQO interaction

`mark_dummy_rel` has an explicit comment about the GEQO short-lived
memory context: a dummy path on a *baserel* must survive across GEQO
exploration cycles, but a dummy on a *joinrel* should live in the join
context. The code picks the rel's own context. [from-comment:1495-1505]

## 5. Tags
`[verified-by-code]` ×4, `[from-comment]` ×6

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
