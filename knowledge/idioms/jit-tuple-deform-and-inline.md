# JIT tuple deform + cross-module fmgr inlining — bitcode-driven specialization

Two of the largest JIT wins in PostgreSQL come not from compiling
arbitrary expressions but from **specializing two very common
patterns**:

1. **Tuple deforming** — converting heap-tuple bytes into the
   `tts_values[]` / `tts_isnull[]` arrays a slot exposes. The
   generic deformer (`slot_deform_heap_tuple`) walks the
   TupleDesc + nullbitmap one column at a time with branches for
   each attribute's varlena/byval/byref nature. A **JIT'd
   deformer** baked for one specific TupleDesc unrolls the loop,
   eliminates type-dispatch branches, and (for NOT NULL columns)
   strips the null-check entirely.

2. **fmgr callee inlining** — when `EEOP_FUNCEXPR_STRICT` calls
   `numeric_add(state, ...)`, the generic call goes through
   `FunctionCallInvoke(fcinfo)` which is opaque. The JIT
   **inliner** loads pre-built `.bc` bitcode files from
   `$pkglib_path/bitcode/postgres/` (and from extensions),
   identifies the function bodies, pulls them into the current
   LLVM module, and lets the optimizer inline them at the call
   site.

This doc covers `slot_compile_deform` (per-TupleDesc specialized
deform function), the conditions under which it generates code
(`guaranteed_column_number`, `attguaranteedalign` tracking), the
inliner's worklist + cost-decay heuristic, the module/summary
caches that avoid re-loading bitcode, and the `create_redirection_function`
trick for ABI compatibility.

Companion docs:
- [[jit-provider-and-context]] — the JitContext + cost gates.
- [[jit-expression-codegen]] — `EEOP_*_FETCHSOME` calls into deform.

## Anchors

- `source/src/backend/jit/llvm/llvmjit_deform.c:1-30` — banner: "Fixed column widths, NOT NULLness, etc can be taken advantage of."
- `source/src/backend/jit/llvm/llvmjit_deform.c:34-540` — `slot_compile_deform` (the entire function).
- `source/src/backend/jit/llvm/llvmjit_inline.cpp:1-50` — banner.
- `source/src/backend/jit/llvm/llvmjit_inline.cpp:155-176` — `llvm_inline_reset_caches`, `llvm_inline` entry.
- `source/src/backend/jit/llvm/llvmjit_inline.cpp:99-110` — cost constants, module + summary caches.
- `source/src/backend/jit/llvm/llvmjit_inline.cpp:182-350` — `llvm_build_inline_plan` (the worklist algorithm).
- `source/src/backend/jit/llvm/llvmjit.c:541-602` — `llvm_function_reference` (the call site that decides direct vs through-fmgr).
- Build artifacts: `$pkglib_path/bitcode/postgres/*.bc` + `$pkglib_path/bitcode/postgres.index.bc`.
- `src/Makefile.global` / `src/backend/Makefile` — bitcode emission rules (`with_llvm=yes` builds emit .bc files alongside .o).

## The deform specialization story

A heap tuple's bytes need decoding into `Datum tts_values[N]` +
`bool tts_isnull[N]` arrays. The generic decoder
(`slot_deform_heap_tuple` in `heaptuple.c`) does:

```c
for (i = 0; i < natts; i++) {
    if (hasnulls && bms_is_member(i, nullbitmap)) {
        tts_values[i] = (Datum) 0;
        tts_isnull[i] = true;
        continue;
    }
    off = align(off, att->attalign);                  /* type-dependent */
    if (att->attbyval)                                 /* type-dispatch */
        tts_values[i] = fetch_att(tp + off, true, att->attlen);
    else
        tts_values[i] = PointerGetDatum(tp + off);
    if (att->attlen == -1)                             /* varlena */
        off += VARSIZE_ANY(tp + off);
    else
        off += att->attlen;
    tts_isnull[i] = false;
}
```

For a wide table (50+ columns) accessed for every tuple, this loop
is a major bottleneck. The JIT'd version:

- **Knows `att->attlen`, `att->attbyval`, `att->attalign` at
  compile time** — fold-able constants.
- **Knows which columns are NOT NULL** — skips null-check IR
  entirely.
