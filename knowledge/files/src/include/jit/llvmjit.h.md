---
path: src/include/jit/llvmjit.h
anchor_sha: e18b0cb7344
loc: 153
depth: read
---

# src/include/jit/llvmjit.h

## Purpose

Public header of the LLVM-based JIT provider that plugs into the
provider-agnostic interface in `jit.h`. Declares the per-context state
(`LLVMJitContext`), the canonical LLVM type / struct references the emitter
uses (`TypeDatum`, `StructFunctionCallInfoData`, …), the entry points the
provider hooks register (`llvm_create_context`, `llvm_get_function`,
`llvm_inline`, `llvm_compile_expr`), and the OOM-handling primitives
(`llvm_enter_fatal_on_oom` / `llvm_leave_fatal_on_oom`) that bridge LLVM's
`std::bad_alloc` world into PG's `ereport(FATAL)` discipline. `[verified-by-code]`

The whole header is wrapped in `#ifdef USE_LLVM` (`:18-152`) so it can be
unconditionally `#include`d by code that may or may not have LLVM, and also in
`extern "C"` (`:33-36`, `:148-150`) because it's included from both the C
backend and the C++ files implementing the provider.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `struct LLVMJitContext` | `:43-71` | Extends `JitContext` with `ResourceOwner`, `LLVMContextRef`, current `LLVMModuleRef`, emitted-objects counter, and a `List *handles` for Orc layers |
| `TypeParamBool`, `TypeStorageBool`, `TypePGFunction`, `TypeSizeT`, `TypeDatum` | `:74-78` | Common scalar `LLVMTypeRef`s used by emit helpers |
| `StructNullableDatum`, `StructTupleDescData`, `StructHeapTupleData`, `StructHeapTupleHeaderData`, `StructMinimalTupleData`, `StructTupleTableSlot`, `StructHeapTupleTableSlot`, `StructMinimalTupleTableSlot`, `StructMemoryContextData`, `StructFunctionCallInfoData`, `StructExprContext`, `StructExprEvalStep`, `StructExprState`, `StructAggState`, `StructAggStatePerTransData`, `StructAggStatePerGroupData`, `StructPlanState` | `:80-96` | Per-struct `LLVMTypeRef` mirrors of PG backend structs the emitter dereferences |
| `AttributeTemplate`, `ExecEvalBoolSubroutineTemplate`, `ExecEvalSubroutineTemplate` | `:98-100` | Template functions linked in from the bitcode-compiled support file |
| `llvm_enter_fatal_on_oom`, `llvm_leave_fatal_on_oom`, `llvm_in_fatal_on_oom`, `llvm_reset_after_error`, `llvm_assert_in_fatal_section` | `:103-107` | OOM-bridge primitives |
| `llvm_create_context`, `llvm_mutable_module`, `llvm_expand_funcname`, `llvm_get_function`, `llvm_split_symbol_name`, `llvm_pg_var_type`, `llvm_pg_var_func_type`, `llvm_pg_func`, `llvm_copy_attributes`, `llvm_function_reference` | `:109-121` | Code-emission API |
| `llvm_inline_reset_caches`, `llvm_inline` | `:123-124` | Inliner entry points |
| `llvm_compile_expr`, `slot_compile_deform` | `:131-134` | Main entry points used by `jit_compile_expr` and slot-deform path |
| `LLVMGetFunctionReturnType`, `LLVMGetFunctionType` | `:142-143` | Compat shims over LLVM C API |
| `LLVMOrcCreateRTDyldObjectLinkingLayerWithSafeSectionMemoryManager` | `:145` | Only when `USE_LLVM_BACKPORT_SECTION_MEMORY_MANAGER` — ARM64 workaround entry point |

## Internal landmarks

- **`LLVMJitContext.handles`** (`:69-70`) — `List *` of Orc resource trackers
  emitted by this context; `jit_release_context` walks them to free JIT
  modules. The `module_generation` counter (`:50-51`) supports a heuristic
  reset of the `LLVMContextRef` when it accretes too many anonymous struct
  types, otherwise type interning in long-lived backends would grow without
  bound. `[from-comment]`
- **`compiled` flag** (`:62-64`) — true if `module` has unemitted IR; the
  release path materializes pending code before destroying the module.
- **OOM trampoline** (`:103-107`) — LLVM throws `std::bad_alloc` on
  allocator failure; the provider's `_PG_jit_provider_init` arms a fatal
  handler so that LLVM exceptions get converted into `ereport(FATAL)` at the
  PG boundary. `llvm_in_fatal_on_oom` is the test guard used by
  `llvm_assert_in_fatal_section`.
- **`extern PGDLLIMPORT`** on every type/value (`:74-100`) — these are
  populated at provider load time (`llvm_session_initialize` in
  `llvmjit_types.c`) and read from the JIT compile path. Static linkers on
  Windows need the explicit DLL import.

## Invariants & gotchas

- **`#ifdef __cplusplus extern "C"`** wraps the *body* (`:33-36`,
  `:148-150`) but the *outer* `#ifdef USE_LLVM` guards everything. Including
  the header from C++ where LLVM is disabled gives an empty translation
  unit — intentional, per `[from-comment]` at `:14-17` so cpluspluscheck
  passes.
- **`AttributeTemplate` / `ExecEval*Template` are *templates*, not
  callbacks.** They're linked in from the bitcode file (`llvmjit_types.bc`)
  so the JIT can copy their attribute set / call signatures into emitted
  functions via `llvm_copy_attributes`. Don't call them at runtime.
- **`USE_LLVM_BACKPORT_SECTION_MEMORY_MANAGER` brings in `<llvm-c/OrcEE.h>`**
  (`:23-25`) and the alternate object-layer constructor (`:145`); the gate
  lives in `llvmjit_backport.h`. If you alter the backport machinery, both
  the gate and this header must match.
- **`LLVMContextRef` per JitContext** (`:55-58`) — the comment is explicit:
  the context is reused across compilations but *occasionally reset*. A patch
  that creates a fresh context per compile would regress steady-state memory.

## Cross-refs

- `knowledge/files/src/include/jit/jit.h.md` — provider-agnostic side of the
  interface.
- `knowledge/files/src/include/jit/llvmjit_emit.h.md` — emit helpers built on
  these types.
- `knowledge/files/src/include/jit/llvmjit_backport.h.md` — ARM64 LLVM <22
  gate.
- `source/src/backend/jit/llvm/llvmjit.c` — implementation of all the
  `llvm_*` entry points declared here.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/jit-expression-codegen.md](../../../../idioms/jit-expression-codegen.md)
- [idioms/jit-provider-and-context.md](../../../../idioms/jit-provider-and-context.md)
