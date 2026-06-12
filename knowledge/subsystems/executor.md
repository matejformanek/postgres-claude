# Executor — subsystem synthesis

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Tom Lane (41), Peter Eisentraut (37), David Rowley (37), Amit Langote (28)
- **Top reviewers (last 24mo):** Andres Freund (25), Tom Lane (21), Chao Li (21), Tomas Vondra (18)
- **Recent landmark commits (12mo):**
  - `e6d6e32f424 (Álvaro Herrera, 2026-01-28): Fix duplicate arbiter detection during REINDEX CONCURRENTLY on partitions`
  - `dd78e69cfc3 (Melanie Plageman, 2026-04-06): Allocate separate DSM chunk for parallel Index[Only]Scan instrumentation`
  - `487cf2cbd2f (Andrew Dunstan, 2026-03-12): Extend DomainHasConstraints() to optionally check constraint volatility`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Companion architecture doc:** `knowledge/architecture/executor.md`
  (Volcano model, four trees, EState lifecycle, NestLoop worked example).
- **Companion docs:** `knowledge/architecture/query-lifecycle.md`,
  `knowledge/idioms/node-types-and-lists.md`, `knowledge/idioms/memory-contexts.md`.
- **Per-file corpus:** `knowledge/files/src/backend/executor/*.md` (~60 files).

This doc complements the architecture overview by going deeper on subsystem-level
**patterns and cross-cutting concerns**: how compiled ExprStates plug into every
node, how memory and slot ownership move, how parallel execution mutates the
serial model, how DML factors into Prologue/Act/Epilogue, and the pitfalls that
catch people writing or reviewing executor code.

---

## 1. What the executor is

The executor turns a `PlannedStmt` into tuples using a **pull-based Volcano
iterator** model: every plan node exposes "give me the next tuple" and parents
pull from children. No intermediate materialization unless a node (Sort, Hash,
Material, CTE, FunctionScan with materialize, WorktableScan) explicitly buffers
[see `knowledge/architecture/executor.md` §1; `execAmi.c:636` for the
`ExecMaterializesOutput` predicate list, via `knowledge/files/.../execAmi.c.md`].

Four parallel trees coexist [via `knowledge/architecture/executor.md` §1]:

| Tree       | Mutable?    | Substrate                          |
|------------|-------------|------------------------------------|
| `Plan`     | read-only   | `PlannedStmt->planTree`, planner-built |
| `PlanState`| mutable     | tree-isomorphic to Plan, per-EState |
| `Expr`     | read-only   | embedded inside Plan nodes         |
| `ExprState`| mutable     | **flat `steps[]`**, not tree-isomorphic |

The key shape rule: **PlanState mirrors Plan; ExprState does NOT mirror Expr**.
Expressions are compiled (by `execExpr.c`) into a linear `steps[]` array for
cache-friendly interpretation and as the substrate JIT compiles against
[via `knowledge/files/.../execExpr.c.md`; `source/src/backend/executor/README:81-160`].

Why read-only Plan matters: a `PlannedStmt` can sit in the plan cache and be
executed concurrently by many backends because none of them mutate it
[from-README `executor/README:56-59`].

### 1.1 Dispatch styles in the executor

The executor mixes **three** different dispatch styles. Knowing which is where
is essential when reading code:

1. **PlanState dispatch is per-node function-pointer** (`PlanState.ExecProcNode`),
   set by `ExecInitFoo`. Not a switch [via `knowledge/architecture/executor.md` §3;
   verified at `source/src/backend/executor/execProcnode.c:448` `ExecProcNodeFirst`].
2. **PlanState init/end/MultiExec/ReScan/MarkPos use big `switch (nodeTag)`**
   in `execProcnode.c` and `execAmi.c` — these are infrequent calls so the
   indirection cost is fine [`execProcnode.c:142,488,543`; `execAmi.c:78,328,
   377,419,512,636`; via `knowledge/files/.../execAmi.c.md`].
3. **ExprState dispatch is direct-threaded** (computed gotos on gcc/clang) or
   switch-threaded (portable fallback), inside one big function
   `ExecInterpExpr` [via `knowledge/files/.../execExprInterp.c.md`;
   `execExprInterp.c:90-93,273-279,470`].

---

## 2. Lifecycle: Start / Run / Finish / End

The top-of-stack entry points all live in `execMain.c`. Each is a thin wrapper
that calls `standard_*` via a hookable function pointer so extensions
(pg_stat_statements, auto_explain) can interpose [`execMain.c:70-73,124,308,
417,477`; cross-ref `knowledge/architecture/executor.md` §2].

### 2.1 `standard_ExecutorStart` (`execMain.c:143`)

1. `CreateExecutorState()` allocates the per-query memory context (`es_query_cxt`)
   that **owns everything** the executor will allocate
   [via `knowledge/files/.../execUtils.c.md`; from-README `executor/README:273-281`].
2. Switches into that context.
3. Copies snapshot, params, source text, instrumentation flags onto the EState.
4. `AfterTriggerBeginQuery` unless skipped.
5. `InitPlan` (`execMain.c:847`) recursively calls `ExecInitNode` on the root
   and builds the parallel PlanState tree.

### 2.2 `standard_ExecutorRun` (`execMain.c:318`)

Loops on `ExecProcNode(root)`, pumping tuples into the `DestReceiver` until the
result is exhausted or `count` is hit. For DML (INSERT/UPDATE/DELETE/MERGE),
all real work happens inside the `ModifyTable` root node; the DestReceiver
typically sees nothing unless there is a `RETURNING` clause
[from-README `executor/README:28-42`].

### 2.3 `standard_ExecutorEnd` (`execMain.c:486`)

`ExecEndPlan` (`execMain.c:1565`) walks the PlanState tree calling `ExecEndNode`,
then unregisters snapshots, then `FreeExecutorState` destroys the per-query
context — which reclaims **every** PlanState, ExprState, ExprContext, slot, and
scratch buffer in one stroke. `ExecEndNode`'s job is therefore *not* to free
memory but to release non-memory resources: close relations, drop buffer pins,
end heap scans, end FDW scans [from-README `executor/README:324-327`;
verified-by-code `execProcnode.c:543` and per-node `ExecEndFoo`; via
`knowledge/files/.../execUtils.c.md`].

This is why every per-node `ExecEndFoo` is short: the heavy lifting is the
context teardown that happens *after* it returns.

### 2.4 `ExecShutdownNode` is separate from `ExecEndNode`

`ExecShutdownNode` (`execProcnode.c:753`) runs **before** ExecEndNode and is
specifically the hook parallel-aware nodes use to release shared resources or
tell workers to finish before the ParallelContext is destroyed
[via `knowledge/files/.../execAmi.c.md`; verified at `execProcnode.c:753-759`].
Plain serial nodes have no ShutdownNode method.

### 2.5 The `execProcnode.c` mini-dispatch

`execProcnode.c` is the only file that knows how to construct, run, and tear
down *every* node type:

- `ExecInitNode` (`execProcnode.c:142`) — switch on `nodeTag(Plan)` to
  `ExecInitFoo`. Each `ExecInitFoo` is responsible for setting
  `PlanState.ExecProcNode` to the per-node row function (often via a wrapper
  `ExecProcNodeFirst` that does stack-depth check on first call, then installs
  the real callback).
