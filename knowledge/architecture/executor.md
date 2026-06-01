# Executor — pull-based volcano iterator

Companion: `query-lifecycle.md` (where the executor sits in the bigger
pipeline), `planner.md` (what hands a Plan tree to the executor).

The executor turns a `PlannedStmt` into tuples. The model is **demand-pull
volcano** [from-README `executor/README:6-12`]: every plan node exposes a
"give me the next tuple" call, and parents pull from children. There is no
materialisation between nodes unless a node (Sort, Hash, Material) explicitly
chooses to buffer.

## 1. Four parallel trees

There are four distinct trees the executor cares about
[from-README `executor/README:75-79`]:

| Tree | Lives in | Lifetime | Mutable? |
|------|----------|----------|----------|
| `Plan` | `PlannedStmt->planTree` and subtrees | Created by planner, may be cached across executions | **Read-only** at exec time |
| `PlanState` | `EState->es_plannedstmt` via `queryDesc->planstate` | One per executor invocation | Mutable |
| `Expr` | Embedded in Plan (`qual`, `targetlist`, …) | With its Plan | Read-only |
| `ExprState` | Compiled into a flat `steps[]` array per expression | With its PlanState | Mutable scratch space inside |

The shape rule is: **PlanState mirrors Plan, but ExprState does not mirror
Expr.** Plan and PlanState are tree-isomorphic — every Plan node has a
corresponding PlanState type, and the children are wired through
`PlanState.lefttree`/`righttree` matching `Plan.lefttree`/`righttree`
[from-comment `execnodes.h:1224-1226`]. Expressions, by contrast, are
flattened during `ExecInitExpr` into a single `ExprState` with a linear
`steps[]` array for cache-friendly interpretation (and as the substrate JIT
compiles against) [from-README `executor/README:81-114`].

The read-only Plan tree is what makes plan caching work: a `PlannedStmt` can
sit in the plan cache and be executed many times concurrently from different
backends, because none of them mutate it [from-README
`executor/README:56-59`].

## 2. Lifecycle: Start / Run / End

The top entry points are `ExecutorStart`, `ExecutorRun`, `ExecutorFinish`,
`ExecutorEnd`, all in `execMain.c`. Each is a thin wrapper that forwards to
a `standard_*` implementation, with a hook variable so extensions can
interpose (`execMain.c:124, 308, 477`).

### 2.1 `standard_ExecutorStart` (`execMain.c:143`)

1. Creates the **EState** (`CreateExecutorState`) — this allocates the
   per-query memory context that owns *everything* the executor will create
   [from-README `executor/README:273-281`]. Stashed as `estate->es_query_cxt`.
2. Switches into that context.
3. Copies the snapshot, params, source text, instrumentation flags onto the
   EState.
4. Calls `AfterTriggerBeginQuery` (unless skipped).
5. Calls `InitPlan` (`execMain.c:847`), which recursively calls `ExecInitNode`
   on the plan-tree root and builds the parallel PlanState tree.

### 2.2 `standard_ExecutorRun` (`execMain.c:318`)

Repeatedly calls `ExecProcNode(planstate)` on the root, pumping tuples into
the destination receiver, until either the result is exhausted or the
`count` cap is hit. For DML (INSERT/UPDATE/DELETE/MERGE) the work happens
inside the `ModifyTable` node at the root; the destination receiver may see
no tuples unless there is a `RETURNING` clause [from-README
`executor/README:28-42`].

### 2.3 `standard_ExecutorEnd` (`execMain.c:486`)

Calls `ExecEndPlan` (which recursively calls `ExecEndNode`), unregisters
snapshots, then `FreeExecutorState` — which destroys the per-query memory
context, reclaiming **everything** the executor allocated. `ExecEndNode`'s
job is therefore *not* to free memory but to release non-memory resources:
close relations, drop buffer pins, end heap scans [from-README
`executor/README:324-327`].

## 3. Per-node dispatch

