---
source_url: https://www.postgresql.org/docs/current/jit-decision.html
chapter: "32.2 When to JIT?"
fetched_at: 2026-07-09
anchor_sha: d92e98340fcb
---

# When JIT fires — the plan-time cost-gate ladder — §32.2

JIT is decided **at plan time from the query's total estimated cost**, never
from runtime measurement. Three ascending cost thresholds form a ladder:
compile at all → also inline → also run expensive optimization. Because the
decision is frozen into the plan, prepared-statement generic plans bake in the
GUC values *as of PREPARE time*, not execution time.

## Non-obvious claims

- **The gate compares the query's total estimated cost against
  `jit_above_cost`.** "To determine whether JIT compilation should be used,
  the total estimated cost of a query … is used." It is a *whole-query*
  decision keyed on the top plan node's total cost, **not** a per-expression
  or per-node one — one cost number gates JIT for the entire query.
  [from-docs §32.2]
- **Three separate thresholds, each adding more work, in ascending order**:
  - `jit_above_cost` — above this, expressions/deforming are JIT-compiled.
  - `jit_inline_above_cost` — above this, *additionally* inline the bodies of
    small functions/operators (extra compile time).
  - `jit_optimize_above_cost` — above this, *additionally* apply expensive
    LLVM optimization passes.
  Each higher tier costs more compile time and only pays off on
  longer-running queries — hence the higher bar. [from-docs §32.2]
- **Defaults** (from source; the docs page names the GUCs but defers exact
  values to the runtime-config reference):
  - `jit_above_cost = 100000`
  - `jit_inline_above_cost = 500000`
  - `jit_optimize_above_cost = 500000`
  [verified-by-code `source/src/backend/jit/jit.c:40-42`]. So a query must be
  ~5× more expensive to earn inlining/optimization than to earn bare codegen.
- **`-1` at any threshold disables that tier.** Setting a threshold to `-1`
  turns off JIT / inlining / optimization respectively regardless of cost.
  (The master `jit` GUC = `off` disables everything up front.) [from-docs,
  runtime-config-query] The C variable `jit_enabled` defaults `false`
  [verified-by-code `source/src/backend/jit/jit.c:33`] — but the shipped
  `jit` GUC boot value is `on`, so a `--with-llvm` build JITs by default once
  a plan clears 100000.
- **The decision is plan-time, so prepared statements freeze it.** "These
  cost-based decisions will be made at plan time, not execution time. … when
  prepared statements are in use, and a generic plan is used …, the values of
  the configuration parameters in effect at prepare time control the
  decisions, not the settings at execution time." Changing `jit_above_cost`
  after `PREPARE` has no effect on an already-cached generic plan.
  [from-docs §32.2] This is the JIT-specific instance of the generic-vs-custom
  plan choice in [[knowledge/docs-distilled/xfunc-optimization.md]] /
  plancache.
- **Worked example from the docs**: a query estimated at cost `16.27` gets no
  JIT under defaults (16.27 < 100000); after `SET jit_above_cost = 10`, the
  same query JITs and `EXPLAIN` shows `Functions: 3` with
  `Inlining false, Optimization false` — because 16.27 still sits below the
  inline/optimize thresholds. Demonstrates the ladder acting independently per
  tier. [from-docs §32.2]
- **Cost, not row count or actual time, is the only signal** — a
  mis-estimated cheap-looking plan that runs long will *not* JIT, and an
  over-estimated plan that returns instantly *will* pay JIT compile overhead.
  This is the core failure mode behind "JIT made my query slower." [inferred
  from the cost-gate mechanism]

## Links into corpus

- What gets compiled once the gate opens:
  [[knowledge/docs-distilled/jit-reason.md]] (§32.1).
- GUC reference + EXPLAIN JIT reporting:
  [[knowledge/docs-distilled/jit-configuration.md]] (§32.3) and the GUC
  landing page [[knowledge/docs-distilled/runtime-config-query.md]].
- Plan-time vs exec-time / generic-plan freezing:
  [[knowledge/docs-distilled/planner-optimizer.md]] +
  [[knowledge/subsystems/optimizer.md]].

## Caveats / verification

- Prose + example claims `[from-docs §32.2]`. The three default threshold
  values and `jit_enabled=false` are `[verified-by-code]` at
  `source/src/backend/jit/jit.c:33,40-42`, anchor `d92e98340fcb`. The `jit`
  GUC boot default (`on`) and `-1`-disables semantics come from the
  runtime-config-query GUC reference, already distilled.