- `MultiExecProcNode` (`execProcnode.c:488`) — for nodes that **don't** return
  one tuple at a time: Hash (returns a `HashJoinTable*`), BitmapIndexScan /
  BitmapAnd / BitmapOr (return a `TIDBitmap*`). Returns a `Node *`.
- `ExecEndNode` (`execProcnode.c:543`) — switch dispatch to per-node end.

### 2.6 The execAmi.c mini-dispatch — "executor access methods"

A **second**, separate dispatch table lives in `execAmi.c` for ops that don't
fit the per-row callback pattern [via `knowledge/files/.../execAmi.c.md`]:

- `ExecReScan(node)` `:78` — cooperative reset. Children with no node-specific
  ReScan are walked recursively.
- `ExecMarkPos(node)` `:328` / `ExecRestrPos(node)` `:377` — mark/restore for
  MergeJoin's inner side. Only valid for nodes reporting
  `ExecSupportsMarkRestore`.
- `ExecSupportsMarkRestore(Path*)` `:419` — planner-time predicate.
- `ExecSupportsBackwardScan(Plan*)` `:512` — planner-time predicate, walked
  recursively for cursor support.
- `ExecMaterializesOutput(NodeTag)` `:636` — true for Sort, Material, CteScan,
  WorktableScan, materializing FunctionScan. Used by Append/MergeAppend to
  decide if a child needs a Material wrapper above it.

**Naming warning:** these "executor access methods" are entirely distinct from
**table access methods** (`TableAmRoutine`, `tableam.h`) — same word, different
layer [via `knowledge/architecture/executor.md` §3].

---

## 3. ExprState compilation and the interpreter

The architecture doc covers the high-level "Var compiles to a load from a
slot" story. Here are the patterns and pitfalls that show up across every node
that uses expressions.

### 3.1 Compilation entry points (`execExpr.c`)

[Via `knowledge/files/.../execExpr.c.md`]

- `ExecInitExpr(Expr*, PlanState *parent)` `:142` — most common; resolves Vars
  against the parent's input slots and Params against
  `estate->es_param_list_info`.
- `ExecInitExprWithContext` `:162` — variant taking an `ErrorSaveContext` for
  soft-error opcodes (SQL/JSON, `COPY ON_ERROR`).
- `ExecInitExprWithParams(Expr*, ParamListInfo)` `:200` — no parent PlanState;
  used by SPI and PL/pgSQL where there is no PlanState scope. Only EXTERN
  params are usable.
- `ExecInitQual(qualList, parent)` `:249` — compiles an implicit-AND list with
  `EEOP_QUAL` short-circuit semantics (NULL → false, jump on first false).
- `ExecInitCheck(qualList, parent)` `:335` — like ExecInitQual but **preserves
  NULL** semantics (used for CHECK constraints).
- `ExecPrepareExpr` / `ExecPrepareQual` / `ExecPrepareCheck` `:785+` — for
  callers with a bare `EState` (no parent PlanState). Switches to per-query
  context and runs `expression_planner` first for const-folding.

### 3.2 The compiled-ExprState builders that drive every node

The fact that **so much per-row work is one `ExecEvalExpr` call** is a major
PG-12-and-later perf story. Builders [via `knowledge/files/.../execExpr.c.md`]:

- `ExecBuildProjectionInfo(tlist, econtext, slot, parent, inputDesc)` `:391` —
  TLIST compilation. Fast path: `EEOP_ASSIGN_{INNER,OUTER,SCAN}_VAR` (one step
  per trivial Var copy). General path: evaluate expr then `EEOP_ASSIGN_TMP`.
- `ExecBuildUpdateProjection` `:568` — UPDATE specialization. Combines
  unchanged columns from old tuple with new-value SET expressions. Emits
  `EEOP_ASSIGN_TMP_MAKE_RO` so expanded datums in unchanged columns survive
  the slot transfer.
- `ExecBuildAggTrans(AggState, phase, doSort, doHash, nullcheck)` `:3704` —
  one ExprState that advances **every** transition for an Agg phase in one
  pass. This is what makes HashAgg fast: per input row, one
  `ExecEvalExpr(state)` does all transitions, with no Aggref-tree walk
  [via `knowledge/files/.../nodeAgg.c.md`].
- `ExecBuildHash32FromAttrs` `:4168` / `ExecBuildHash32Expr` `:4329` — compile
  a slot-or-expr hash to uint32, used by HashAgg / Hashjoin / Memoize.
- `ExecBuildGroupingEqual` `:4493` — compile an early-exit per-column equality
  between two slots (returns boolean).
- `ExecBuildParamSetEqual` `:4653` — Memoize uses this to compare a probe param
  vector against a cached entry.

### 3.3 Setup-prefix `FETCHSOME` optimization

The compiler runs an `ExprSetupInfo` walker over the whole Expr tree *before*
emitting any other step, collecting `last_inner/outer/scan/old/new`
AttrNumbers. Then `ExecPushExprSetupSteps` emits **one** `EEOP_*_FETCHSOME` per
used slot at the top of `steps[]`. Each `Var` step downstream becomes a pure
array fetch with no slot-deconstruct branch [via
`knowledge/files/.../execExpr.c.md`; `execExpr.c:56-69, 80-82`].

### 3.4 Direct-result-placement: subexpr results land where the consumer reads them

The architecture doc states this; here is the load-bearing operational
consequence. Each `ExprEvalStep` has explicit `resvalue`/`resnull` **pointers**,
and during compilation the result pointer of a sub-step is set to land
**directly inside the next step's `FunctionCallInfo->args[i]`**. There is no
"push to operand stack / pop into consumer" — the consumer step already sees the
value where it needs it [via `knowledge/architecture/executor.md` §1; from-comment
`execExpr.c:3-15`; from-README `executor/README:81-160`].

This is the calling convention for steps. It is also a **pitfall** (see §10).

### 3.5 Interpreter — `ExecInterpExpr` (`execExprInterp.c:470`)

[Via `knowledge/files/.../execExprInterp.c.md`]

- `HAVE_COMPUTED_GOTO` → `EEO_DISPATCH` is `goto *(op->opcode)` after
  `ExecReadyInterpretedExpr` rewrites each step's opcode field to a label
  address (`EEO_FLAG_DIRECT_THREADED`) [`execExprInterp.c:90-93,273-279`].
- Without computed gotos, the same source file is re-included with different
  EEO_* macros and produces a `switch` variant.
- A single ≈1800-line function with every opcode inlined — the hot loop
  PG perf profiles show.

### 3.6 The ExecJust* fast paths

`ExecReadyInterpretedExpr` looks at the first ~5 opcodes of a freshly compiled
program and, if they match a common idiom, replaces `evalfunc_private` with a
hardcoded routine that bypasses dispatch entirely
[`execExprInterp.c:252,288-292,293-470`]:

| Pattern                          | Handler                                     |
|----------------------------------|---------------------------------------------|
| single `Var`                     | `ExecJustInner/Outer/ScanVar` (+Virt variants) |
| single `ASSIGN_*_VAR`            | `ExecJustAssign*`                           |
| `OpExpr(CaseTestExpr)`           | `ExecJustApplyFuncToCase`                   |
| single `Const`                   | `ExecJustConst`                             |
| hash-key extraction of a Var     | `ExecJustHashInner/OuterVar(WithIV)`        |