`execProcnode.c` is the only file that knows how to construct, run, and tear
down every node type. It does so via three giant `switch (nodeTag(node))`
statements:

- `ExecInitNode` (`execProcnode.c:142`) — dispatches to `ExecInitFoo`.
- `ExecProcNode` — **not** a switch! Instead, the function-pointer
  `PlanState.ExecProcNode` is set inside each `ExecInitFoo` to the right
  per-node function, and the indirect call goes there directly. This is
  faster than a switch because the predicted call target is stable for the
  lifetime of the plan. The first call goes through `ExecProcNodeFirst`,
  which does the stack-depth check and installs the real callback (or an
  instrumentation wrapper) for all subsequent calls [verified-by-code
  `execProcnode.c:391, 430, 444-470`].
- `ExecEndNode` (`execProcnode.c:543`) — dispatches to `ExecEndFoo`.

Nodes that don't produce one-tuple-at-a-time results (Hash building, Bitmap
construction) go through `MultiExecProcNode` (`execProcnode.c:488`) instead;
this is a smaller switch, and the per-node MultiExec function returns a
hashtable or bitmap as a `Node *`.

## 4. EState, ExprContext, and memory

```
EState (per-query)
 ├─ es_query_cxt              ← MemoryContext, owns everything below
 ├─ es_snapshot
 ├─ es_param_list_info / es_param_exec_vals
 ├─ es_processed              ← tuples returned at the top
 ├─ es_top_eflags             ← EXEC_FLAG_EXPLAIN_ONLY, etc.
 ├─ es_instrument             ← bitmap of InstrumentOption flags
 ├─ es_jit_flags
 └─ ...
```

[from-code `execnodes.h:690-…`]

The **per-query context** holds all PlanState and ExprState nodes and any
long-lived scratch buffers — long-lived meaning "lasts as long as the query"
[from-README `executor/README:279-281`].

The **per-tuple context** (`ExprContext.ecxt_per_tuple_memory`) is where
expression evaluation allocates. It is reset before each tuple of work, so
short-lived palloc'd objects (Datum results, intermediate string copies, …)
go away automatically [from-README `executor/README:282-287`]. Each PlanState
typically owns one ExprContext via `ExecAssignExprContext`, and the per-tuple
reset is the caller's responsibility — for example NestLoop calls
`ResetExprContext(econtext)` at the top of every `ExecNestLoop` invocation
[verified-by-code `nodeNestloop.c:92`].

`ExprContext` (`execnodes.h:281`) carries the tuple-slot pointers expressions
read from:
- `ecxt_scantuple` — the SCAN_VAR fetch target (the current row from the
  underlying scan).
- `ecxt_innertuple` / `ecxt_outertuple` — the inputs at a join node.
- `ecxt_param_exec_vals` — runtime values for `PARAM_EXEC` parameters (subplan
  results, NestLoop pushdown values).

`Var` expressions compile to step opcodes that load directly from one of
these slots' `tts_values[]` arrays, so the slot pointers are effectively the
calling convention for expression evaluation.

## 5. The projection model — TupleTableSlot

Tuples flow between nodes as `TupleTableSlot *` (`execTuples.c`), not as raw
`HeapTuple`. A slot is an abstract container: it can hold a `HeapTuple`, a
`MinimalTuple`, a virtual tuple (already-deconstructed Datum array), or a
buffer-pinned tuple. The slot's `ops` vtable handles deconstruction lazily
— `slot_getattr(slot, attno, …)` materialises columns up to `attno` on
demand.

Projection (`ProjectionInfo`, set up in `ExecAssignScanProjectionInfo` and
friends) is an `ExprState` whose final `EEOP_ASSIGN_*` steps write into the
target slot's `tts_values[]`/`tts_isnull[]` arrays, marking the slot as
"virtual" (no heap tuple yet) [from-README `executor/README:218-228`]. This
means a node that only renames or rearranges columns does **zero** copying.

Per-node slots a `ScanState` owns:

- `ss_ScanTupleSlot` — the raw input tuple from the table AM.
- `ps.ps_ResultTupleSlot` — what `ExecProcNode` returns (post-projection,
  post-qual).

