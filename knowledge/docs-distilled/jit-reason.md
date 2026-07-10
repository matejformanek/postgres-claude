---
source_url: https://www.postgresql.org/docs/current/jit-reason.html
chapter: "32.1 What Is JIT compilation?"
fetched_at: 2026-07-09
anchor_sha: d92e98340fcb
---

# What JIT compiles — accelerated operations, inlining, optimization — §32.1

The conceptual root of the JIT chapter. JIT (`src/backend/jit/`) turns the
*interpreted* execution of two specific hot paths into native code generated
at run time. It is **not** a whole-query compiler: only expression evaluation
and tuple deforming are accelerated; everything else (node dispatch, tuple
flow, buffer access) stays interpreted. Available only when PostgreSQL is
built `--with-llvm`.

## Non-obvious claims

- **JIT accelerates exactly two things today — expression evaluation and
  tuple deforming.** "Currently PostgreSQL's JIT implementation has support
  for accelerating expression evaluation and tuple deforming. Several other
  operations could be accelerated in the future." [from-docs §32.1]
- **"Expression evaluation" is broad**: `WHERE` clauses, target lists,
  aggregates, and projections — anything normally walked by the generic
  expression interpreter. The win is generating code *specific to each
  expression* (e.g. `WHERE a.col = 3`) instead of the general-purpose
  interpreter that can evaluate arbitrary SQL expressions. [from-docs §32.1]
  The interpreter this replaces is `ExecInterpExpr` in
  [[knowledge/files/src/backend/executor/execExprInterp.c.md]].
- **"Tuple deforming" = turning an on-disk tuple into its in-memory Datum
  array.** JIT builds a function specific to *this table's layout and the
  number of columns actually extracted*, so the generic column-walking loop
  (with its null-bitmap checks and alignment math) collapses into
  straight-line code. [from-docs §32.1] The interpreted version lives in
  `slot_deform_heap_tuple` /
  [[knowledge/files/src/backend/executor/execTuples.c.md]].
- **The gated compile flags mirror the two operations plus effort tiers**:
  `PGJIT_EXPR` (compile expressions) and `PGJIT_DEFORM` (compile deforming)
  are separate bits from `PGJIT_INLINE` (inline function bodies) and
  `PGJIT_OPT3` (run LLVM `-O3` passes). [verified-by-code
  `source/src/include/jit/jit.h:19-24` — `PGJIT_NONE/PERFORM/OPT3/INLINE/
  EXPR/DEFORM`]
- **Inlining is the answer to PG's extensibility tax.** Because operators and
  types dispatch through `fmgr` function pointers, a single `a + b` is several
  indirect calls. "JIT compilation can inline the bodies of small functions
  into the expressions using them," letting LLVM optimize the call overhead
  away. Only `C`- and `internal`-language functions can be inlined (their
  bodies ship as LLVM bitcode — see §32.4,
  [[knowledge/docs-distilled/jit-extensibility.md]]). [from-docs §32.1]
- **Optimization is split into cheap-always vs expensive-only-if-long.**
  "Some of the optimizations are cheap enough to be performed whenever JIT is
  used, while others are only beneficial for longer-running queries." This is
  the conceptual justification for the *separate* cost thresholds in §32.2 —
  cheap codegen at one threshold, inlining and full `-O3` at higher ones.
  [from-docs §32.1]
- **The docs do not quantify the compile-time cost** on this page — the "JIT
  can hurt short queries" story is implicit in §32.2's cost gates, not stated
  here. [inferred]

## Links into corpus

- What JIT replaces: [[knowledge/files/src/backend/executor/execExprInterp.c.md]]
  (interpreted expression eval) + the compiled-expr build in
  [[knowledge/files/src/backend/executor/execExpr.c.md]] +
  [[knowledge/files/src/backend/executor/execTuples.c.md]] (deforming).
- The cost-gate decision: [[knowledge/docs-distilled/jit-decision.md]] (§32.2).
- GUCs + EXPLAIN reporting: [[knowledge/docs-distilled/jit-configuration.md]] (§32.3).
- Pluggable provider + bitcode inlining:
  [[knowledge/docs-distilled/jit-extensibility.md]] (§32.4).
- Executor context: [[knowledge/subsystems/executor.md]].

## Caveats / verification

- Prose claims `[from-docs §32.1]`. The `PGJIT_*` flag decomposition
  (EXPR/DEFORM/INLINE/OPT3) is `[verified-by-code]` at
  `source/src/include/jit/jit.h:19-24`, anchor `d92e98340fcb`.
- `jit.html` (the §32 chapter root) is ToC-only prose ("This chapter explains
  what just-in-time compilation is, and how it can be configured") — not
  distilled separately; same skip-class as `indextypes`/`charset`.
