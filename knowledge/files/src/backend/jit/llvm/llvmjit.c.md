---
path: src/backend/jit/llvm/llvmjit.c
anchor_sha: e18b0cb7344
loc: 1289
depth: read
---

# llvmjit.c

- **Source path:** `source/src/backend/jit/llvm/llvmjit.c`
- **Lines:** 1289
- **Last verified commit:** `e18b0cb7344`
- **Companion files:** `src/include/jit/llvmjit.h`, `src/include/jit/llvmjit_emit.h`, `src/backend/jit/llvm/llvmjit_error.cpp`, `src/backend/jit/llvm/llvmjit_inline.cpp`, the per-expr / per-deform codegen siblings.

## Purpose

Core of the loadable LLVM JIT provider. Owns the per-backend LLVM session: creates the `LLVMContextRef`, target machine and two ORC `LLJIT` instances (one at `-O0`, one at `-O3`), the resource owner that ties `LLVMJitContext` lifetime to a subxact / xact, the bitcode-loaded type information that keeps codegen in sync with C structs, and the pass-pipeline driver that runs inlining / optimization / emission. It exposes `_PG_jit_provider_init` so `jit.c` can populate its vtable when the `.so` is `dlopen`ed ([verified-by-code] `llvmjit.c:152-157`).

## Public / exported symbols

| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `_PG_jit_provider_init(cb)` | extern entry point | `llvmjit.c:152-157` | Loaded by `jit.c:provider_init` via `load_external_function`. Fills the three callback slots. |
| `PG_MODULE_MAGIC_EXT` | macro | `llvmjit.c:142-145` | `.name="llvmjit"`. Required so the loader accepts it. |
| `llvm_create_context(jitFlags)` | function | `llvmjit.c:223-247` | Allocates `LLVMJitContext` in `TopMemoryContext`, registers it with `CurrentResourceOwner`, lazy-initialises the LLVM session on first call. |
| `llvm_mutable_module(context)` | function | `llvmjit.c:316-334` | Returns the in-progress `LLVMModuleRef`, creating one on demand. |
| `llvm_expand_funcname(context, base)` | function | `llvmjit.c:341-356` | `<base>_<modulegen>_<counter>` — guaranteed unique per emitted function. GDB dislikes dots so underscores are used. |
| `llvm_get_function(context, funcname)` | function | `llvmjit.c:362-416` | Triggers `llvm_compile_module` if not yet compiled, looks up the symbol, returns a native pointer. Accumulates emission time into `JitInstrumentation`. |
| `llvm_pg_var_type(name)` / `llvm_pg_var_func_type(name)` | functions | `llvmjit.c:422-455` | Pull cached `LLVMTypeRef` for a global / function from the `llvmjit_types.bc` module. Sole sync mechanism between C and IR. |
| `llvm_pg_func(mod, funcname)` | function | `llvmjit.c:464-486` | Add (or reuse) a function declaration in `mod` copying the signature + attributes from the types module. Used by `llvmjit_deform.c` and `llvmjit_expr.c` for every cross-C call. |
| `llvm_copy_attributes(from, to)` | function | `llvmjit.c:516-535` | Copies function-, return-, and parameter-level attributes; used to make JITed functions inline-compatible with their bitcode siblings. |
| `llvm_function_reference(context, b, mod, fcinfo)` | function | `llvmjit.c:540-598` | Returns an `LLVMValueRef` callable for an `fcinfo`: by name for `internal` / `pgextern.<mod>.<fn>`, by pointer-constant global for unknown OIDs. |
| `llvm_split_symbol_name(name, *modname, *funcname)` | function | `llvmjit.c:1050-1083` | Inverse of the `pgextern.X.Y` mangling. Used by inliner + symbol resolver. |
| `llvm_compile_expr` | declared in `llvmjit.h`, defined in `llvmjit_expr.c` | — | Wired into the vtable here at `:156`. |
| `llvm_reset_after_error` | declared in `llvmjit.h`, defined in `llvmjit_error.cpp` | — | Wired in at `:154`. |

## Internal landmarks