These dominate `perf` profiles on OLTP workloads
[via `knowledge/files/.../execExprInterp.c.md`].

### 3.7 JIT-shared opcode helpers

The big-table opcodes (`ExecEvalParamExtern`, `ExecEvalArrayExpr`,
`ExecEvalFieldStore`, `ExecEvalJsonExprPath`, …) are exported helpers
[`execExprInterp.c:42-46`]. **Invariant:** these helpers must **not** dispatch
to the next step — they return, and the caller (interp or JIT) performs the
dispatch [via `knowledge/files/.../execExprInterp.c.md`; from-README].
LLVM/JIT emits direct calls to them instead of regenerating every opcode body.

### 3.8 Plancache revalidation: `ExecInterpExprStillValid`

`execExprInterp.c:2297` is the first-call wrapper installed by
`ExecReadyInterpretedExpr`. It runs `CheckExprStillValid` which verifies the
`varattno` of every `EEOP_*_VAR` step still matches the slot's TupleDesc
(schema can change between prepare and execute via the plancache). On success
the first-call wrapper replaces `evalfunc` with `ExecInterpExpr` for all
subsequent calls [via `knowledge/files/.../execExprInterp.c.md`].

---

## 4. TupleTableSlot — the executor's universal container

[Via `knowledge/files/.../execTuples.c.md`]

Tuples flow between nodes as `TupleTableSlot *`, not raw `HeapTuple`. A slot
is a container with a `TupleTableSlotOps` vtable. The four kinds
(`execTuples.c:84-87`):

| Kind                     | Storage                                          | Used for                                  |
|--------------------------|--------------------------------------------------|-------------------------------------------|
| `TTSOpsVirtual`          | `tts_values[]/tts_isnull[]`                      | Projection results, computed tuples       |
| `TTSOpsHeapTuple`        | palloc'd HeapTuple (`shouldFree`)                | Trigger inputs, materialized heap rows    |
| `TTSOpsMinimalTuple`     | MinimalTuple (no header, no system cols)         | Sort, HashAgg, Hash, tuplestore, **shm_mq** |
| `TTSOpsBufferHeapTuple`  | HeapTuple **inside a shared buffer page** + pin  | What `heap_getnext` gives you             |

A scan node's `ss_ScanTupleSlot` is BufferHeapTuple; its `ps_ResultTupleSlot`
becomes Virtual after projection. Projection writes into the result slot's
`tts_values[]`/`tts_isnull[]` via `EEOP_ASSIGN_*`, marking it virtual — a node
that only renames columns does **zero** copying
[via `knowledge/architecture/executor.md` §5; from-README `executor/README:218-228`].

### 4.1 The lazy-deformation contract

`slot_getsomeattrs(slot, attnum)` deconstructs columns 1..attnum into
`tts_values/tts_isnull`. The fast path (`slot_deform_heap_tuple`) keeps a
per-column offset cache (`tts_off`) so repeated decoding at the same depth is
amortized [via `knowledge/files/.../execTuples.c.md`]. This is the reason
ExprState compilation emits one FETCHSOME up front rather than per-Var.

### 4.2 Slot ownership invariants

- A **Virtual** slot's `tts_values[]` may point into per-tuple-context palloc'd
  memory; the next `ExecClearTuple` is what releases the slot's claim
  (`TTS_FLAG_SHOULDFREE`). This is why every node resets its per-tuple
  ExprContext after emitting a row.
- `tts_tid` is **only** valid on slots holding a real heap row (Buffer/Heap
  ops). Virtual/Minimal slots invalidate it on clear.
- `tts_tableOid` is set by the scan AM, used by triggers and EvalPlanQual to
  route back to the right partition.

These three invariants are easy to violate when writing a new scan node — see
§10.

---

## 5. EState, ExprContext, and memory

[Via `knowledge/files/.../execUtils.c.md`; `knowledge/idioms/memory-contexts.md`]

The architecture doc has the EState diagram. The operational rules:

- `CreateExecutorState()` creates `es_query_cxt`. **Everything** below — every
  PlanState, ExprState, slot, ExprContext, scratch buffer — is rooted here.
  `FreeExecutorState` destroys the context, which frees the lot.
- `ExecAssignExprContext(estate, planstate)` is boilerplate every `ExecInitFoo`
  uses; it creates one ExprContext attached to the EState and stores it on
  `planstate->ps_ExprContext`. The context's `ecxt_per_tuple_memory` is a
  child AllocSet that **expression evaluation allocates into and must be reset
  per row by the caller** (e.g. NestLoop calls `ResetExprContext(econtext)` at
  the top of each `ExecNestLoop` invocation
  [via `knowledge/architecture/executor.md` §4]).
- `CreateStandaloneExprContext(estate)` skips the link into
  `estate->es_exprcontexts` — used by callers that manage their own lifetime
  (e.g. CHECK constraint evaluation).
- `RegisterExprContextCallback(econtext, fn, arg)` — used by SRFs, JsonExpr,
  and similar to ensure cleanup at shutdown.

### 5.1 Range-table opening — the single point of truth

`ExecGetRangeTableRelation(estate, rti, isResultRel)` is the **only** place
that opens (and locks) a relation referenced by an RT index; it caches the
result in `es_relations[rti-1]` [via `knowledge/files/.../execUtils.c.md`].
`ExecOpenScanRelation` is a thin scan-node wrapper that asserts the planner
already took the lock and calls `table_open(rel, NoLock)`. This is the
invariant: **the planner records the lockmode**; the executor takes the lock
exactly once per relation, lazily, at the first access.

---

## 6. Scan-node family

[Via `knowledge/files/.../execScan.c.md`,
`knowledge/files/.../nodeIndexscan.c.md`,
`knowledge/files/.../nodeBitmapHeapscan.c.md`, et al.]

The unifying point: `execScan.c` provides `ExecScan(ScanState*, accessMtd,
recheckMtd)` — the **generic** "fetch next, apply qual, project" loop shared
by SeqScan, IndexScan, FunctionScan, ValuesScan, ForeignScan, CustomScan,
TidScan, TidRangeScan, NamedTuplestoreScan, WorkTableScan. Individual scan
nodes supply only:

- **access method** callback returning the next raw tuple in the scan slot (or
  NULL for EOS).
- **recheck method** that re-evaluates internal pushed-down quals when
  EvalPlanQual hands the node a different row.

ExecScan handles EPQ transparently: when `estate->es_epq_active` is in play,
it diverts to `EvalPlanQualNext` and re-runs qual + projection + the supplied
recheck callback [via `knowledge/files/.../execScan.c.md`].

### 6.1 Notable scan-node specifics

- **SeqScan** picks one of four `ExecProcNode` specialisations at init time
  based on `(qual != NULL, ps_ProjInfo != NULL)`, plus a separate
  `ExecSeqScanEPQ` variant if EPQ is active
  [via `knowledge/architecture/executor.md` §5; `source/.../nodeSeqscan.c:272-291,
  206`].
- **IndexScan** has an extra access method `IndexNextWithReorder` for
  approximate-ordering indexes (kNN GIST/SP-GiST with distance operators); it
  maintains a reorder heap to deliver tuples in true ORDER BY order, rechecking
  actual distances against the latest heap row [via
  `knowledge/files/.../nodeIndexscan.c.md`].
