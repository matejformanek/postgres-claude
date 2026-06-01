# execAmi.c

- **Source:** `source/src/backend/executor/execAmi.c` (654 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Dispatcher for the **executor "access method" operations** on a PlanState:
ReScan, MarkPos, RestrPos, and the planner-time predicates
SupportsMarkRestore / SupportsBackwardScan / MaterializesOutput. Big switch
on `nodeTag(node)` calling the right `ExecReScan<NodeType>` etc.
[from-comment] file is intentionally just dispatch glue.

## Entry points

- `ExecReScan(PlanState *node)` `:78` — top-level rescan. First resets
  `chgParam`-driven invalidations on children, then dispatches per node
  type to e.g. `ExecReScanSeqScan`, `ExecReScanAgg`. The dispatch also
  recursively rescans children if the node has no node-type-specific
  ReScan (e.g. Hash, Material's downstream).
- `ExecMarkPos(node)` `:328` — only valid for nodes that report
  ExecSupportsMarkRestore. Used by MergeJoin's inner side to remember
  position before a candidate-match group, so `ExecRestrPos` can rewind
  on tie groups.
- `ExecRestrPos(node)` `:377` — restore.
- `ExecSupportsMarkRestore(Path *pathnode)` `:419` — planner-time predicate.
  Returns true for SeqScan / IndexScan / Material / Sort and a few others;
  used to decide when MergeJoin needs to insert a Material below its inner.
- `ExecSupportsBackwardScan(Plan *node)` `:512` — recursive check whether
  scan-backward (cursor) is supported all the way down a plan subtree.
- `ExecMaterializesOutput(NodeTag plantype)` `:636` — "does this node type
  buffer its output so its parent can rewind without driving the subtree
  again?" True for Sort, Material, CteScan, FunctionScan with materialize,
  WorktableScan. Used by Append / MergeAppend to decide whether a child
  needs an extra Material wrapper.

## Shutdown

- `ExecShutdownNode(node)` — pre-shutdown pass run before ExecEnd; used by
  parallel-aware nodes (Gather, GatherMerge, parallel Hash, parallel Append)
  to release shared resources / tell workers to finish before
  ParallelContext destruction. Called from ExecutorEnd before ExecEndNode.

## Tags

- [verified-by-code] entry-point line numbers and dispatch structure.
- [inferred] role of ExecMaterializesOutput in the planner's Material decisions.
