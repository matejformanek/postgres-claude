# nodeMergejoin.c

- **Source:** `source/src/backend/executor/nodeMergejoin.c` (≈1500 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Classic sort-merge join. Outer and inner inputs are pre-sorted on the join
keys; we walk both in lockstep, advancing the lesser side until they match,
then emit the cartesian product of equal "groups". The file header has a
beautiful textbook example. [from-comment] `:15-45`

## State machine in `ExecMergeJoin` `:596`

`mj_JoinState ∈ { EXEC_MJ_INITIALIZE_OUTER, EXEC_MJ_INITIALIZE_INNER,
EXEC_MJ_JOINTUPLES, EXEC_MJ_NEXTOUTER, EXEC_MJ_TESTOUTER, EXEC_MJ_NEXTINNER,
EXEC_MJ_SKIP_TEST, EXEC_MJ_SKIPOUTER_ADVANCE, EXEC_MJ_SKIPINNER_ADVANCE,
EXEC_MJ_ENDOUTER, EXEC_MJ_ENDINNER }`

The big `for(;;) switch` walks through these. The README's "(0 1 1 2 5 5 5 6)
vs (1 3 5 5 5 5 6)" example is exactly what the state machine sequences
through.

## Cartesian on equal groups

When a match is found we **mark** the inner position (`ExecMarkPos`), then
emit all inner rows equal to the outer key, then on the next outer row, if
its key also equals that of the marked group, we **restore** (`ExecRestrPos`)
and replay the inner group. This is why the planner places a Material below
the inner side if the inner is not naturally mark/restore-capable
(`ExecSupportsMarkRestore` in execAmi.c controls this).

## Comparator: `MJCompare(mergestate)` `:388`

Walks the per-clause `MergeJoinClause[]` array. Each clause has precomputed
SortSupport: ascending vs descending and NULLS FIRST/LAST. Returns -1, 0,
or +1.

## Outer join handling

- `MJFillOuter(node)` `:449` — emit current outer with all-null inner (LEFT
  unmatched).
- `MJFillInner(node)` `:480` — emit current inner with all-null outer
  (RIGHT/FULL unmatched).

For FULL outer, both fills fire; the matched-bit on the inner is tracked so
unmatched-inner is emitted at outer EOS.

## Quals: `MJExamineQuals` `:177`

Init time: walks `mergeclauses` to build `MergeJoinClause[]` with the type-
specific compare functions resolved. Sort orderings come from the planner-
provided `mergeStrategies` and `mergeNullsFirst` arrays.

## Tags

- [verified-by-code] state machine constants + entry points.
- [from-comment] the worked example at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