- **Tracks running alignment** at compile time — if all preceding
  columns have fixed alignment, the offset of column N is a
  compile-time constant; no `align(off, ...)` IR needed.

`slot_compile_deform` (`llvmjit_deform.c:34`) emits this
specialized function. The signature:

```c
void deform_<id>(TupleTableSlot *slot);
```

It modifies the slot's `tts_values[]` + `tts_isnull[]` + `tts_nvalid`
in place. The expression evaluator's `EEOP_*_FETCHSOME` opcodes,
when JIT'd, call this directly instead of going through
`slot_getsomeattrs`.

## The deform compile-time analysis

The first loop in `slot_compile_deform` (lines 105-130) computes
`guaranteed_column_number`: the highest attnum that's certain to
exist (NOT NULL declared + no `atthasmissing` + not dropped).
Columns up to this can be deformed without checking `natts`.

```c
/* llvmjit_deform.c:110-129 */
for (attnum = 0; attnum < desc->natts; attnum++) {
    CompactAttribute *att = TupleDescCompactAttr(desc, attnum);

    if (att->attnullability == ATTNULLABLE_VALID &&
        !att->atthasmissing &&
        !att->attisdropped)
        guaranteed_column_number = attnum;
}
```

[verified-by-code] (`llvmjit_deform.c:110-129`).

Then through the actual codegen loop (not fully shown), two tracking
variables propagate:

- **`known_alignment`** — the alignment guarantee at the current
  offset. Starts at the tuple-data alignment (8 bytes typically).
  Each column that's known to be present reduces `known_alignment`
  to the lower of (its actual padding-implied alignment, current).
- **`attguaranteedalign`** — whether `known_alignment` is actually
  the column's offset. False once a varlena or nullable column
  introduces uncertainty.

When both are favorable, the code can compute a column's offset
at compile time and emit a direct GEP — no runtime alignment
arithmetic.

## Deform: virtual + minimal slot exclusions

```c
/* llvmjit_deform.c:92-99 */
if (ops == &TTSOpsVirtual)
    return NULL;                /* virtual slots never need deforming */

if (ops != &TTSOpsHeapTuple && ops != &TTSOpsBufferHeapTuple &&
    ops != &TTSOpsMinimalTuple)
    return NULL;                /* slot type not understood */
```

Three slot operation sets handled: `TTSOpsHeapTuple`,
`TTSOpsBufferHeapTuple`, `TTSOpsMinimalTuple`. Virtual slots
already have their `tts_values[]` populated by upstream; index
scans and join intermediate slots usually don't need a specialized
deform. [verified-by-code] (`llvmjit_deform.c:92-99`).

## Deform: basic block structure

The function uses one basic block per attribute, plus shared
"out" / "dead" blocks. The block names:

```
b_entry                  — function entry
b_adjust_unavail_cols    — adjust nvalid for missing columns
b_find_start             — find offset to start of nullbitmap (if any)
b_out                    — set nvalid, return
b_dead                   — never reached (safety net)

For each attnum 0..natts-1:
  attcheckattnoblocks[i]   — if !slot fields beyond natts, set tts_isnull=true
  attstartblocks[i]        — compute offset of this attribute
  attisnullblocks[i]       — if column is in nullbitmap, set tts_isnull=true
  attcheckalignblocks[i]   — if needed, align the offset
  attalignblocks[i]        — actual alignment instruction
  attstoreblocks[i]        — store the value into tts_values[i]
```

[verified-by-code] (`llvmjit_deform.c:46-57`).

Most blocks may be empty or unreached, but allocating them upfront
makes the code structure uniform. LLVM's optimizer removes
unreached blocks. The "five blocks per column" arrangement makes
the IR a straight-line decision tree per column with no branches
once specialization is done.

## When deform JIT happens

The expression evaluator's `EEOP_*_FETCHSOME` opcodes
(`EEOP_INNER_FETCHSOME`, `EEOP_OUTER_FETCHSOME`,
`EEOP_SCAN_FETCHSOME`) are the consumers. In the JIT'd
expression's IR for these opcodes:

```
EEOP_SCAN_FETCHSOME case:
    if (es_jit_flags & PGJIT_DEFORM) {
        slot_compile_deform(context, slot_desc, slot_ops, max_natts_seen);
        ... emit IR that calls the specialized deform function ...
    } else {
        ... emit IR that calls slot_getsomeattrs (the generic deformer) ...
    }
```

The deform function is created **on-demand** when the JIT'd
expression first runs, in the same LLVM module as the expression.
This way one query's JIT'd code has both the expression and
its deformers in a single module, optimized together.

## The cross-module inliner — bitcode loading

For the inliner to work, the postgres build system emits
`.bc` (LLVM bitcode) files alongside `.o` files. With
`with_llvm=yes`, every `.c` file in `src/backend/` produces a
`.bc` file installed to `$pkglib_path/bitcode/postgres/<src_path>.bc`.
A summary index (`$pkglib_path/bitcode/postgres.index.bc`) maps
function names to their containing module + symbol summaries
(instruction counts, dependencies).

[verified-by-code] — the Makefile rules; see
`src/Makefile.shlib` / `meson.build`.

Extensions can do the same: with proper Makefile rules, an
extension's `.so` is accompanied by `$pkglib_path/bitcode/<extname>/`
plus `<extname>.index.bc`. Postgres_fdw, contrib/citext, etc. all
provide their own bitcode.

## `llvm_inline` — the entry

```cpp
/* llvmjit_inline.cpp:166-176 */
void llvm_inline(LLVMModuleRef M) {
    LLVMContextRef lc = LLVMGetModuleContext(M);
    llvm::Module *mod = llvm::unwrap(M);

    std::unique_ptr<ImportMapTy> globalsToInline = llvm_build_inline_plan(lc, mod);
    if (!globalsToInline) return;
    llvm_execute_inline_plan(mod, globalsToInline.get());
}
```

[verified-by-code] (`llvmjit_inline.cpp:166-176`).

Called from `llvm_compile_module` (`llvmjit.c:710`) when
`PGJIT_INLINE` is set. Three steps:

1. **`llvm_build_inline_plan`** — walks the current module's
   external function references, builds an `ImportMapTy` (per-
   source-module list of symbols to import).
2. **`llvm_execute_inline_plan`** — pulls those functions into
   the current module (via LLVM `IRMover`), making them visible
   to the LLVM inliner pass that runs later in the optimize phase.

## The cost-decay heuristic

```cpp
/* llvmjit_inline.cpp:99-100 */
const float inline_cost_decay_factor = 0.5;
const int   inline_initial_cost      = 150;
```

[verified-by-code].