- **Per-session globals** (`llvmjit.c:55-101`) — `llvm_context`, `llvm_ts_context`, `llvm_opt0_orc`, `llvm_opt3_orc`, plus the cached `LLVMTypeRef`s (`TypeSizeT`, `TypeDatum`, `StructTupleTableSlot`, …). Initialised by `llvm_session_initialize` on first `llvm_create_context` call, torn down by `llvm_shutdown` via `on_proc_exit`.
- **LLVMContext recycling** (`llvm_recreate_llvm_context`, `:173-213`) — every `LLVMJIT_LLVM_CONTEXT_REUSE_MAX = 100` (`:45`) JIT contexts AND every time `llvm_jit_context_in_use_count == 0`, the LLVM context is disposed and recreated. The big comment at `:160-172` explains the leak it works around: inlining "leaks" types inside the context, no API to free them piecemeal, so periodic full recreate is the only workaround. Module cache must be reset first (`llvm_inline_reset_caches`) to avoid dangling-pointer disposal. [verified-by-code, `llvmjit.c:160-213`]
- **Sticky in-use counter** (`llvm_jit_context_in_use_count`, `:89`) — incremented in `llvm_create_context`, decremented in `llvm_release_context`. `llvm_shutdown` `elog(PANIC)`s if it isn't zero at exit (`:932-934`), which catches leaked contexts.
- **Two LLJIT instances** (`llvm_opt0_orc`, `llvm_opt3_orc`, `:100-101`) — one per opt level. `llvm_compile_module` picks based on the `PGJIT_OPT3` flag (`:718-721`). Same target machine settings except `LLVMCodeGenLevelNone` vs `LLVMCodeGenLevelAggressive` (`:879-888`).
- **Pass pipeline split** (`llvm_optimize_module`, `:603-704`) — LLVM-major-version forked: pre-17 uses the legacy `PassManagerBuilder` API; ≥17 uses the new `PassBuilder` and a string pass spec (`"default<O3>"`, `"default<O0>,mem2reg,inline"`, etc.). The pre-17 path explicitly re-creates the builder every call — comment at `:618-622` calls out that the inliner has per-builder state that otherwise sticks. [verified-by-code, `llvmjit.c:603-704`]
- **Inliner threshold** is hardcoded at 512 (`:630`, `:695`), flagged as "unscientifically determined" in the inline comment.
- **`jit_dump_bitcode` writes `.bc` files** at `MyProcPid.<gen>.bc` and `.optimized.bc` per module (`:733-742`, `:752-761`), in the data directory.
- **ORC's lazy emission** (`:766-803`) — `LLVMOrcLLJITAddLLVMIRModuleWithRT` does NOT emit code; emission happens the first time a symbol is looked up. That's why `llvm_get_function` (not `llvm_compile_module`) wraps `INSTR_TIME_ACCUM_DIFF(emission_counter)` (`:391-407`). Comment at `:399-403`: "lookup time to emission time."
- **Module ownership transfer** (`:789, 798-799`) — once `LLVMOrcLLJITAddLLVMIRModuleWithRT` is called, the module belongs to LLJIT. `context->module = NULL` defends against double-dispose. Repeated on line 805 belt-and-braces.
- **`llvm_shutdown` skips when `llvm_in_fatal_on_oom()`** (`:920-930`) — if we reached the FATAL path through LLVM, the state is corrupt; we'd risk re-entering LLVM. Process exit will reap memory anyway.
- **`llvm_resolve_symbol`** (`:1088-1125`) — the late-binding hook for symbols not in the postgres binary. macOS prefixes object-level symbols with `_`; we strip that here (`:1099-1103`). Routes `pgextern.<mod>.<fn>` names through `load_external_function` (loading an extension's .so if needed) and the rest through `LLVMSearchForAddressOfSymbol`.
- **Object layer customisation** (`llvm_create_object_layer`, `:1180-1210`) — three-way LLVM-major-version fork: ≥22 uses the upstream layer with reserved alloc; the backport-section-memory-manager path is used between LLVM 16 and 21 to work around a bug; older versions use the stock factory. GDB / Perf event listeners attached here per the `jit_debugging_support` / `jit_profiling_support` GUCs.
- **`fatal_on_oom`** discipline is enforced everywhere a real LLVM API is touched — `llvm_create_context`, `llvm_mutable_module`, `llvm_get_function` all `llvm_assert_in_fatal_section()`. Entering / leaving the section is the caller's job (typically `llvm_compile_expr` in `llvmjit_expr.c`). [verified-by-code, `llvmjit.c:228, 319, 367`]
- **`ResOwnerReleaseJitContext`** (`:1282-1289`) — the resource-owner callback that runs at xact / subxact end if the context wasn't explicitly released. Sets `resowner = NULL` so the subsequent `jit_release_context` -> `llvm_release_context` -> `ResourceOwnerForgetJIT` doesn't try to remove from an owner that's already dropping us.

## Invariants & gotchas

- **`llvm_release_context` skips actual LLVM teardown when `proc_exit_inprogress`** (`:269-270`). Comment: an error might have originated inside LLVM, so we do not re-enter. Cleanup falls through to process exit. This is why `llvm_shutdown` is the one with the `llvm_in_fatal_on_oom()` guard — both endpoints respect the same "don't go back in" rule. [verified-by-code, `llvmjit.c:264-270`, `:920-930`]
- **`llvm_create_context` calls `llvm_recreate_llvm_context` on every entry** (`:232`). The recreation only actually runs once the reuse counter hits `LLVMJIT_LLVM_CONTEXT_REUSE_MAX=100` AND no contexts are in use. So in a steady-state busy backend, the recreate is effectively rare — but a backend churning JIT contexts under low concurrency will trigger frequent recreates and pay re-`llvm_create_types` cost each time. [verified-by-code, `llvmjit.c:183-213`]
- **Symbol-pool clearing on every `release_context`** (`:286-300`) — comment notes "It'd be sufficient to do this far less often, but in experiments the required time was small enough to just always do it." File-local TODO, not an [ISSUE].
- **`llvm_function_reference` caches by name**, not by OID. For "unknown function" (no `basename` from `fmgr_symbol`), the synthesised name is `pgoidextern.<OID>` (`:572-574`) and the function pointer is embedded as a runtime constant. Two different OIDs produce two different globals, but the *same* OID in the same module reuses (`:575-577`). [verified-by-code, `llvmjit.c:566-588`]
- **CPU feature autodetection** uses `LLVMGetHostCPUName` + `LLVMGetHostCPUFeatures` (`:874-877`). For a process migrating between heterogeneous machines (e.g. in a containerised env with CPU isolation), the JIT'd code is tied to first-startup features. No re-detection on the fly.
- **`llvm_pg_var_type` / `llvm_pg_func` `elog(ERROR)`** on missing names (`:431, 449, 477-478`). The `llvmjit_types.c` build-time bitcode is the source of truth; if it's stale (e.g. extension built against older PG), JIT codegen fails loudly rather than silently mismangling.

## Potential issues

- `[ISSUE-undocumented-invariant: llvm_release_context decrements llvm_jit_context_in_use_count BEFORE the proc_exit_inprogress early return at :269 (maybe)]` — comment at `:259-262` explicitly defends this ("Consider as cleaned up even if we skip doing so below"), but it means the in-use count is consistent only because both halves agree to skip. A future change that re-orders the decrement could silently regress the PANIC at shutdown. Worth a header comment on the function. [verified-by-code, `llvmjit.c:259-270, 932-934`]

## Cross-refs

- [[knowledge/subsystems/jit.md]] §3 — file roles.
- [[knowledge/files/src/backend/jit/jit.c.md]] — the dispatcher that loads this.
- [[knowledge/files/src/backend/jit/llvm/llvmjit_expr.c.md]] — calls `llvm_create_context`, `llvm_mutable_module`, `llvm_get_function`.
- [[knowledge/files/src/backend/jit/llvm/llvmjit_deform.c.md]] — calls `llvm_pg_func`, `llvm_pg_var_func_type`.

<!-- issues:auto:begin -->
- [Issue register — `jit`](../../../../../issues/jit.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=13`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/jit-expression-codegen.md](../../../../../idioms/jit-expression-codegen.md)
- [idioms/jit-provider-and-context.md](../../../../../idioms/jit-provider-and-context.md)
- [idioms/jit-tuple-deform-and-inline.md](../../../../../idioms/jit-tuple-deform-and-inline.md)
