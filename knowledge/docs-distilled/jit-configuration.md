---
source_url: https://www.postgresql.org/docs/current/jit-configuration.html
chapter: "32.3 Configuration"
fetched_at: 2026-07-09
anchor_sha: d92e98340fcb
---

# JIT configuration — GUCs, defaults, EXPLAIN reporting — §32.3

The §32.3 page itself only *names* the user GUCs and points at
runtime-config-developer for the debug knobs; the concrete defaults are
verified from source here so the corpus has one authoritative table. Two GUC
tiers: the user-facing cost/enable/provider set, and the developer/debug set
(`runtime-config-developer` §20.17).

## Non-obvious claims

- **The five user-facing JIT GUCs** are `jit` (master on/off), `jit_above_cost`,
  `jit_inline_above_cost`, `jit_optimize_above_cost`, and `jit_provider`.
  §32.3 lists them by name only and defers values elsewhere. [from-docs §32.3]
- **Verified defaults** (source, anchor `d92e98340fcb`):
  - `jit_enabled` C var = `false`; shipped `jit` GUC boot value = `on`.
    [verified-by-code `source/src/backend/jit/jit.c:33`]
  - `jit_above_cost = 100000` [`jit.c:40`]
  - `jit_inline_above_cost = 500000` [`jit.c:41`]
  - `jit_optimize_above_cost = 500000` [`jit.c:42`]
  - `jit_provider = "llvmjit"` (the default shared library loaded; the C var
    initializes to `NULL` and is filled by the GUC's boot default)
    [verified-by-code `source/src/backend/jit/jit.c:34` for the var; default
    string per §32.4 docs]
- **`jit_provider` is `PGC_POSTMASTER`** — provider choice is fixed at server
  start, unlike the cost thresholds which are `PGC_USERSET` and can be changed
  per session/transaction. [from-docs §32.3 / runtime-config-client] This is
  why swapping providers "without recompiling" still needs a restart.
- **The developer/debug GUCs live in §20.17, not here.** §32.3 says only: "For
  development and debugging purposes a few additional configuration parameters
  exist, as described in Section 20.17." Those include `jit_debugging_support`
  (register generated functions with a debugger), `jit_profiling_support`
  (emit perf data), `jit_dump_bitcode` (write `.bc` to the data dir),
  `jit_expressions`, and `jit_tuple_deforming` (toggle each accelerated
  operation independently for A/B testing). [from-docs §32.3 →
  runtime-config-developer §20.17]
- **`jit_expressions` / `jit_tuple_deforming` map 1:1 to the `PGJIT_EXPR` /
  `PGJIT_DEFORM` flag bits** — turning one off clears the corresponding bit so
  you can measure each half of JIT's contribution separately.
  [verified-by-code `source/src/include/jit/jit.h:23-24` for the bits;
  GUC↔bit wiring in `jit.c`]
- **`EXPLAIN (ANALYZE)` surfaces JIT as a `JIT` block**: a `Functions:` count
  (how many functions were generated), an `Options:` line (`Inlining`,
  `Optimization`, `Expressions`, `Deforming` each true/false), and a `Timing:`
  breakdown (`Generation`, `Inlining`, `Optimization`, `Emission`, `Total`).
  A high `Total` timing relative to execution time is the direct diagnostic
  for "JIT overhead exceeded its benefit." [from-docs §32.3; the
  `Inlining false, Optimization false` shape is shown in the §32.2 example]

## Links into corpus

- The cost gates that these thresholds feed:
  [[knowledge/docs-distilled/jit-decision.md]] (§32.2).
- What the flags/GUCs toggle: [[knowledge/docs-distilled/jit-reason.md]] (§32.1).
- Provider selection detail: [[knowledge/docs-distilled/jit-extensibility.md]] (§32.4).
- GUC landing pages: [[knowledge/docs-distilled/runtime-config-query.md]]
  (cost thresholds) — the developer knobs pair with the §20.17 debug family.

## Caveats / verification

- Default values are `[verified-by-code]` at
  `source/src/backend/jit/jit.c:33-34,40-42` and
  `source/src/include/jit/jit.h:23-24`, anchor `d92e98340fcb`. The `jit`
  GUC boot value (`on`), `jit_provider` string default (`"llvmjit"`), the
  `PGC_*` contexts, and the developer-GUC list are `[from-docs]` /
  runtime-config-developer §20.17 — not re-fetched here (that page is already
  distilled). The `EXPLAIN` `Timing`/`Options` field names are `[from-docs
  §32.3]`.
