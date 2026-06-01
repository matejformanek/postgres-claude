# joininfo.c — per-baserel joininfo list maintenance

- **Source:** 183 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

Maintains the `joininfo` list hanging off each `RelOptInfo` — the list
of join clauses that mention this rel. Tiny file.

- `have_relevant_joinclause(root, rel1, rel2)` (38) — used by
  `join_search_one_level` to prune clauseless pairings.
- `add_join_clause_to_rels(root, rinfo, relids)` (97) — push a
  RestrictInfo onto every member rel's joininfo.
- `remove_join_clause_from_rels(root, rinfo, relids)` (160) — symmetric
  for join removal / EC-derived rebuild.

Tag tally: `[verified-by-code]` ×3.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
