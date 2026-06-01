# jit (provider-independent JIT + LLVM provider)

- **Source path:** `source/src/backend/jit/` (dispatch) and
  `source/src/backend/jit/llvm/` (LLVM provider)
- **Header path:** `source/src/include/jit/`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **README anchor:** `source/src/backend/jit/README`

## 1. Purpose

Generate native machine code at query-execution time for the two
expression-evaluation hot paths — **tuple deforming** and
**expression evaluation** — replacing the interpreter loops that
otherwise dominate analytics-query CPU time
([from-README] `README:1-46`). The provider-independent `jit.c`
loads an LLVM-backed shared library on demand so the main backend
binary never has to link LLVM ([from-README] `README:59-87`).

## 2. Mental model

- **Two-layer architecture.** Top: `jit.c` defines a tiny `JitProviderCallbacks`
  vtable (`reset_after_error`, `release_context`, `compile_expr`) and a
  loader that `dlopen`s `pkglibdir/llvmjit.so` on first need. Bottom:
  `llvm/` directory implements those callbacks plus all real codegen.
  Dispatch through three pointer calls is the entire indirection
  ([verified-by-code] `jit.c:43-49, 127-179`, `jit.h:65-79`).
- **GUC-gated and lazy.** No provider is loaded until the first
  `jit_compile_expr` call where `jit_enabled = true` and
  `state->parent->state->es_jit_flags & PGJIT_EXPR` is set
  ([verified-by-code] `jit.c:151-178`).
- **Sticky failure.** A load attempt sets `provider_failed_loading`
  first and only clears it on success; subsequent calls short-circuit.
  This prevents repeated expensive `load_external_function` calls
  in a backend that doesn't have LLVM installed
  ([verified-by-code] `jit.c:78-120`).
- **One `JitContext` per query.** Lives in `EState->es_jit`,
  registered with `CurrentResourceOwner`, freed on xact end or
  earlier via `jit_release_context` ([from-README] `README:89-124`).
- **OOM is FATAL.** Inside `llvm_enter_fatal_on_oom()` /
  `llvm_leave_fatal_on_oom()` windows, libstdc++ `new` and LLVM's
  fatal-error and bad-alloc handlers `ereport(FATAL)` — never ERROR
  — because LLVM's internal state isn't safe to leave half-modified
  ([from-README] `README:127-165`, [verified-by-code]
  `llvmjit_error.cpp:54-105`).
- **Type sync via bitcode, not by hand.** `llvmjit_types.c` is a
  small C file referencing every PG struct that codegen needs to
  know. Clang compiles it to bitcode; LLVM loads it at runtime so
  type definitions stay in sync without manual duplication
  ([from-README] `README:168-189`).
- **Field offsets via `#define FIELDNO_*`.** Because LLVM IR has no
  notion of C field names, a small set of `FIELDNO_<STRUCT>_<FIELD>`
  macros live next to the C struct definitions; the JIT uses them
  to index into runtime structs ([from-README] `README:182-189`).
- **Inlining via Clang-emitted bitcode.** Installed in
  `$pkglibdir/bitcode/postgres/` plus an index `postgres.index.bc`,
  with the same layout for extensions ([from-README] `README:194-219`).

## 3. Key files

- `jit/jit.c` (5 KB) — the provider-independent shim. Holds the
  GUCs, loads the provider, calls `compile_expr` / `release_context`
  / `reset_after_error` through the vtable ([verified-by-code]
  `jit.c:43-191`).
- `jit/README` — high-quality conceptual doc; cite it before
  inferring anything about architecture.
- `jit/llvm/llvmjit.c` (~35 KB) — Core LLVM provider. Owns
  `LLVMContextRef` pooling (`LLVMJIT_LLVM_CONTEXT_REUSE_MAX = 100`,
  [verified-by-code] `llvmjit.c:45`), Orc LLJIT setup, type imports,
  `llvm_mutable_module` / `llvm_get_function` from the README.
- `jit/llvm/llvmjit_deform.c` (21 KB) — `slot_compile_deform()`:
  generates a per-(TupleDesc, natts) deforming function with
  fixed-width / NOT NULL branches removed ([from-README]
  `README:30-46`, [verified-by-code] `llvmjit_deform.c:33-40`).
- `jit/llvm/llvmjit_expr.c` (87 KB) — `llvm_compile_expr()`: walks
  the `ExprState->steps` array and emits IR mirroring
  `execExprInterp.c`. The single biggest file in the JIT subdir.
- `jit/llvm/llvmjit_inline.cpp` (24 KB) — cross-module inliner;
  reads `$pkglibdir/bitcode/*/index.bc`, picks worth-inlining
  externals from the module, imports their IR, then lets LLVM's
  inliner do its thing ([from-comment] `llvmjit_inline.cpp:1-20`).
