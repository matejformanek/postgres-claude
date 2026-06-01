# nodeMaterial.c

- **Source:** `source/src/backend/executor/nodeMaterial.c` (≈350 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Buffers child output in a Tuplestorestate so the parent can rescan, mark/
restore, or read backwards without driving the subtree again. Two common
reasons the planner inserts Material:

1. The subplan is **expensive** and the parent will rescan it (e.g. NestLoop
   inner side when the outer is short — but the inner is non-trivial).
2. The subplan **doesn't support mark/restore** but the parent needs it
   (e.g. MergeJoin inner that is not Sort/SeqScan).

[from-comment] `:14-37`

## Mechanics

`ExecMaterial`:
- If we've already advanced to the end of the buffered store and need
  more, pull one row from outer, stash into `Tuplestorestate`, return it.
- If we're mid-store (after a rescan or a backward step), read from
  the store.

Tuplestorestate handles spilling to disk past `work_mem`.

## ReScan

Optimization: if no params changed below, just `tuplestore_rescan` —
return the same rows again from offset 0 without re-running outer.
This is what lets NestLoop with a Material'd inner avoid repeated
sub-plan execution.

## Tags

- [verified-by-code] decision logic at top of ExecMaterial.
- [from-comment] interface comment at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