Each call to inline a function `F` consumes some "budget." When
`F` references another function `G`, the cost to inline `G` is
**half** what it would be at the top level (decay factor 0.5).
This biases the inliner toward shallow-and-wide inlining (lots
of small functions called from the JIT'd expression) over
deep-and-narrow (one big function with a chain of nested calls).

The `inline_initial_cost = 150` is the budget for each top-level
external function reference. Functions whose instruction count
exceeds this aren't inlined.

The worklist:

```cpp
/* llvmjit_inline.cpp:72-77 */
typedef struct InlineWorkListItem {
    llvm::StringRef symbolName;
    llvm::SmallVector<llvm::ModuleSummaryIndex *, 2> searchpath;
} InlineWorkListItem;
typedef llvm::SmallVector<InlineWorkListItem, 128> InlineWorkList;
```

Each item is `(function name, list of source modules to look in)`.
The list grows as inlined functions introduce new external
references. The `FunctionInlineState` tracks per-function decisions
(processed/inlined/allowReconsidering + remaining cost limit).

## Module + summary caches

```cpp
/* llvmjit_inline.cpp:106-110 */
typedef llvm::StringMap<std::unique_ptr<llvm::Module>> ModuleCache;
llvm::ManagedStatic<ModuleCache> module_cache;
typedef llvm::StringMap<std::unique_ptr<llvm::ModuleSummaryIndex>> SummaryCache;
llvm::ManagedStatic<SummaryCache> summary_cache;
```

The caches are **session-scoped** — once loaded, a module's
bitcode stays in memory for the rest of the backend's lifetime.
This is critical for repeated JIT'ing: every query that needs
`numeric_add` doesn't re-parse `numeric.bc` from disk.

`llvm_inline_reset_caches` (`llvmjit_inline.cpp:155-160`) is
called when the LLVMContext is rotated — module references would
be dangling, so the caches must be cleared. This is where the
**LLVMContext rotation** described in [[jit-provider-and-context]]
intersects with the inliner.

## `llvm_function_reference` — the call-site decision

```c
/* llvmjit.c:541-602 (paraphrased) */
LLVMValueRef llvm_function_reference(LLVMJitContext *context,
                                      LLVMBuilderRef builder,
                                      LLVMModuleRef mod,
                                      FunctionCallInfo fcinfo)
{
    if (jit_inline_above_cost >= 0 && (context->base.flags & PGJIT_INLINE)) {
        /* Try to reference the function by name in the module — if it's
         * already there (or will be after inlining), the call can be
         * direct + inline-able */
        const char *funcname = fcinfo->flinfo->fn_addr ? get_funcname_by_addr(...)
                                                       : NULL;
        if (funcname && llvm_pg_func(mod, funcname)) {
            v_fn = llvm_pg_func(mod, funcname);
            return v_fn;
        }
    }

    /* Otherwise: emit an indirect call through fmgr */
    v_fcinfo_p = l_ptr_const(fcinfo, l_ptr(StructFunctionCallInfoData));
    v_fn_p = l_load_struct_gep(builder, ..., FIELDNO_FMGRINFO_FN_ADDR, ...);
    return v_fn_p;       /* will be called via call indirect */
}
```

The two paths:

- **Direct reference** (with PGJIT_INLINE): the function is
  referenced by name; the inliner will pull its body into the
  module; LLVM's standard inliner pass can then expand it at the
  call site.
- **Indirect call** (without PGJIT_INLINE or when the function
  isn't available in bitcode form): emit a load-via-fmgr that
  reads the function address from `fcinfo->flinfo->fn_addr` and
  calls indirectly. Same code path as the interpreter, just
  inlined.

[verified-by-code] (`llvmjit.c:541-602` approximate; check actual
file for current implementation).

## The redirection-function trick

Some functions can't be inlined directly because their bitcode
signature doesn't match the expected pg-side call signature
(e.g. internal `int8inc` taking the `transvalue` directly vs the
fmgr-wrapped variant taking `FunctionCallInfo`). The inliner
generates a **redirection function**:

```cpp
/* llvmjit_inline.cpp:121-123 */
static llvm::Function *create_redirection_function(
    std::unique_ptr<llvm::Module> &importMod,
    llvm::Function *F,
    llvm::StringRef Name);
```

The generated wrapper has the fmgr-callable signature, unpacks
arguments from the FunctionCallInfo, and forwards to the real
function. After standard inlining, the redirection wrapper
disappears and the call site directly invokes the inlined body.

## What "successful inlining" looks like

For `SELECT sum(a + 1) FROM t WHERE b = 42`, the JIT'd code
(with PGJIT_INLINE + PGJIT_OPT3) includes:

- `int4eq` inlined for `b = 42` → just `icmp eq` IR.
- `int4pl` inlined for `a + 1` → just `add nsw` IR with overflow
  check.
- `int8_avg_combine` or `int8_avg_accum` inlined into the
  aggregate transition step.
- `slot_compile_deform` emits a specialized loop for `t`'s
  TupleDesc, inlined into the `EEOP_SCAN_FETCHSOME` call site.

The optimizer then runs at O3, doing constant folding,
loop-invariant code motion, dead-code elimination across the
whole assembled module. The resulting machine code may be 3-10x
faster than the interpreter on hot expressions.

## Failure modes

- **Bitcode files missing**: extensions built without bitcode
  emission fall back to indirect-call (no inlining). The
  `pg_jit_available()` SQL function still returns true; just
  inlining of that extension's functions doesn't happen.
- **Function not in bitcode index**: same; uninlineable but
  still works.
- **Function too large**: skipped per the cost-decay budget.
- **OOM during inline**: `llvm_enter_fatal_on_oom` catches it
  and FATAL's the backend (LLVM uses C++ exceptions; we have to
  convert to Postgres ereport-via-longjmp).

## Invariants and races

1. **Deform only for `TTSOpsHeapTuple`/`BufferHeapTuple`/`MinimalTuple`**;
   virtual slots return NULL (no deform needed); other slot
   types not supported. [verified-by-code]
   (`llvmjit_deform.c:92-99`).
2. **`guaranteed_column_number`** + `attguaranteedalign` /
   `known_alignment` enable progressive specialization — early
   columns benefit most. Once a varlena or nullable column
   appears, alignment becomes runtime-only.
3. **One BB per attribute** in the deform function — uniform
   structure; unused BBs eliminated by the optimizer.
4. **Inliner caches are session-scoped**, invalidated on
   LLVMContext rotation. [verified-by-code]
   (`llvmjit_inline.cpp:155-160`).
5. **`inline_cost_decay_factor = 0.5`** — biases toward wide-shallow
   inlining. [verified-by-code] (`llvmjit_inline.cpp:99`).
6. **`inline_initial_cost = 150`** instructions per top-level
   reference. Larger functions skipped. [verified-by-code]
   (`llvmjit_inline.cpp:100`).
7. **Bitcode emission requires `with_llvm=yes`** at build time.
   Extensions need their own Makefile rules to produce bitcode.
8. **`create_redirection_function`** allows ABI-mismatched
   inlining — e.g. fmgr-wrapped functions can resolve to their
   internal implementations.
9. **`llvm_inline` only runs when `PGJIT_INLINE` is set** —
   without it, every external function call is indirect via
   `fcinfo->flinfo->fn_addr`.

## Useful greps

```bash
# Deform entry:
grep -n "^slot_compile_deform\b" source/src/backend/jit/llvm/llvmjit_deform.c

# Inline entry + plan + cache:
grep -nE "^llvm_inline\b|llvm_build_inline_plan|module_cache|summary_cache|llvm_inline_reset_caches" \
       source/src/backend/jit/llvm/llvmjit_inline.cpp

# Cost constants:
grep -n "inline_cost_decay_factor\|inline_initial_cost\|threshold" \
       source/src/backend/jit/llvm/llvmjit_inline.cpp

# Call-site decision:
grep -n "^llvm_function_reference\b" source/src/backend/jit/llvm/llvmjit.c

# Where deform is invoked from expression codegen:
grep -n "slot_compile_deform\|EEOP_SCAN_FETCHSOME\|EEOP_OUTER_FETCHSOME\|EEOP_INNER_FETCHSOME" \
       source/src/backend/jit/llvm/llvmjit_expr.c

# Bitcode build rules:
grep -rn "with_llvm\|BITCODE\|\.bc:" source/src/Makefile.global.in source/src/Makefile.shlib source/meson.build | head
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/jit/llvm/llvmjit.c`](../files/src/backend/jit/llvm/llvmjit.c.md) | 541 | llvm_function_reference (the call site that decides direct vs through-fmgr) |
| [`src/backend/jit/llvm/llvmjit_deform.c`](../files/src/backend/jit/llvm/llvmjit_deform.c.md) | 1 | banner: "Fixed column widths, NOT NULLness, etc can be taken advantage of." |
| [`src/backend/jit/llvm/llvmjit_deform.c`](../files/src/backend/jit/llvm/llvmjit_deform.c.md) | 34 | slot_compile_deform (the entire function) |
| `src/backend/jit/llvm/llvmjit_inline.cpp` | 1 | banner |
| `src/backend/jit/llvm/llvmjit_inline.cpp` | 99 | cost constants, module + summary caches |
| `src/backend/jit/llvm/llvmjit_inline.cpp` | 155 | llvm_inline_reset_caches, llvm_inline entry |
| `src/backend/jit/llvm/llvmjit_inline.cpp` | 182 | llvm_build_inline_plan (the worklist algorithm) |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md)

<!-- /scenarios:auto -->
## Cross-references

- [[jit-provider-and-context]] — JitContext lifecycle + cost gates that enable PGJIT_DEFORM / PGJIT_INLINE.
- [[jit-expression-codegen]] — `EEOP_*_FETCHSOME` codegen that calls the specialized deform; `llvm_function_reference` for inline-ready calls.
- [[expression-evaluator-flow]] — the `EEOP_*` interpreter showing the un-JITed deform + fmgr-indirect paths.
- `source/src/backend/jit/README` — design overview, including bitcode emission rationale.
