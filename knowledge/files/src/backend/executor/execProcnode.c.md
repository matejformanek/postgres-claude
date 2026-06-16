# execProcnode.c

- **Source:** `source/src/backend/executor/execProcnode.c` (968 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

The plan-node dispatch hub. Contains three giant `switch(nodeTag(node))`
statements — `ExecInitNode`, `MultiExecProcNode`, `ExecEndNode` — plus
the per-PlanState `ExecProcNode` indirection trick. Per the top
comment: "this used to be three files. It is now all combined into one
file so that it is easier to keep the dispatch routines in sync when
new nodes are added." [from-comment] `:19-24`

There is no `ExecProcNode` switch — the per-PlanState `ExecProcNode`
function pointer (installed during each node's `ExecInit*`) is called
directly. Only Init / MultiExec / End fan out from here.

## The three dispatch tables

### `ExecInitNode(plan, estate, eflags)` `:142`

Recursive plan-tree walker. For each Plan node:
1. `check_stack_depth()` — `:159`, separately from `ExecProcNodeFirst`
   because init alone can overrun a deep tree.
2. `switch(nodeTag(node))` over **42 node types** grouped as control /
   scan / join / materialization. `:161-389`
3. `ExecSetExecProcNode(result, result->ExecProcNode)` — wraps the
   per-node ExecProcNode in `ExecProcNodeFirst` so the first-call
   stack check + instrumentation re-wiring runs once. `:391`
4. `initPlan` loop: for every SubPlan in `node->initPlan` (parameter-
   free correlated subqueries hoisted by the planner),
   `ExecInitSubPlan` and append to `result->initPlan`. `:401-412`
5. Allocate `Instrumentation` if `estate->es_instrument`. `:415`

The 42 cases route to `ExecInit{Result,ProjectSet,ModifyTable,Append,
MergeAppend,RecursiveUnion,BitmapAnd,BitmapOr, SeqScan,SampleScan,
IndexScan,IndexOnlyScan,BitmapIndexScan,BitmapHeapScan,TidScan,
TidRangeScan,SubqueryScan,FunctionScan,TableFuncScan,ValuesScan,
CteScan,NamedTuplestoreScan,WorkTableScan,ForeignScan,CustomScan,
NestLoop,MergeJoin,HashJoin, Material,Sort,IncrementalSort,Memoize,
Group,Agg,WindowAgg,Unique,Gather,GatherMerge,Hash,SetOp,LockRows,
Limit}`.

### `MultiExecProcNode(node)` `:488`

For node types that don't produce per-tuple slots but instead an
opaque result — currently 4: `Hash` (hashtable), `BitmapIndexScan`
(TIDBitmap), `BitmapAnd` / `BitmapOr` (combined TIDBitmap). `:499-525`

Side-effect first: if `chgParam != NULL`, call `ExecReScan(node)`
before dispatching — `:496-497`. This is the same param-change-driven
rescan trigger used by all multi-input combinators.

No instrumentation tick is performed here — "each per-node function
must provide its own instrumentation support". [from-comment] `:481-485`

### `ExecEndNode(node)` `:543`

Mirror of `ExecInitNode`. Iterates the 42 (well, 39 — see below) node
types, calling each `ExecEnd*`. `:564-743`

Three node types appear in the table with **no cleanup**:
`ValuesScanState`, `NamedTuplestoreScanState`, `WorkTableScanState`
fall through to a shared break. `:735-738`

Before dispatch: clears `chgParam` if non-NULL (`bms_free` + set NULL,
`:558-562`) — this is the only place that bitmap is reaped.

## The `ExecProcNodeFirst` first-call trick `:448`

The per-PlanState `ExecProcNode` callback is NOT the node's real impl.
At `ExecInitNode` end, `ExecSetExecProcNode` `:430` stores the real
function into `node->ExecProcNodeReal` and points `node->ExecProcNode`
at the shim `ExecProcNodeFirst`. On the very first call it:

1. Performs a `check_stack_depth()` — expensive on some architectures
   (e.g. x86), so done only once per node. `:457`
2. If `node->instrument` is set, swap in `ExecProcNodeInstr` (which
   wraps Real with `InstrStartNode` / `InstrStopNode`); otherwise
   install `ExecProcNodeReal` directly. `:464-467`
3. Tail-call the now-installed function. `:469`

This means **steady-state ExecProcNode is one indirect call with zero
overhead**, which matters a lot when the loop calls it once per tuple.

`ExecSetExecProcNode` `:430` is the public re-installation API for
nodes that swap impls (e.g. nodeSeqscan's four specialized variants
chosen at init time based on whether quals/projection are needed).
The shim is reinstalled so instrumentation wrapping survives. `:432-440`

## `ExecShutdownNode` `:753`

Optional pre-`ExecEnd` pass that lets nodes release async resources
without ending. Walks via `planstate_tree_walker` and only fires for 6
types: `Gather`, `ForeignScan`, `CustomScan`, `GatherMerge`, `Hash`,
`HashJoin`. `:781-803`. Used by `ExecutePlan` to release parallel
workers / DSM segments as soon as the executor knows it won't need to
back up (i.e. `!(es_top_eflags & EXEC_FLAG_BACKWARD)`).

Instrumentation accounting subtlety: starts the node's instrument
running across shutdown so that worker buffer-usage stats get
attributed to (e.g.) the Gather node, but only if the node ran at
least once — otherwise we'd falsely claim it executed. [from-comment]
`:767-775`

## `ExecSetTupleBound` `:828`

Push a parent-imposed LIMIT down into child nodes that can use it:
`Sort`, `IncrementalSort` (bounded sort), `Append` / `MergeAppend`
(propagate to every child), `Result` (descend if projecting),
`SubqueryScan` (descend iff no qual that could discard rows),
`Gather` / `GatherMerge` (workers honor bound). The list of safe
descents is deliberately conservative — any node that can "discard or
combine input rows" blocks propagation. [from-comment] `:962-967`

## Invariants

- 42 cases in `ExecInit`, 39 in `ExecEnd` — keep in sync when adding a
  new node type. The top comment explicitly cites "easier to keep
  dispatch routines in sync" as the reason these live in one file.
  [from-comment] `:21-24`
- `ExecProcNode` is never dispatched from this file — it's the
  function pointer in `PlanState`, set by each `ExecInit*`. Only
  Init / MultiExec / End / Shutdown fan out by tag. [verified-by-code]
- `check_stack_depth` must be called in both `ExecInitNode` and
  `ExecProcNodeFirst` because init can recurse without ever calling
  ExecProcNode (e.g. EXPLAIN-only) and ProcNode can run without
  re-init. [from-comment] `:155-158, 553-556`
- `chgParam` is bms_freed in `ExecEndNode` — `proc.c`/`ReScan` does
  the same when consuming it; this file is the catch-all on shutdown
  for nodes that never got rescanned. [verified-by-code] `:558-562`

## Cross-refs

- `knowledge/architecture/executor.md` — frames how the Init/Proc/End
  trio relates to the Plan vs PlanState split.
- `.claude/skills/executor-and-planner/SKILL.md` — already cites the
  `ExecProcNodeFirst` trick.
- `knowledge/files/src/backend/executor/execMain.c.md` — `InitPlan` /
  `ExecEndPlan` are the top-level callers.
- The included `executor/node*.h` headers `:77-119` — every per-node
  driver file lives behind one of these.

## Tags

- [verified-by-code] dispatch counts (42 init / 39 end), the
  ExecProcNodeFirst trick, the MultiExec 4-type list.
- [from-comment] "one file to keep dispatch in sync" rationale; the
  worked Nest Loop walkthrough at `:25-72`; the ExecShutdownNode
  instrumentation comment.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new plan node](../../../../scenarios/add-new-plan-node.md)

<!-- scenarios:auto:end -->