- `jit/llvm/llvmjit_error.cpp` — `llvm_enter_fatal_on_oom`,
  `llvm_leave_fatal_on_oom`, `llvm_in_fatal_on_oom`,
  `llvm_reset_after_error`, plus the libstdc++ new-handler and
  LLVM bad-alloc / fatal-error handlers that all `ereport(FATAL)`
  ([verified-by-code] `llvmjit_error.cpp:28-141`).
- `jit/llvm/llvmjit_wrap.cpp` — small C++ wrappers exposing
  LLVM functionality not in the C API: `LLVMGetFunctionReturnType`,
  `LLVMGetFunctionType`, and a safe SectionMemoryManager
  factory for `USE_LLVM_BACKPORT_SECTION_MEMORY_MANAGER` builds
  ([verified-by-code] `llvmjit_wrap.cpp:37-66`).
- `jit/llvm/llvmjit_types.c` (5 KB) — the type-sync file
  ([from-README] `README:174-181`). Referenced struct names appear
  but only to keep the bitcode honest.
- `jit/llvm/SectionMemoryManager.cpp` — backport of an LLVM section
  memory manager for older LLVMs.

## 4. Key data structures

- **`JitContext`** (`jit.h:57-63`). Just `int flags; JitInstrumentation
  instr;`. Subclassed by `LLVMJitContext` (`llvmjit.h:43-71`) which
  adds `ResourceOwner resowner`, `LLVMContextRef llvm_context`,
  `LLVMModuleRef module`, `bool compiled`, `int counter`,
  `List *handles` (the live module/resource-tracker pairs from
  `LLVMJitHandle` `llvmjit.c:48-52`).
- **`JitProviderCallbacks`** (`jit.h:74-79`). Three function
  pointers: `reset_after_error`, `release_context`, `compile_expr`.
  Populated by the provider's `_PG_jit_provider_init` (`jit.h:67`,
  [verified-by-code] `jit.c:111-114`).
- **`JitInstrumentation`** (`jit.h:27-46`). `created_functions`
  plus four `instr_time` counters: `generation_counter`,
  `inlining_counter`, `optimization_counter`, `emission_counter`,
  with `deform_counter` rolled into generation.
- **`SharedJitInstrumentation`** (`jit.h:51-55`). DSM-friendly
  variable-length variant for parallel workers.
- **Type holders** in `llvmjit.h:74-100` — `TypeDatum`, `TypeSizeT`,
  `StructTupleTableSlot`, `StructExprState`, etc. — globals set
  from `llvmjit_types.c` bitcode on provider init.

### Flag bits (`jit.h:18-24`)
`PGJIT_NONE=0`, `PGJIT_PERFORM=1<<0`, `PGJIT_OPT3=1<<1`,
`PGJIT_INLINE=1<<2`, `PGJIT_EXPR=1<<3`, `PGJIT_DEFORM=1<<4`.
These map onto the cost-GUCs: `jit_above_cost` sets `PERFORM`;
`jit_optimize_above_cost` adds `OPT3`; `jit_inline_above_cost`
adds `INLINE`; `jit_expressions` / `jit_tuple_deforming` toggle
`EXPR` / `DEFORM` ([from-README] `README:266-296`).

## 5. Control flow — the common paths

### 5.1 `jit_compile_expr(state)` [verified-by-code] `jit.c:151-179`
1. If `state->parent == NULL` → return false. Comment explains:
   creating a one-off context would leak until xact end and slow
   gdb to a crawl ([from-comment] `jit.c:154-164`).
2. If `!(es_jit_flags & PGJIT_PERFORM)` → false.
3. If `!(es_jit_flags & PGJIT_EXPR)` → false.
4. `provider_init()`:
   - Quick exit if `!jit_enabled` or `provider_failed_loading`.
   - Already loaded? return true.
   - `snprintf("%s/%s%s", pkglib_path, jit_provider, DLSUFFIX)`,
     `pg_file_exists` probe → if missing, set
     `provider_failed_loading = true` and return false
     ([verified-by-code] `jit.c:86-99`).
   - Set `provider_failed_loading = true` *first*, then
     `load_external_function(path, "_PG_jit_provider_init", true,
     NULL)` and call it with `&provider`. Only on success clear
     `provider_failed_loading` and set
     `provider_successfully_loaded` ([verified-by-code]
     `jit.c:101-120`).
5. Call `provider.compile_expr(state)`.

### 5.2 `provider.compile_expr` (LLVM impl)
At a high level (not deep-read):
1. Create/reuse `LLVMJitContext`, register with
   `CurrentResourceOwner`, attach to `state->parent->state->es_jit`.
2. `llvm_mutable_module(context)` returns the current module
   (creating one on demand).
3. Walk `state->steps[]`, emit IR via the helpers in
   `llvmjit_emit.h`. Inline candidates are remembered for later.
4. If `PGJIT_INLINE` flag set → `llvm_inline(mod)`.
5. Optimize at O0 or O3 depending on `PGJIT_OPT3`.
6. Hand module to Orc LLJIT; emit. Patch `state->evalfunc` to point
   at the emitted function. ([from-README] `README:91-124, 247-296`)