- **BitmapHeapScan** receives a `TIDBitmap` from a Bitmap{Index,And,Or} child
  via `MultiExecProcNode`, walks heap pages in physical order. Lossy pages
  (TIDBitmap collapses to page-level marks when over `work_mem`) require
  per-tuple recheck of the original index quals — EXPLAIN reports
  `Heap Blocks: exact=N lossy=M` [via `knowledge/files/.../nodeBitmapHeapscan.c.md`].
- **ForeignScan / CustomScan** are the FDW / custom-AM hooks; they expose a
  per-node callbacks struct so the same `ExecScan` shell still works.

---

## 7. Join nodes

### 7.1 NestLoop

[Via `knowledge/architecture/executor.md` §6;
`knowledge/files/.../nodeNestloop.c.md` if present, else from architecture doc]

A NestLoop does **not** re-init the inner per outer tuple. It:

1. Pulls next outer via `ExecProcNode(outerPlan)`.
2. Copies outer Var values into `PARAM_EXEC` slots referenced by the inner
   (`nestParams`).
3. Sets `innerPlan->chgParam` to the bitmap of changed param IDs.
4. Calls `ExecReScan(innerPlan)`.

`ExecReScan` is the cooperative reset: a node like Sort, which already has
its output materialised, can check `chgParam` against the params its subtree
actually depends on — if none changed, it rewinds its tape and skips the
rescan entirely [from-README `executor/README:19-26`].

### 7.2 HashJoin

[Via `knowledge/files/.../nodeHashjoin.c.md`, `knowledge/files/.../nodeHash.c.md`]

Hybrid hashjoin (Zeller & Gray 1990): if inner fits in memory, classical
one-pass hashjoin; otherwise partition both sides on hashbits into `n_batches`
(power of 2) and process batches one at a time.

**Serial state machine** (`nodeHashjoin.c:182-189`):
`HJ_BUILD_HASHTABLE → HJ_NEED_NEW_OUTER → HJ_SCAN_BUCKET → HJ_FILL_OUTER_TUPLE
| HJ_FILL_INNER_TUPLES | … → HJ_NEED_NEW_BATCH`.

Implemented as a single `pg_attribute_always_inline ExecHashJoinImpl` taking
`bool parallel`, so the compiler emits two specializations:
`ExecHashJoin` (parallel=false) at `:802` and `ExecParallelHashJoin`
(parallel=true) at `:818`, each with dead branches DCE'd. This is the cleanest
"specialize at compile time" trick in the executor
[via `knowledge/files/.../nodeHashjoin.c.md`; verified at
`source/.../nodeHashjoin.c:225,802,818`].

**Parallel state machine**: `PHJ_BUILD_ELECT → PHJ_BUILD_ALLOCATE →
PHJ_BUILD_HASH_INNER → PHJ_BUILD_HASH_OUTER → PHJ_BUILD_RUN → PHJ_BUILD_FREE`
coordinated by a `Barrier` (storage/ipc/barrier.c). Per-batch:
`PHJ_BATCH_ELECT → ALLOCATE → LOAD → PROBE → SCAN → FREE`. Batch 0 starts at
PROBE because BUILD_HASH_INNER filled it.

**Deadlock avoidance**: backends never wait on a barrier while holding output
they could be drained on; they use `BarrierArriveAndDetach` /
`BarrierArriveAndDetachExceptLast` to transition without waiting
[from-comment `nodeHashjoin.c:146-158`].

**Hash table** (`nodeHash.c`) — the build half — manages:

- `buckets.unshared[]/.shared[]` — bucket head pointers to `HashJoinTuple`
  chains (MinimalTuple + next + match flag).
- `chunks` — list of bump-allocated `HashMemoryChunk` (≥32KB) holding
  current-batch tuples. Lets us free all batch-0 tuples by walking this list.
- `innerBatchFile[]` / `outerBatchFile[]` — BufFile arrays of size `nbatch`.
- Optional `skewBucket[]` — MCV inner-side keys hashed separately for cache
  locality on skewed joins.
- `ExecChooseHashTableSize(...)` `:683` is the sizing function — picks
  `nbatch`/`nbuckets` so in-memory hashtable + BufFile arrays fit work_mem.

### 7.3 MergeJoin

[Via `knowledge/files/.../nodeMergejoin.c.md`]

Classic sort-merge: both inputs pre-sorted on the join keys, walked in
lockstep. State machine `mj_JoinState` cycles through INITIALIZE_OUTER,
INITIALIZE_INNER, JOINTUPLES, NEXTOUTER, TESTOUTER, NEXTINNER, SKIP_TEST,
SKIPOUTER_ADVANCE, SKIPINNER_ADVANCE, ENDOUTER, ENDINNER. Cartesian on equal
groups: mark inner position (`ExecMarkPos`), emit all inner rows with the
matching key, on next outer with same key restore (`ExecRestrPos`) and replay.

This is why the planner inserts a Material below the inner side if the inner
isn't naturally mark/restore-capable — checked via `ExecSupportsMarkRestore`
in `execAmi.c` [via `knowledge/files/.../nodeMergejoin.c.md`].

---

## 8. Aggregation, sort, materialization

### 8.1 nodeAgg — both algorithms in one node

[Via `knowledge/files/.../nodeAgg.c.md`]

Handles **sorted/plain Group Aggregation** (`AGG_PLAIN`, `AGG_SORTED`) and
**Hash Aggregation** (`AGG_HASHED`, `AGG_MIXED`), including GROUPING SETS /
CUBE / ROLLUP and DISTINCT/ORDER-BY-inside-aggregate.

- Sorted: `agg_retrieve_direct` `:2283` — on each PARTITION boundary, finalize,
  emit, start new group.
- Hashed: `agg_fill_hash_table` `:2629` builds the table (one per grouping
  set), then `agg_retrieve_hash_table` `:2837` walks it. AGG_MIXED combines
  one sorted set with hashed sets in a single Agg.

**Spilling** (`hashagg_spill_init` `:2986`): when `work_mem` is exceeded during
build, rows whose groups don't yet exist are partition-spilled into N tapes;
after in-memory groups are emitted, we recurse on tapes, possibly spilling
further. PG 13+ behavior; older PGs would OOM
[via `knowledge/files/.../nodeAgg.c.md`].

**aggsplit modes** for parallel/FDW partial agg:

- `AGGSPLIT_SIMPLE` — normal.
- `AGGSPLIT_INITIAL_SERIAL` — run transfn, skip finalfn, serialize.
- `AGGSPLIT_FINAL_DESERIAL` — deserialize input, use combinefn, run finalfn.

**Per-aggregate state sharing**: multiple Aggrefs sharing the same transition
function and arguments share a single `AggStatePerTrans`. This is why
`AVG(x), SUM(x)` only do the SUM transition once
[via `knowledge/files/.../nodeAgg.c.md`].

### 8.2 The shared TupleHashTable

[Via `knowledge/files/.../execGrouping.c.md`]

HashAgg, Hashjoin's in-memory side, SetOp(hash), Subplan hashed-IN, Memoize,
and Recursive Union (UNION dedup) **all share** the simplehash-based
`TupleHashTable` in `execGrouping.c`. `BuildTupleHashTable(..., additionalsize,
metacxt, tablecxt, tempcxt, use_variable_hash_iv)` `:184` is the constructor.

