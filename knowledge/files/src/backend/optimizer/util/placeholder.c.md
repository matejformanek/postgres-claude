# placeholder.c — PlaceHolderVar / PlaceHolderInfo

- **Source:** 678 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

PlaceHolderVars wrap subquery output expressions that need to retain
their identity across the join level where they're evaluated (e.g. so
NULL-extension from an outer join above doesn't NULLify them before
they're computed). PHIs track the eval level and required-relids.

## Public entries

- `make_placeholder_expr` (55) — wrap an expr in PHV.
- `find_placeholder_info` (84) — lookup/create PHI for a PHV.
- `find_placeholders_in_jointree` (186) — pre-deconstruct walk.
- `fix_placeholder_input_needed_levels` (301) — bubble eval level up.
- `add_placeholders_to_base_rels` (328), `add_placeholders_to_joinrel`
  (357), `placeholder_is_eval_at_relids` (492),
  `find_placeholders_in_expr` (401), `phinfo_get_relids` (560),
  `contain_placeholder_references` (613).

## Invariant

After `deconstruct_jointree` runs, no new PHIs may be created — that's
why `find_lateral_references` must run before it (it can create PHIs).
[from-comment in initsplan.c:1090-1092]

Tag tally: `[verified-by-code]` ×3, `[from-comment]` ×1.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