### 5.3 Error recovery [verified-by-code] `jit.c:127-132` +
`llvmjit_error.cpp:96-105`
After ERROR, `PostgresMain`'s sigsetjmp loop calls
`jit_reset_after_error()` → `provider.reset_after_error()` →
LLVM provider calls `llvm_reset_after_error()` which unconditionally
unregisters all three handlers and zeros `fatal_new_handler_depth`.
This is why callers do *not* need PG_TRY/CATCH around `enter_fatal_on_oom`
sections ([from-README] `README:158-165`).

## 6. Locking and invariants

- **OOM inside LLVM must be FATAL, not ERROR.** ([from-README]
  `README:152-158`, [verified-by-code]
  `llvmjit_error.cpp:113-141`). All three handlers `ereport(FATAL)`.
- **`llvm_enter/leave_fatal_on_oom` are reference-counted** via
  `fatal_new_handler_depth`; the handlers are only installed when
  depth goes 0→1 and uninstalled when it returns to 0
  ([verified-by-code] `llvmjit_error.cpp:54-79`). This is so
  extensions using libstdc++ (e.g. PostGIS) aren't disturbed when
  no JIT is in progress.
- **One `JitContext` per `EState`.** Cleanup happens at end-of-query
  via resowner, *or* explicitly via `jit_release_context()` to free
  earlier ([from-README] `README:91-105, 127-140`).
- **Sticky-failure pattern.** `provider_failed_loading = true` is
  set *before* the dl-load so a partial-success → ereport leaves
  the flag stuck; subsequent calls don't retry ([from-comment]
  `jit.c:78-110`).
- **Caching of generated code is not implemented** — known
  limitation, blocked on getting absolute pointers out of generated
  code ([from-README] `README:222-244`).
- **`FIELDNO_*` macros are load-bearing.** If you renumber a field
  in a struct used by JIT, you must update the macro next to it,
  or codegen will silently read wrong memory ([from-README]
  `README:182-189`).

## 7. Interactions with other subsystems

- **executor/execExpr.c** — calls `jit_compile_expr` from
  `ExecReadyExpr`. Steps array is the IR source.
- **executor/execTuples.c** — calls `slot_compile_deform` via
  `slot_getsomeattrs_int` when deforming a frequently-touched slot.
- **utils/resowner** — JIT contexts are resowner-managed.
- **postmaster / dynloader** — `load_external_function` brings in
  `llvmjit.so` (the real symbol is `_PG_jit_provider_init`).
- **EXPLAIN ANALYZE** — `InstrJitAgg` rolls per-worker counters
  into `JitInstrumentation` for display.

## 8. Tests

- `src/test/regress/sql/jit.sql` — small regress test; mostly
  EXPLAIN-driven, runs with low `jit_above_cost` so JIT actually
  triggers.
- `src/test/modules/test_misc/` — has some JIT-on/off tests.
- Real coverage comes from running the whole regression suite with
  `jit_above_cost = 0`; many buildfarm members do this.

## 9. Open questions / unverified claims

- The exact `LLVMJitContext.handles` lifecycle (resource_tracker
  release order vs. resowner) not deep-traced.
- `llvmjit_inline.cpp` index-file format read only at the comment
  level.
- LLVM-version compat code in `llvmjit.c` (`#if LLVM_VERSION_MAJOR > 16`)
  not validated against the C-API headers actually in use.
- `SectionMemoryManager.cpp` not opened; appears to be a verbatim
  backport per the README in `SectionMemoryManager.LICENSE`.
- The "two `provider_failed_loading = true` sets" pattern is
  documented in the comment but the precise failure mode it
  guards against could use a real-world repro.

## 10. Glossary

- **JIT provider** — the shared library implementing
  `JitProviderCallbacks`. Currently only `llvmjit`.
- **JIT context (`JitContext`)** — per-query container for emitted
  modules + LLVM resources, tied to an `EState` and resowner.
- **LLVM module** — LLVM's TU-equivalent. PG emits multiple
  functions per module so the inliner can do its job.
- **Orc LLJIT** — LLVM's "ORC" JIT framework; the v2 API replaced
  MCJIT.
- **Tuple deforming** — turning a packed `HeapTuple` into a
  `TupleTableSlot`'s `tts_values`/`tts_isnull` arrays. JITted
  deforming compiles in the TupleDesc and skips branches.
- **Inlining** — replacing `OidFunctionCallN` with the body of
  the called operator's C code, by reading bitcode from
  `$pkglibdir/bitcode/`.
- **`FIELDNO_*`** — macro convention for syncing C struct field
  positions into JIT codegen.
- **`PGJIT_*` flags** — bitmask in `es_jit_flags` controlling what
  the JIT actually does for this query.
- **Sticky failure** — once provider load fails in a backend, JIT
  is disabled for the rest of the backend's life.