**The trick that makes HashAgg fast: `additionalsize`.** The hash table
allocates that many pad bytes immediately after each `TupleHashEntryData`,
so HashAgg's per-group transition values **live inline in the hash entry**.
One cache line, one allocation per group; the per-group state is recovered
via `((char*)entry) + MAXALIGN(sizeof(TupleHashEntryData))`
[via `knowledge/architecture/executor.md` §7b; verified at
`source/.../execGrouping.c:184,502`].

`use_variable_hash_iv` mixes the parallel worker number into the seed so
workers don't all hash identically — important for partitioned hashagg.

### 8.3 Sort

[Via `knowledge/files/.../nodeSort.c.md`]

Thin wrapper around `utils/sort/tuplesort.c`. Two physical modes:

- **Datum sort** for single-column results — `tuplesort_putdatum` /
  `tuplesort_getdatum`. Much faster for pass-by-value types.
- **Tuple sort** for multi-column.

**Bounded sort**: when an enclosing Limit communicates `tuples_needed` via
`ExecSetTupleBound`, Sort switches to a heap-of-k algorithm
(`tuplesort_set_bound`) that retains only the top-k rows — dramatic savings
for `LIMIT k` over a large input.

**Parallel sort**: works inside a worker as part of a partial plan
(`Gather Merge` above), or in shared-tape final-merge mode where each worker
hands its sorted run as a tape to a SharedTuplesort and one backend does the
merge.

### 8.4 IncrementalSort

[Via `knowledge/files/.../nodeIncrementalSort.c.md`]

When input is already sorted by a prefix of the requested keys, only sort
within prefix-equal groups. Two `Tuplesort` instances alternate (one
building, one draining). Falls back to "full sort" mode when prefix groups
get too large (`DEFAULT_MIN_GROUP_SIZE = 32`).

### 8.5 Material

[Via `knowledge/files/.../nodeMaterial.c.md`]

Buffers child output in a `Tuplestorestate` so the parent can rescan, mark/
restore, or read backwards without driving the subtree again. Planner inserts
it when (1) the subplan is expensive and parent will rescan, or (2) parent
needs mark/restore and subplan doesn't natively support it. ReScan
optimization: if no params changed below, `tuplestore_rescan` replays without
re-running outer.

---

## 9. ModifyTable — DML, with Prologue/Act/Epilogue

[Via `knowledge/files/.../nodeModifyTable.c.md`;
`knowledge/architecture/executor.md` §8a]

`nodeModifyTable.c` (~5500 lines) is the driver for **all DML**: INSERT,
UPDATE, DELETE, MERGE. The top loop `ExecModifyTable` `:4619`:

1. Pull one row from `outerPlanState(mtstate)`.
2. Read row-identity junk columns (CTID, tableoid for partitioned targets,
   wholerow for views with INSTEAD triggers, MERGE source markers).
3. For partitioned targets: `ExecFindPartition` (execPartition.c) routes to
   the leaf ResultRelInfo.
4. Dispatch: `ExecInsert` / `ExecUpdate` / `ExecDelete` / `ExecMerge`.
5. Optionally project RETURNING.

### 9.1 The Prologue / Act / Epilogue refactor

Since PG 15 (introduced with MERGE), each DML primitive factors into three
phases [verified-by-code via per-file doc: UPDATE `:2383,2461,2614`; DELETE
`:1739,1771,1798`]:

- **Prologue** — BEFORE ROW triggers, generated-column / RLS / FK pre-checks.
- **Act** — the single `table_tuple_insert/update/delete` call and its tuple-
  method-result handling (`TM_Ok | TM_Updated | TM_Deleted | TM_SelfModified`).
- **Epilogue** — index update (`ExecInsertIndexTuples` /
  `ExecUpdateIndexTuples`), AFTER ROW triggers, RETURNING projection queue.

This factoring exists so `ExecMerge` `:3394` can drive any of the three
actions per WHEN clause without re-implementing trigger + index logic. The
shared bottom layer is also what lets MERGE retry a WHEN MATCHED clause via
EvalPlanQual on `TM_Updated`/`TM_Deleted` without losing trigger semantics.

### 9.2 INSERT specifics

[Via `knowledge/files/.../nodeModifyTable.c.md`]

`ExecInsert` `:872` runs BEFORE ROW, BEFORE STATEMENT (`fireBSTriggers`
`:4448`), then for ON CONFLICT runs `ExecCheckIndexConstraints` first to find
a conflicting CTID before the heap insert. Heap insert uses
`HEAP_INSERT_SPECULATIVE` for ON CONFLICT. On conflict in any arbiter index,
`heap_abort_speculative` + `ExecOnConflictUpdate` `:3134`.

### 9.3 EvalPlanQual under READ COMMITTED

[Via `knowledge/architecture/executor.md` §7]

When UPDATE/DELETE/MERGE finds a row concurrently modified, READ COMMITTED
can't abort. Instead [from-README `executor/README:355-401`]:

1. Wait for the concurrent xact to commit.
2. Re-run the same query with a synthesised scan that returns only the
   modified tuple.
3. If the rerun yields a tuple, that row still passes quals; update *that* row.

Scans cooperate: `ExecInitSeqScan` checks `estate->es_epq_active` and installs
a separate `ExecSeqScanEPQ` variant when EPQ is active. `ExecScan` handles EPQ
diversion uniformly for all scan-family nodes.

### 9.4 Cross-partition UPDATE

`ExecCrossPartitionUpdate` `:2218`: when the new partition-key sends a row to
a different partition, the UPDATE becomes a DELETE on the old partition +
INSERT into the new. Trigger semantics: UPDATE row triggers fire on the old
partition; INSERT triggers fire on the new. FK side handled in
`ExecCrossPartitionUpdateForeignKey` `:2669`
[via `knowledge/files/.../nodeModifyTable.c.md`].

### 9.5 Index updates and constraint enforcement

[Via `knowledge/files/.../execIndexing.c.md`]

`ExecInsertIndexTuples(resultRelInfo, slot, estate, update, noDupErr,
&specConflict, arbiterIndexes, onlySummarizing)` `:311` inserts the row into
every index. `IndexUniqueCheck` is `UNIQUE_CHECK_YES` for normal unique,
`UNIQUE_CHECK_PARTIAL` for deferrable unique (returns conflict but doesn't
error), `UNIQUE_CHECK_NO` for non-unique.

`ExecCheckIndexConstraints` `:543` — dry-run for ON CONFLICT: probes arbiters
without inserting, reports conflicting CTID for `ExecOnConflictUpdate` to
fetch and lock.

The file-header essay on **speculative insertion** is the authoritative
narrative on the two-backend insert race [`execIndexing.c:3-115`].

### 9.6 Tuple routing and pruning

[Via `knowledge/files/.../execPartition.c.md`]

`execPartition.c` does two jobs:

- **Tuple routing** for INSERT/COPY/UPDATE into partitioned tables.
  `ExecSetupPartitionTupleRouting` `:221` sets up the root's
  PartitionDispatch only; subtrees are built lazily. `ExecFindPartition`
  `:268` walks down keys, calls `ExecInitPartitionInfo` `:564` for first-time
  partitions (opens, builds ResultRelInfo, TupleConversionMap, indexes,
  trigger info, RETURNING projection, ON CONFLICT helpers).