For nodes that don't project (qual present but tlist trivially matches scan
output), `ps_ProjInfo` is NULL and `ps_ResultTupleSlot` is just the scan slot
— this is why `ExecInitSeqScan` picks one of four `ExecProcNode`
specialisations depending on `(qual != NULL, ps_ProjInfo != NULL)`
[verified-by-code `nodeSeqscan.c:272-291`].

## 6. ReScan, params, and inner-loop reuse

A nestloop drives its inner subplan once per outer tuple, but it does **not**
re-init the inner each time. Instead it:

1. Fetches the next outer tuple from `ExecProcNode(outerPlan)`.
2. Copies outer Var values into `PARAM_EXEC` slots that the inner plan
   references (`nestParams`, `nodeNestloop.c:129-146`).
3. Sets `innerPlan->chgParam` to the bitmap of changed param IDs.
4. Calls `ExecReScan(innerPlan)`.

`ExecReScan` is the cooperative reset: a node like Sort, which already has
its output materialised, can check `chgParam` against the params its
subtree actually depends on — if none changed, it just rewinds its tape and
skips the rescan entirely. This is the "moderately intelligent scheme"
mentioned in the README [from-README `executor/README:19-26`].

## 7. EvalPlanQual — concurrent-update handling

In `READ COMMITTED`, when an UPDATE/DELETE/MERGE finds a row that has been
concurrently modified, it can't just abort like a serialisable transaction
would. Instead it [from-README `executor/README:355-401`]:

1. Waits for the concurrent transaction to commit.
2. Re-runs **the same query** with a synthesised scan that returns only the
   modified tuple in place of the original one.
3. If the rerun returns a tuple, the modified row still passes the quals, so
   we update *that* row instead.

The per-relation scans get tweaked to return the EPQ tuple via a special
`EvalPlanQual` slot. This is why `ExecInitSeqScan` checks
`estate->es_epq_active` and installs a separate `ExecSeqScanEPQ` variant
when EPQ is active [verified-by-code `nodeSeqscan.c:276-277, 206`].

## 8. Async execution (Append over ForeignScan)

A modern wrinkle in the otherwise pull-only model: an Append node sitting
over multiple ForeignScans can issue non-blocking requests to each child via
`ExecAsyncRequest`, run an event loop with `ExecAppendAsyncEventWait`, and
collect results via the children's `ExecAsyncResponse` callback
[from-README `executor/README:412-449`]. Only `Append` is an async consumer
today, and only `ForeignScan` is async-capable. The `PlanState.async_capable`
flag marks the latter.

## 9. Worked example: `SELECT … FROM dept, emp WHERE …`

Lifted from the file header at `execProcnode.c:25-71`:

```
                NestLoop
                /     \
           SeqScan   SeqScan
            dept       emp
```

1. `standard_ExecutorStart` → `InitPlan` → `ExecInitNode(NestLoop)` →
   `ExecInitNestLoop` → recursively `ExecInitNode` for each scan →
   `ExecInitSeqScan` opens the relations and creates scan slots.
2. `standard_ExecutorRun` calls `ExecProcNode(nestloopstate)` in a loop.
   Each call resolves indirectly to `ExecNestLoop`, which:
   - pulls one outer tuple by calling `ExecProcNode(outerPlanState(nl))` →
     `ExecSeqScan` → returns next dept row.
   - rescans inner, then pulls inner tuples one at a time, evaluates the
     join qual, emits matching join tuples.
3. When `ExecSeqScan` on `dept` returns NULL, the join ends.
4. `standard_ExecutorEnd` → `ExecEndNode(NestLoop)` → recurses → each
   `ExecEndSeqScan` calls `table_endscan` and closes the relation
   [verified-by-code `nodeSeqscan.c:303-333`]. Then `FreeExecutorState`
   destroys the per-query context and the entire PlanState tree disappears
   in one stroke.

That is the executor in one diagram and one page.
