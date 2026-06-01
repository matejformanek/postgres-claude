# inherit.c — inheritance/partition expansion into appendrel children

- **Source:** 958 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

Implements `expand_inherited_rtentry` and partition expansion: turns a
single inheritance/partition parent RTE into the parent + N child RTEs +
N AppendRelInfos. Called by `add_other_rels_to_query` in initsplan.c.

- `expand_inherited_rtentry(root, rel, parentrte, parentRTindex)` (87) —
  top entry; uses pg_inherits + partition descriptor.
- `apply_child_basequals(...)` (838) — push parent's baserestrictinfo
  down onto a child, with Var translation via AppendRelInfo.

Tag tally: `[verified-by-code]` ×2.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