- **Runtime partition pruning** for Append/MergeAppend.
  `ExecCreatePartitionPruneState` compiles planner-produced `PartitionPruneInfo`
  into a runtime state. `ExecDoInitialPruning` `:1995` runs at ExecutorStart
  with external params only (prunes partitions away before they're even
  opened); `ExecFindMatchingSubPlans` `:2667` runs per ReScan when relevant
  `chgParam` fires (e.g. nested loop driving partition key from outer).

Pruning steps are interpreted by a tiny VM in partprune.c; execPartition just
drives it.

---

## 10. Parallel query

[Via `knowledge/files/.../execParallel.c.md`,
`knowledge/files/.../nodeGather.c.md`,
`knowledge/files/.../nodeGatherMerge.c.md`,
`knowledge/files/.../tqueue.c.md`]

### 10.1 Leader setup — `ExecInitParallelPlan` (`execParallel.c:653`)

1. Walk plan tree counting DSM space per parallel-aware node
   (`EstimateParallelExecutorInfoSpace` + per-node `ExecXxxEstimate`).
2. Create ParallelContext via `InitializeParallelDSM`.
3. Serialize plan via **`nodeToString`** into a shm_toc key, plus ParamListInfo,
   queryString, env, snapshot. (Workers `stringToNode` it back. This means
   everything in a Plan must be string-roundtrippable.)
4. Per-node `ExecXxxInitializeDSM` lets nodes lay out shared state (Hash sets
   up `ParallelHashJoinState`, etc.).
5. Create N `shm_mq` queues + leader-side TupleQueueReaders.
6. **Workers are NOT launched yet**. Launch happens lazily in
   `ExecParallelCreateReaders` `:944` from Gather/GatherMerge on first row.

`ExecParallelFinish` `:1221` waits for workers, accumulates BufferUsage and
WalUsage into the leader's pgBufferUsage/pgWalUsage globals, collects
Instrumentation arrays. `ExecParallelCleanup` `:1274` destroys the
ParallelContext + DSM segment.

### 10.2 Worker entry — `ParallelQueryMain` (`execParallel.c:1514`)

Looks up serialized plan + params from DSM, reconstructs a QueryDesc, restores
snapshots and the param list, runs
`ExecutorStart/Run/Finish/End` with a `DestReceiver` writing to the worker's
shm_mq. Per-node `ExecXxxInitializeWorker` lets nodes attach to leader-side
DSM.

### 10.3 tqueue.c — worker → leader tuple transport

[Via `knowledge/files/.../tqueue.c.md`]

`TQueueDestReceiver`'s `receiveSlot` **always** calls
`ExecFetchSlotMinimalTuple` then `shm_mq_send`. So what arrives on the leader
is by construction a `MinimalTuple` — no header, no system columns, no OID,
no `tts_tid` [verified-by-code `tqueue.c:3-12`, whole file]. The leader-side
`TupleQueueReader` wraps the bytes back into a MinimalTuple in the reader's
memory context.

### 10.4 Gather vs GatherMerge

[Via `knowledge/files/.../nodeGather.c.md`,
`knowledge/files/.../nodeGatherMerge.c.md`]

- **Gather** — interleaves worker outputs in arbitrary order. Round-robins
  over `funnel->reader[i]` with `nowait=true`; if no worker has a row
  immediately, it may run the plan locally (`need_to_scan_locally`); blocks
  on a WaitEventSet over all worker shm_mq fds + latch. GUC
  `parallel_leader_participation=off` disables the local-run.
- **GatherMerge** — preserves order. Each worker's partial subplan emits in
  sort order (usually ends in a Sort or ordered Index Scan). The leader
  k-way-merges using a `binaryheap` with per-worker prefetch buffers
  (`MAX_TUPLE_STORE=10`).

### 10.5 Async execution — the wrinkle in the otherwise pull-only model

[Via `knowledge/files/.../execAsync.c.md`, `knowledge/files/.../nodeAppend.c.md`]

An `Append` over multiple `ForeignScan` children can issue non-blocking
requests via `ExecAsyncRequest`, run an event loop with
`ExecAppendAsyncEventWait`, and collect results via `ExecAsyncResponse`.
Six-callback mini-protocol (`execAsync.c`):

- `ExecAsyncRequest` — leader asks a child for a row.
- `ExecAsyncRequestPending` — child says "not ready, here's my fd".
- `ExecAsyncRequestDone` — child says "here's the row" (or NULL EOS).
- `ExecAsyncConfigureWait` — child adds its fd to the leader's WaitEventSet.
- `ExecAsyncNotify` — leader tells child its fd is ready.
- `ExecAsyncResponse` — generic upcall routing completion to requestor.

Today only `Append` is an async consumer and only `ForeignScan` is an async
producer; `PlanState.async_capable` marks the latter.

---

## 11. SubPlan, SRF, Memoize, Window, Recursive Union

### 11.1 SubPlan (an Expr) vs SubqueryScan (a Plan node)

[Via `knowledge/files/.../nodeSubplan.c.md`]

`nodeSubplan.c` implements the **SubPlan expression node** — a subquery
embedded in an expression: scalar subquery, EXISTS, ANY/ALL, MULTIEXPR,
ARRAY, plus InitPlan subqueries. Not to be confused with `nodeSubqueryscan.c`
which is for FROM-clause subqueries.

- **Hashed mode** (when `useHashTable`): `buildSubPlanHash` `:474` drains the
  subplan once into a TupleHashTable, then `ExecHashSubPlan` `:98` does O(1)
  probes.
- **Scanned mode**: `ExecScanSubPlan` `:201` re-runs the subplan per probe.
- **InitPlan**: `ExecSetParamPlan` `:1118` runs once per query (or per outer
  Param change), stashing output into PARAM_EXEC slots in the EState. The
  subplan's PlanState is allocated as a child of the **EState**, not the
  parent PlanState — this is what lets one InitPlan serve many sibling
  expressions.

### 11.2 SRF — two clients, one execSRF.c

[Via `knowledge/files/.../execSRF.c.md`]

`nodeFunctionscan` (FROM-clause) and `nodeProjectSet` (legacy SRF-in-TLIST)
both call set-returning functions via `ReturnSetInfo`. Two return modes:

- **ValuePerCall** — re-entered per row; state in `fcinfo->flinfo->fn_extra`,
  signals via `rsi->isDone = ExprMultipleResult | ExprEndResult`.
- **Materialize** — fully-populated tuplestore in `rsi->setResult`.

`ExecMakeTableFunctionResult` `:102` is used by FunctionScan — drains a SRF
into a Tuplestore (handles `WITH ORDINALITY`, `ROWS FROM (...)`).
`ExecMakeFunctionResultSet` `:499` is used by ProjectSet — pulls one row at a
time.

`nodeProjectSet`'s LCM semantics: multiple SRFs in TLIST produce
`LCM(cardinalities)` rows where shorter SRFs cycle (deprecated PG-pre-10
behavior).

### 11.3 Memoize — LRU cache over a parameterized inner scan

[Via `knowledge/files/.../nodeMemoize.c.md`]

