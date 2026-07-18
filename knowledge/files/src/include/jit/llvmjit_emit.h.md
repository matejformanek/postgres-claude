---
path: src/include/jit/llvmjit_emit.h
anchor_sha: e18b0cb7344
loc: 329
depth: read
---

# src/include/jit/llvmjit_emit.h

## Purpose

Header of short `static inline` wrappers around the LLVM C API (`<llvm-c/Core.h>`,
`<llvm-c/Target.h>`) that make the JIT-emission sites in
`src/backend/jit/llvm/llvmjit_expr.c` and friends terser and immune to
pgindent reformatting. Two flavors of helper:

1. **Constant / type / GEP / load / call shorthands** (`l_int32_const`,
   `l_ptr`, `l_struct_gep`, `l_gep`, `l_load`, `l_call`) — wrap one LLVM C-API
   call each, taking a `LLVMBuilderRef` first to match PG style.
2. **Higher-level emit idioms** (`l_load_struct_gep`, `l_funcvalue`,
   `l_funcnull`, `l_mcxt_switch`, `l_callsite_ro`, `l_callsite_alwaysinline`,
   `l_bb_before_v`, `l_bb_append_v`) — emit the IR equivalent of common
   backend C operations (struct-field load, FunctionCallInfo arg access,
   `CurrentMemoryContext` switch, basic-block creation with `printf`-style
   naming). `[verified-by-code]`

The whole file is guarded by `#ifdef USE_LLVM` (`:16`) so it stays parseable
under cpluspluscheck when LLVM is disabled. `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `l_ptr_const(void *ptr, LLVMTypeRef type)` | `:27` | Emit a host pointer as an LLVM IR constant of `type` |
| `l_ptr(LLVMTypeRef t)` | `:38` | `LLVMPointerType(t, 0)` shorthand |
| `l_int8/16/32/64_const(LLVMContextRef, intN)` | `:47-77` | Per-width integer constant emitters |
| `l_sizet_const(size_t)` / `l_datum_const(Datum)` | `:83-95` | Constants of `TypeSizeT` / `TypeDatum` |
| `l_sbool_const(bool)` / `l_pbool_const(bool)` | `:101-113` | Storage-flavor vs parameter-flavor bool |
| `l_struct_gep`, `l_gep`, `l_load`, `l_call` | `:117-138` | Builder-call wrappers (typed GEP, load, call) |
| `l_load_struct_gep`, `l_load_gep1` | `:144-159` | Compose GEP + load into one helper |
| `l_bb_before_v`, `l_bb_append_v` | `:162-205` | `printf`-named basic-block creation, with `pg_attribute_printf(2,3)` |
| `l_callsite_ro`, `l_callsite_alwaysinline` | `:210-238` | Attach `readonly` / `alwaysinline` string attribute to a callsite |
| `l_mcxt_switch(mod, b, nc)` | `:243-256` | Emit IR that swaps `CurrentMemoryContext` and returns the previous value |
| `l_funcnullp`, `l_funcvaluep`, `l_funcnull`, `l_funcvalue` | `:261-326` | `fcinfo->args[argno].{isnull,value}` accessors over LLVM IR |

## Internal landmarks

- **Bool flavors.** Two separate constant builders for booleans because PG
  uses `bool` (1 byte) for storage but generally `int` width for function
  parameters; `l_sbool_const` uses `TypeStorageBool`, `l_pbool_const` uses
  `TypeParamBool`. Mixing the two emits silently-wrong IR. `[verified-by-code]`
- **`pg_attribute_printf` separation.** `l_bb_before_v` and `l_bb_append_v`
  have a forward declaration carrying `pg_attribute_printf(2, 3)` and a
  definition without it — `[from-comment]`: the attribute is rejected on the
  inline definition by some compilers, so PG splits the prototype and the body.
- **`l_mcxt_switch` uses `LLVMGetNamedGlobal` then falls back to
  `LLVMAddGlobal`** (`:250-251`) — the first time a module emits the helper it
  declares the `CurrentMemoryContext` global; subsequent emissions reuse the
  declaration. Returning the previous context lets the caller restore it in
  an unwind path.
- **`l_funcnullp` / `l_funcvaluep` walk `StructFunctionCallInfoData →
  args[argno] → {isnull,value}`** (`:267-307`) using
  `FIELDNO_FUNCTIONCALLINFODATA_ARGS`, `FIELDNO_NULLABLE_DATUM_ISNULL`,
  `FIELDNO_NULLABLE_DATUM_DATUM` — the JIT mirror of the offsetof-style
  constants in `fmgr.h`. If anyone reorders `NullableDatum` or
  `FunctionCallInfoBaseData`, those FIELDNO_* macros and these emit helpers
  must move together.
- **`LLVMArrayType(StructNullableDatum, 0)`** (`:273,300`) — a zero-length
  array type used purely as the GEP "addressing type"; LLVM accepts it as a
  way of saying "treat as flexible array of NullableDatum".

## Invariants & gotchas

- **`USE_LLVM` gate is total.** Including the header without LLVM is allowed
  but yields zero symbols — every helper is inside `#ifdef USE_LLVM`. Callers
  that themselves don't gate get loud link/compile errors, which is
  intentional. `[from-comment]`
- **`name` parameter on `l_struct_gep` / `l_load` etc. is currently passed
  as `""`** to the wrapped LLVM call, ignoring the caller-supplied string.
  This is a deliberate post-Opaque-Pointers cleanup leftover — the LLVM C API
  no longer needs the name to disambiguate types. Don't "fix" it by passing
  `name` through without checking the wider IR-naming policy.
- **`l_callsite_ro` uses a *string* attribute (`"readonly"`) rather than the
  enum** — string attributes survive cross-module verification quirks. The
  `alwaysinline` helper uses the enum-attribute path with
  `LLVMGetEnumAttributeKindForName`.
- **Inline functions ⇒ ODR risk.** Because every helper is `static inline`,
  including the header in two .c files with different `LLVMContextRef`
  flavors would just compile two copies — no ODR violation, but also no
  shared state. Keep them stateless.

## Cross-refs

- `knowledge/files/src/include/jit/llvmjit.h.md` — the LLVM-side types and
  declarations these helpers consume.
- `knowledge/files/src/include/jit/jit.h.md` — provider-agnostic side.
- `source/src/backend/jit/llvm/llvmjit_expr.c` — primary consumer.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/jit.md](../../../../subsystems/jit.md)
