---
path: src/backend/jit/llvm/llvmjit_types.c
anchor_sha: e18b0cb7344
loc: 185
depth: read
---

# llvmjit_types.c

- **Source path:** `source/src/backend/jit/llvm/llvmjit_types.c`
- **Lines:** 185
- **Last verified commit:** `e18b0cb7344`
- **Companion files:** `src/backend/jit/llvm/llvmjit.c` (`llvm_create_types`, the loader); `src/backend/jit/llvm/Makefile` / `meson.build` (the build rule that emits `llvmjit_types.bc`); `src/backend/jit/README` (architecture rationale at `:168-189`).

## Purpose

The single most-misnamed file in the JIT — this is **not C code that runs**. It's a small reference-source file that the build compiles to LLVM bitcode (`llvmjit_types.bc`, installed in `pkglibdir`); the LLVM provider then loads that bitcode at runtime and pulls type descriptions and function signatures from it via `LLVMGetNamedGlobal` / `LLVMGetNamedFunction`. This is how the IR generator stays bit-compatible with the C struct definitions: any field reorder, any signature change, any `bool`-as-i1-vs-i8 ABI subtlety is mechanically reflected in the bitcode without manual re-declaration in C. The big block comment at `:8-17` is explicit: "this file will not be linked into the server, it's just converted to bitcode" ([from-comment] `llvmjit_types.c:8-25`).

## Public symbols

| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `TypePGFunction` | global `PGFunction` | `:48` | Loaded as `LLVMTypeRef TypePGFunction` in `llvmjit.c`. |
| `TypeSizeT` | global `size_t` | `:49` | Native size_t. |
| `TypeDatum` | global `Datum` | `:50` | Datum width (pointer-width on most platforms). |
| `TypeStorageBool` | global `bool` | `:51` | The "stored" bool — i8 on most ABIs. Distinct from the i1 produced by function returns (see `FunctionReturningBool`). |
| `TypeExecEvalSubroutine` | global `ExecEvalSubroutine` | `:53` | Function-pointer type. |
| `TypeExecEvalBoolSubroutine` | global `ExecEvalBoolSubroutine` | `:54` | Boolean-returning eval subroutine. |
| `StructNullableDatum` | global `NullableDatum` | `:56` | One of ~18 struct templates. |
| `StructAggState` | global `AggState` | `:57` | |
| `StructAggStatePerGroupData` | global `AggStatePerGroupData` | `:58` | |
| `StructAggStatePerTransData` | global `AggStatePerTransData` | `:59` | |
| `StructExprContext` | global `ExprContext` | `:60` | |
| `StructExprEvalStep` | global `ExprEvalStep` | `:61` | |
| `StructExprState` | global `ExprState` | `:62` | |
| `StructFunctionCallInfoData` | global `FunctionCallInfoBaseData` | `:63` | |
| `StructHeapTupleData` | global `HeapTupleData` | `:64` | |
| `StructHeapTupleHeaderData` | global `HeapTupleHeaderData` | `:65` | |
| `StructMemoryContextData` | global `MemoryContextData` | `:66` | |
| `StructTupleTableSlot` | global `TupleTableSlot` | `:67` | |
| `StructHeapTupleTableSlot` | global `HeapTupleTableSlot` | `:68` | |
| `StructMinimalTupleTableSlot` | global `MinimalTupleTableSlot` | `:69` | |
| `StructTupleDescData` | global `TupleDescData` | `:70` | |
| `StructPlanState` | global `PlanState` | `:71` | |
| `StructMinimalTupleData` | global `MinimalTupleData` | `:72` | |
| `AttributeTemplate(PG_FUNCTION_ARGS)` | extern function | `:80-87` | Source of function/return/parameter attributes for emitted V1 functions. |
| `ExecEvalSubroutineTemplate(...)` | extern function | `:94-104` | Signature template for non-bool eval subroutines. |
| `ExecEvalBoolSubroutineTemplate(...)` | extern function | `:106-118` | Signature template for bool-returning eval subroutines. |
| `FunctionReturningBool(void)` | extern function | `:125-130` | Solves the "returned bool is i1, stored bool is i8" mismatch (`:120-124`). |
| `referenced_functions[]` | global array | `:137-185` | The "function symbol pinning" trick — see below. |

## Internal landmarks

