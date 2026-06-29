---
path: src/include/jit/jit.h
anchor_sha: e18b0cb7344
loc: 106
depth: read
---

# src/include/jit/jit.h

## Purpose

Provider-independent JIT infrastructure. Defines the `PGJIT_*` operation-flag
bitset, the per-query `JitContext` base (extended by each provider — currently
only `LLVMJitContext`), the `JitInstrumentation` time/count counters surfaced
in EXPLAIN ANALYZE and `pg_stat_statements`, the `SharedJitInstrumentation`
DSM struct that parallel workers aggregate into, the `JitProviderCallbacks`
function-pointer table that providers fill in via `_PG_jit_provider_init`,
and the `jit_*` GUCs (`jit_enabled`, `jit_above_cost`, …). This is the header
the rest of the backend includes to *use* JIT; it knows nothing about LLVM.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `PGJIT_NONE / PGJIT_PERFORM / PGJIT_OPT3 / PGJIT_INLINE / PGJIT_EXPR / PGJIT_DEFORM` | `:19-24` | Bit flags chosen by the planner per query |
| `struct JitInstrumentation` | `:27-46` | `created_functions`, plus five `instr_time` counters (generation, deform, inlining, optimization, emission) |
| `struct SharedJitInstrumentation` | `:51-55` | DSM-layout `num_workers + FLEXIBLE_ARRAY_MEMBER` of per-worker `JitInstrumentation` |
| `struct JitContext` | `:57-63` | Provider-extensible base: `flags`, `instr` |
| `struct JitProviderCallbacks` | `:74-79` | `reset_after_error`, `release_context`, `compile_expr` slots |
| `_PG_jit_provider_init(JitProviderCallbacks *cb)` | `:67` | `PGDLLEXPORT` entry point each provider library exposes |
| GUC externs `jit_enabled`, `jit_provider`, `jit_debugging_support`, `jit_dump_bitcode`, `jit_expressions`, `jit_profiling_support`, `jit_tuple_deforming`, `jit_above_cost`, `jit_inline_above_cost`, `jit_optimize_above_cost` | `:83-91` | GUCs the planner / provider consult |
| `jit_reset_after_error`, `jit_release_context`, `jit_compile_expr`, `InstrJitAgg` | `:95-103` | Public C entry points |

## Internal landmarks

- **`PGJIT_*` flag bits.** The planner ORs these together based on cost
  comparisons against `jit_above_cost`, `jit_inline_above_cost`,
  `jit_optimize_above_cost`. The provider receives the OR-bitmask in
  `JitContext.flags` and decides what to actually do. A flag of
  `PGJIT_PERFORM | PGJIT_EXPR | PGJIT_DEFORM` is the typical "compile, no
  inline, no -O3" combo.
- **`JitInstrumentation.deform_counter` is a subset of `generation_counter`**
  (`:35`) — `[from-comment]`: deform-time is already inside generation-time,
  so EXPLAIN must not sum them.
- **`SharedJitInstrumentation` is FAM-tailed** (`:54`) — providers /
  ExecParallelFinish copy worker-local `JitInstrumentation` into
  `jit_instr[worker]`, then leader rolls them up via `InstrJitAgg`.
- **`JitProviderCallbacks` is intentionally minimal** (3 slots). New provider
  duties (e.g. a hypothetical compile-statement callback) require adding a
  slot here, bumping a version check, and updating both the LLVM provider and
  any external providers an extension ships.
- **GUC `jit_provider` is a string** (`:84`) — the runtime dlopens
  `$libdir/$jit_provider.so` and calls `_PG_jit_provider_init`. Custom JIT
  providers are an extension mechanism, not a fork point.

## Invariants & gotchas

- **`JitContext` is a *base struct***, not opaque. Providers extend it by
  embedding `JitContext base;` as the first field (see `LLVMJitContext.base`
  at `llvmjit.h:45`). Downcasting via `(LLVMJitContext *) ctx` is the
  contract. Any future header that hides `JitContext` fields breaks every
  provider.
- **`_PG_jit_provider_init` is PGDLLEXPORT, not PGDLLIMPORT**, because the
  symbol is looked up via dlsym in the *provider's* .so, not in the backend.
  `[verified-by-code]`
- **GUCs are all `PGDLLIMPORT`** (`:83-91`) so external providers compiled
  against PG headers can read them on Windows.
- **No JIT context lifecycle beyond `release_context`.** The cleanup hook
  must be idempotent — `jit_release_context` may be invoked from
  `ResourceOwnerRelease` during error unwind and during normal end-of-query.
  Providers that allocate process-global resources must check this.
- **`InstrJitAgg` adds, never resets.** EXPLAIN's pretty-printer relies on
  monotonic counters; resetting in a per-query path would suppress the
  parallel-worker aggregate.

## Cross-refs

- `knowledge/files/src/include/jit/llvmjit.h.md` — the LLVM provider that
  consumes this interface.
- `source/src/backend/jit/jit.c` — implementation of the provider-agnostic
  side (GUC plumbing, dlopen-the-provider).
- `source/src/backend/jit/llvm/llvmjit.c` — `_PG_jit_provider_init` lives
  here for the LLVM provider.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/jit-provider-and-context.md](../../../../idioms/jit-provider-and-context.md)