PG 14+. Hash table keyed by parameter vector (uses the
`ExecBuildParamSetEqual` ExprState from execExpr.c). Each entry stores a list
of MinimalTuples for that param combo + complete flag. **LRU eviction**:
doubly-linked list; over `hash_mem` → evict head. No spill to disk.

**Incomplete entries**: if the parent stops pulling early (semi-join finds
match), the entry is marked incomplete. Next same-key probe either uses it
(if planner marked join as unique → first row was enough) or discards it and
rescans the child.

### 11.4 WindowAgg

[Via `knowledge/files/.../nodeWindowAgg.c.md`]

Input must arrive sorted by partition keys + order keys (planner inserts
the Sort). One WindowAgg evaluates all window functions sharing identical OVER
specs; multiple distinct OVERs become stacked WindowAggs separated by Sorts.

Partitions are buffered into a per-partition `Tuplestorestate`; never more
than one partition at a time. Frame edges (`ROWS|RANGE|GROUPS BETWEEN…`) are
tracked incrementally — when the frame's lower bound advances past a row, we
**retract** it via the aggregate's `inverse_transition function`. Without an
inverse, the agg recomputes from scratch each output row (expensive). The
`EXCLUDE` clause is implemented the same way.

### 11.5 Recursive Union

[Via `knowledge/files/.../nodeRecursiveunion.c.md`]

Semi-naive evaluation:
1. Run non-recursive term, push to `intermediate_table` (and into a hash
   table for UNION DISTINCT dedup).
2. Loop: swap `intermediate` ↔ `working`; rescan recursive term (its
   WorkTableScan reads from `working`); drain into `intermediate`; stop when
   empty.

No `max_recursion` GUC — infinite recursion eventually runs out of disk.

---

## 12. SPI and SQL-language functions

### 12.1 SPI

[See `knowledge/idioms/spi.md` for the full surface.]

SPI lives in `executor/spi.c`. It's the procedural-language gateway into the
executor: PL/pgSQL, PL/Python, PL/Perl, and C extensions use SPI to plan,
prepare, and execute SQL strings without going through libpq. SPI manages its
own memory context per `SPI_connect()`, builds a QueryDesc, runs Executor*,
and exposes results as `SPI_tuptable` (a Tuplestorestate-backed view).

### 12.2 functions.c — `language sql` functions

[Via `knowledge/files/.../functions.c.md`]

`fmgr_sql` `:1577` is the fmgr handler for SQL-language functions:

1. First call: `init_sql_fcache` `:537` parses, analyzes, plans every body
   query (cached via plancache).
2. `check_sql_fn_retval` `:2117` validates the last query matches the
   declared return type.
3. `init_execution_state` `:654` builds the `execution_state` list.
4. `postquel_start` `:1277` / `postquel_getnext` `:1401` drive each query.

**Lazy vs eager**: `RETURNS SETOF` runs the final query row-by-row through
fmgr's ValuePerCall mechanism; otherwise the final query is materialized into
a tuplestore and returned in Materialize mode. Controlled by `lazyEvalOK`.

**Inlining bypass**: a simple-enough `LANGUAGE sql` function (single SELECT,
immutable/stable, no side effects) is **inlined by the planner** in
`optimizer/util/clauses.c:inline_function` and this code path never runs —
which is why such functions appear in EXPLAIN as their inlined expression.

### 12.3 execReplication.c — logical replication apply

[Via `knowledge/files/.../execReplication.c.md`]

Helpers for the logical replication apply worker. **Bypasses the SQL
executor**: given the replicated old/new tuple, locate the target row by
replica-identity index (`RelationFindReplTupleByIndex` `:182`) or fallback
sequential scan for `REPLICA IDENTITY FULL`
(`RelationFindReplTupleSeq` `:370`), then call `ExecSimpleRelationInsert/
Update/Delete`. Only AFTER row triggers fire (BEFORE are skipped by design).

### 12.4 execCurrent.c — `WHERE CURRENT OF cursor`

[Via `knowledge/files/.../execCurrent.c.md`]

Walks the named Portal's executor state to find the scan that's currently
scanning the target relation OID, reads its `tts_tid`. Limited to cursors
whose plan top is a single scan or an Append of inheritance scans — not
joins/aggregates/subqueries.

### 12.5 execJunk.c — junk columns

[Via `knowledge/files/.../execJunk.c.md`]

Junk attributes are TargetEntry items with `resjunk=true` carrying executor-
internal info: CTID for UPDATE/DELETE, tableoid for partitioned/inheritance
targets, wholerow for view INSTEAD triggers, rowmark TIDs for FOR UPDATE,
order-by columns not in SELECT, MERGE source markers. A `JunkFilter` strips
them before the client sees the row.

The pattern is universal: **any time something needs to ride through the plan
that isn't part of the user's visible row, it goes in as a resjunk TLE**.

### 12.6 tstoreReceiver.c — Tuplestore DestReceiver

[Via `knowledge/files/.../tstoreReceiver.c.md`]

A `DestReceiver` that stores rows into a `Tuplestorestate`. Used by WITH HOLD
cursors, SPI cursors, Materialize-mode SRF results, `RETURN QUERY` in
PL/pgSQL. Has optional `force-detoast` for tuples whose toasted columns might
outlive the source table (WITH HOLD over temp tables, or across xacts).

### 12.7 instrument.c — EXPLAIN ANALYZE accounting

[Via `knowledge/files/.../instrument.c.md`]

`InstrAlloc/Init/StartNode/StopNode/EndLoop` are the API. Each `StartNode`
snapshots the process-wide `pgBufferUsage`/`pgWalUsage` counters; each
`StopNode` diffs into the per-node per-loop counters. `EndLoop` folds per-loop
into running totals (`ntuples`, `nloops`, `total_time`, `min_t/max_t`). The
snapshot-diff pattern is what makes EXPLAIN (BUFFERS) per-node attribution
work.

Parallel: `InstrAggNode(target, add)` merges a worker's Instrumentation into
the leader's after `ExecParallelFinish` retrieves per-worker arrays.

---

## 13. Common pitfalls

These come up when writing or reviewing executor patches. Each maps to a
specific invariant that is easy to break.

### 13.1 Direct `resvalue`/`resnull` writes vs the ExprState calling convention

The ExprState calling convention is "the consumer step's
`FunctionCallInfo->args[i]` already points where the producer step writes".
A new opcode that allocates a fresh return slot **breaks this**: the consumer
will read the old, stale location. Always wire `op->resvalue`/`op->resnull`
to the destination the compiler picked, never to a private buffer
[from-comment `execExpr.c:3-15`].

Related: JIT-shared helpers (`ExecEvalArrayExpr` etc.) must return without
performing dispatch — the caller is responsible. Don't add a "loop the next
N steps from inside" helper [from-README via
`knowledge/files/.../execExprInterp.c.md`].

### 13.2 MinimalTuple loss across tqueue: ctid/tableoid become junk-only

Anything sent by a worker through `tqueue.c` arrives as a `MinimalTuple` —
**no header, no system columns, no `tts_tid`, no `tts_tableOid`**. If a
consumer above a Gather/GatherMerge needs `ctid` or `tableoid` (ModifyTable
with FOR UPDATE under a parallel SELECT, sort-with-tie-break-by-ctid), those
must be present as **junk columns in the row body**; the planner is
responsible for adding the resjunk TLEs [via
`knowledge/architecture/executor.md` §7a; `tqueue.c:3-12`].