- **`StaticAssertVariableIsOfType`** (`:84, 102, 114`) — compile-time assertions that the template function pointer actually matches the declared typedef. Catches signature drift at build time, not runtime. (Renamed from `AssertVariableIsOfType` to `StaticAssertVariableIsOfType` in `137d05df2f2`, Peter Eisentraut, 2026-02-03.)
- **The "non-static globals" trick** (`:43-47`) — every `TypeX` / `StructX` is a file-scope global with no `static`. The trick is that clang/LLVM cannot remove the symbol because it has external linkage; therefore its type stays in the bitcode and is reachable via `LLVMGetNamedGlobal`. Comment is explicit: "These have to be non-static, otherwise clang/LLVM will omit them. As this file will never be linked into anything, that's harmless."
- **`referenced_functions[]`** (`:137-185`) — an array of function pointers to every `ExecEval*` helper that JITed expression code may call (plus a few from `slot_getsomeattrs_int`, `varsize_any`, `strlen`). Same trick as the globals: declaring them as initialisers of a non-static array forces clang to emit declarations and signatures in the bitcode. Without this, `llvm_pg_func` (in `llvmjit.c`) would fail to find the named function in `llvm_types_module`.
- **`AttributeTemplate`** (`:80-87`) — the body just `PG_RETURN_NULL()`s and is never called. Its job is to be a clang-emitted function whose function-level / return-value-level / parameter-level attributes (`nounwind`, `readonly`, calling conv, alignment of parameters, etc.) match what the compiler would put on any real `PGFunction`. `llvm_copy_attributes(AttributeTemplate, v_to)` in `llvmjit.c:516` is how every emitted function picks them up.

## Invariants & gotchas

- **This file is NEVER linked into the server binary** (`:14-17` comment). Build rules compile it through clang to bitcode and install it; if a packager forgets `llvmjit_types.bc` in the install layout, `llvm_create_types` in `llvmjit.c:1002-1015` will `elog(ERROR, "LLVMCreateMemoryBufferWithContentsOfFile ... failed")`. The `pkglibdir/llvmjit_types.bc` is therefore a **hard runtime dependency** of the JIT provider.
- **Adding a struct used by JITed code requires three coordinated changes:** declare a `StructX` here, add a `StructX = llvm_pg_var_type("StructX")` line in `llvm_create_types` (`llvmjit.c:1023-1040`), and define / extern the `LLVMTypeRef StructX` in `llvmjit.h`. If you skip step 2 the global is silently NULL until first dereference.
- **Adding a function callable from JITed expressions** means appending it to `referenced_functions[]`. Otherwise `llvm_pg_func` in `llvmjit.c:464-486` will `elog(ERROR, "function %s not in llvmjit_types.c")` the first time a JITed step tries to call it.
- **The bool ABI dance** (`:120-130`) — Clang emits a bool-returning function with i1 return type but stores bool as i8 in memory. To produce an i1 from a stored bool at JIT time, you load i8 then truncate, or compare to zero. `TypeParamBool` (set via `load_return_type(... "FunctionReturningBool")` in `llvmjit.c:1020`) is the i1 type; `TypeStorageBool` (`:51`) is the i8 type. Treating the two as interchangeable is the bug class this dual-symbol guards against.
- **`StaticAssertVariableIsOfType` checks compile-time** — if you change the typedef of `ExecEvalSubroutine` in `execExpr.h` without updating the corresponding template here, this file's build will fail loudly before any runtime issue can appear.

## Potential issues

- `[ISSUE-undocumented-invariant: referenced_functions[] order is incidental but the SET of pointers is contractual (nit)]` — adding a new ExecEval helper to `execExpr.c` without appending here is the most common JIT-related contributor mistake. A `clang -Wunused-function`-style check that warns about JIT-callable helpers missing from this array would help, but there's no such check today; the only catch is the runtime `elog(ERROR)` in `llvm_pg_func`. [verified-by-code, `llvmjit_types.c:137-185`, `llvmjit.c:464-486`]

## Cross-refs

- [[knowledge/subsystems/jit.md]] §2 (mental-model bullet "Type sync via bitcode, not by hand").
- [[knowledge/files/src/backend/jit/llvm/llvmjit.c.md]] — `llvm_create_types`, `llvm_pg_var_type`, `llvm_pg_func` are the consumers.

<!-- issues:auto:begin -->
- [Issue register — `jit`](../../../../../issues/jit.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[from-comment]=2 [verified-by-code]=6`
