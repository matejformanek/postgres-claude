---
path: src/backend/jit/jit.c
anchor_sha: e18b0cb7344
loc: 191
depth: deep
---

# jit.c

- **Source path:** `source/src/backend/jit/jit.c`
- **Lines:** 191
- **Last verified commit:** `e18b0cb7344`
- **Companion files:** `src/include/jit/jit.h`, `src/backend/jit/README`, `src/backend/jit/llvm/llvmjit.c` (the provider this shim loads).

## Purpose

Provider-independent JIT dispatcher for the backend. The whole file does three jobs: declares the `jit_*` GUCs (default-off `jit_enabled`, the various cost thresholds, the dump/debug toggles); lazily `dlopen`s a JIT provider shared library on first need; and forwards `compile_expr` / `release_context` / `reset_after_error` calls through a small vtable to whatever provider was loaded. No LLVM-specific (or any codegen-specific) code lives here — the architecture splits cleanly at this file so the main backend binary need not link LLVM ([from-README] `README:59-87`, [verified-by-code] `jit.c:1-191`).

## Public symbols

| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `jit_enabled` | global bool GUC | `jit.c:33` | Default `false`. Guards all provider loading. |
| `jit_provider` | global string GUC | `jit.c:34` | Library basename, e.g. `"llvmjit"`. |
| `jit_debugging_support` | global bool GUC | `jit.c:35` | Enables GDB symbol registration in the LLVM provider. |
| `jit_dump_bitcode` | global bool GUC | `jit.c:36` | Causes the provider to dump `.bc` files per-compile. |
| `jit_expressions` | global bool GUC | `jit.c:37` | Default `true` — caller still gated by `PGJIT_EXPR` flag. |
| `jit_profiling_support` | global bool GUC | `jit.c:38` | Enables Linux `perf` JIT listener in the LLVM provider. |
| `jit_tuple_deforming` | global bool GUC | `jit.c:39` | Default `true`. |
| `jit_above_cost` | global double GUC | `jit.c:40` | 100000 — planner threshold to set `PGJIT_PERFORM`. |
| `jit_inline_above_cost` | global double GUC | `jit.c:41` | 500000. |
| `jit_optimize_above_cost` | global double GUC | `jit.c:42` | 500000. |
| `pg_jit_available()` | SQL function | `jit.c:56-60` | Returns whether provider can be loaded; calls `provider_init`. |
| `jit_reset_after_error(void)` | function | `jit.c:127-132` | Called from `AbortTransaction` paths; safe no-op if no provider loaded. |
| `jit_release_context(JitContext *)` | function | `jit.c:137-144` | Delegates to provider, then `pfree`s the context shell. |
| `jit_compile_expr(ExprState *)` | function | `jit.c:151-179` | Multi-gate entry point: returns `false` if any precondition fails or no provider loaded; otherwise delegates. |
| `InstrJitAgg(dst, add)` | function | `jit.c:182-191` | Sums `JitInstrumentation` counters (used by EXPLAIN). |

## Internal landmarks

- **The provider vtable** (`provider`, `jit.c:44`) — a single file-local `JitProviderCallbacks` filled in by `provider_init`. Three function pointers: `reset_after_error`, `release_context`, `compile_expr`. The shim has nothing to add beyond dispatch.
- **Sticky-load state machine** (`jit.c:45-46`) — two flags `provider_successfully_loaded` / `provider_failed_loading`. `provider_init` sets `failed=true` BEFORE attempting `load_external_function` so an `ereport(ERROR)` from `load_external_function` (e.g. shared deps missing on disk) doesn't cause silent retry storms. On success both flags are flipped: failed→false, success→true ([verified-by-code] `jit.c:108-116`).
- **Pre-check via `pg_file_exists`** (`jit.c:91-99`) — the comment is explicit: `load_external_function()` would `ereport(ERROR)` on a missing file, and we want a clean "JIT not available, move on" path when LLVM simply isn't installed. So a stat() probe runs first.
- **Provider library path** is `pkglib_path/<jit_provider><DLSUFFIX>` (`jit.c:91`). E.g. `/usr/lib/postgresql/<ver>/lib/llvmjit.so`. The entry symbol name is hardcoded: `_PG_jit_provider_init` (`jit.c:112`).
- **`jit_compile_expr` short-circuits four ways** (`jit.c:163-178`) before ever calling `provider.compile_expr`:
  1. `!state->parent` — no PlanState means no executor-shutdown callback to free the JIT context, so we'd leak until xact end (see big comment at `jit.c:154-162`).
  2. `!(es_jit_flags & PGJIT_PERFORM)` — planner didn't request JIT.
  3. `!(es_jit_flags & PGJIT_EXPR)` — expression-JIT specifically not requested.
  4. `provider_init()` returns false — JIT disabled or loading failed.

## Invariants & gotchas

- **Provider can only be loaded once per backend.** No unload path. If `jit_provider` GUC is changed after first use, the change is silently ignored — the already-loaded vtable wins. [verified-by-code, `jit.c:67-121`]
- **`jit_release_context` always `pfree`s the context shell** even when no provider loaded (`jit.c:142-143`). Callers must not pass NULL — the code assumes a real allocation. [verified-by-code, `jit.c:137-144`]
- **`jit_reset_after_error` is the only re-entry point** after an ERROR thrown from inside JIT-emitted code. The LLVM provider uses it to clear `llvm_in_fatal_on_oom` state and to recycle the LLVMContext on demand. Calling `reset_after_error` when no provider was loaded is a no-op by design ([verified-by-code] `jit.c:127-132`).
- **`PGJIT_OPT3` / `PGJIT_INLINE` flags are not consulted here** — they only matter to the provider. `jit_compile_expr` checks only `PGJIT_PERFORM | PGJIT_EXPR`. This is consistent with the model that `jit.c` is provider-agnostic.
- **`jit_compile_expr` returning `false` is NOT an error** — it just means "interpreter, please." Callers (in `execExpr.c`) treat it as graceful fallback. [verified-by-code, `jit.c:163, 178`]
- **No `jit_compile_deform` symbol** — tuple deforming is initiated from inside `llvm_compile_expr` (when it processes a `FETCHSOME` opcode and emits a deform function inline) rather than as a separate provider callback. The vtable has no `compile_deform` slot. [verified-by-code, `jit.c:43-49`, `jit.h:65-79`]

## Cross-refs

- [[knowledge/subsystems/jit.md]] — fuller architectural overview, README synthesis, and the `llvmjit.c` mental model.
- [[knowledge/files/src/backend/jit/llvm/llvmjit.c.md]] — the only provider that exists in-tree; what gets `dlopen`ed.

## Confidence tag tally
`[from-README]=1 [verified-by-code]=8`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/jit-provider-and-context.md](../../../../idioms/jit-provider-and-context.md)

- [subsystems/jit.md](../../../../subsystems/jit.md)