### 13.3 Projection vs raw tuples — when a scan slot leaks past projection

A scan node's `ss_ScanTupleSlot` is a **buffer-pinned heap slot**;
`ps_ResultTupleSlot` is virtual (post-projection). Returning the scan slot
directly to a parent (which `ExecScan` does when `ps_ProjInfo == NULL` and
no qual or qual passes) means the **buffer pin survives until the parent
next clears the slot**. If that parent's consumer holds the slot across
something that releases the buffer mapping, you can lose the row mid-read.
The cure is `ExecMaterializeSlot` — forces the slot to own its data so the
pin can be dropped [via `knowledge/files/.../execTuples.c.md`].

### 13.4 Slot ownership across ExprContext reset

A Virtual slot's `tts_values[]` may point into per-tuple-context palloc'd
memory. If your node forgets to `ResetExprContext` before emitting a row,
old per-tuple allocations pile up. If your node resets the ExprContext
**before** clearing a slot that points into it, the slot is now dangling
[from-README `executor/README:282-287`; via
`knowledge/files/.../execTuples.c.md`].

Rule of thumb: emit row, return to parent, **next** call resets the context.
NestLoop's `ExecNestLoop` resets at top of call, after the previous row was
consumed.

### 13.5 ExecEndNode does NOT free memory — it releases handles

People often try to `pfree` palloc'd internal state in `ExecEndFoo`. Don't.
The per-query context is about to be destroyed by `FreeExecutorState`;
your pfree is wasted work, and worse, it tempts you into double-free bugs
across error paths. What `ExecEndFoo` **must** do: close relations
(`ExecCloseScanRelation`), end heap scans, drop buffer pins, end FDW
state, close tuplesorts/tuplestores (they own external resources), free
parallel coordination state [from-README `executor/README:324-327`].

### 13.6 ExecReScan must respect chgParam

A naive Sort `ReScan` that always re-runs the outer wastes the entire
materialized result every nestloop iteration. The cooperative protocol is:
parent sets `chgParam` to the param IDs it changed; the node checks its
recorded `extParam`/`allParam` to decide if its cached results are still
valid. Sort just rewinds when no relevant params changed
[from-README `executor/README:19-26`].

### 13.7 EvalPlanQual is per-scan, not per-query

`estate->es_epq_active` flips during EPQ replay; scan nodes must check it at
init time (e.g. `ExecInitSeqScan` installs the `ExecSeqScanEPQ` variant
when EPQ is in play) **and** at run time (ExecScan diverts to
`EvalPlanQualNext` when active). A scan node that bypasses ExecScan (like
ForeignScan with its own access method) must reimplement EPQ diversion
explicitly via `RefetchForeignRow`/`RecheckForeignScan`
[via `knowledge/files/.../nodeLockRows.c.md`].

### 13.8 ExecGetRangeTableRelation is the single open point

Don't `table_open` directly in a new node type — go through
`ExecGetRangeTableRelation` or `ExecOpenScanRelation`. The planner's recorded
lockmode must match what gets taken, and the per-EState relation cache must
not be bypassed (otherwise you double-lock, or lock at the wrong strength)
[via `knowledge/files/.../execUtils.c.md`].

### 13.9 `BuildTupleHashTable`'s `additionalsize` requires fixed-width state

Inline transition state via `additionalsize` only works for fixed-width
transition values. By-ref transition values (numeric, text-aggregating) are
allocated separately into the per-group memory and the inline area holds the
pointer. If you write a new node that wants HashAgg-style inline state, you
must mirror this discipline [via `knowledge/files/.../execGrouping.c.md`,
`knowledge/files/.../nodeAgg.c.md`].

### 13.10 Plan serialization for parallel: nodeToString round-trip

`ExecInitParallelPlan` serializes the entire plan tree by `nodeToString`.
If you add a new Plan-node field that doesn't have `out`/`read` support
(`outfuncs.c`/`readfuncs.c`), parallel workers will deserialize a partial
tree and crash. Symptom: parallel-only crashes that vanish with
`max_parallel_workers_per_gather=0`
[via `knowledge/files/.../execParallel.c.md`].

---

## 14. Cross-references

- `knowledge/architecture/executor.md` — Volcano model, four trees, the
  Start/Run/End lifecycle at high level, the SeqScan-on-NestLoop worked
  example. Read this first if new to the executor.
- `knowledge/architecture/query-lifecycle.md` — where the executor sits
  between parser/planner/return-to-client.
- `knowledge/architecture/planner.md` — what hands a `PlannedStmt` to the
  executor and what guarantees the planner provides (lockmodes, sort orders,
  partition prune info, parallel-safety annotations).
- `knowledge/architecture/bgworker-and-parallel.md` — the ParallelContext
  + DSM substrate that `execParallel.c` builds on.
- `knowledge/architecture/jit.md` — what JIT replaces inside the ExprState
  interpreter (the opcode-body helpers from §3.7).
- `knowledge/idioms/node-types-and-lists.md` — the NodeTag / `List *` / 
  `lfirst()` idioms used everywhere in PlanState init.
- `knowledge/idioms/memory-contexts.md` — palloc / context lifetime rules
  that EState and ExprContext implement.
- `knowledge/idioms/spi.md` — the SPI surface for procedural languages.
- `knowledge/idioms/fmgr.md` — `fcinfo`, strict-function handling — relevant
  to the FUNCEXPR opcodes in §3.
- `knowledge/subsystems/access-heap.md` — `table_tuple_insert/update/delete`
  contract, TM_Result codes, that ModifyTable's Act phase calls.
- `knowledge/subsystems/access-transam.md` — snapshots, xact lifecycle,
  combo-CID — relevant to EvalPlanQual.
- `knowledge/subsystems/storage-ipc.md` — `shm_mq` and Barrier primitives
  that `tqueue.c` and `nodeHashjoin.c` build on.
- Per-file docs: `knowledge/files/src/backend/executor/*.md`.

---

## 15. Suggested gaps for future deep-reads

- `execMain.c` itself has no per-file doc yet; the architecture doc covers
  the lifecycle but `InitPlan` (`:847`) and `ExecEndPlan` (`:1565`) are
  not deep-read. Worth its own per-file doc with the InitPlan recursion +
  initPlan/subPlan list handling.
- `execProcnode.c` similarly has no per-file doc; the per-node dispatch
  tables (`ExecInitNode`, `ExecProcNodeFirst`, `MultiExecProcNode`,
  `ExecEndNode`, `ExecShutdownNode`) deserve documentation as the single
  inventory of "what node types exist and which file implements them".
- `spi.c` is referenced via the SPI idiom doc but has no per-file doc.
- `nodeNestloop.c` has no per-file doc; architecture doc §6 covers it but a
  per-file write-up would lock down EPQ interaction + `nestParams` + the
  `ResetExprContext` call site `:92`.
- The `JitProvider` (`jit/jit.c`) interface that `ExecReadyExpr` dispatches
  to is documented in `architecture/jit.md` but a subsystem-level doc on
  how JIT splices into ExprState would help close the executor↔JIT loop.
