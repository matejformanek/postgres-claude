---
path: src/backend/jit/llvm/llvmjit_deform.c
anchor_sha: e18b0cb7344
loc: 758
depth: read
---

# llvmjit_deform.c

- **Source path:** `source/src/backend/jit/llvm/llvmjit_deform.c`
- **Lines:** 758
- **Last verified commit:** `e18b0cb7344`
- **Companion files:** `src/backend/access/common/heaptuple.c` (`slot_deform_heap_tuple` — the interpreter being replaced), `src/backend/executor/execTuples.c` (`TTSOpsVirtual` / `TTSOpsHeapTuple` / `TTSOpsBufferHeapTuple` / `TTSOpsMinimalTuple`), `src/include/access/tupdesc_details.h` (`CompactAttribute`).

## Purpose

JIT-compile a per-`TupleDesc`, per-slot-type heap-tuple deformer. The single exported entry point `slot_compile_deform(context, desc, ops, natts)` emits an LLVM function that takes one argument (a `TupleTableSlot *`), reads the underlying `HeapTupleHeader`, and stores the first `natts` columns into `slot->tts_values[]` / `slot->tts_isnull[]`. The compile-time knowledge being exploited is the `TupleDesc` itself — every column's length, alignment, NOT-NULL-ness, drop-status, missing-default-status is known at code-gen time, so the resulting function has no per-attribute branches that the interpreter has to take. The function pointer is then called from JITed expression code at `EEOP_*_FETCHSOME` sites (`llvmjit_expr.c`) ([verified-by-code] `llvmjit_deform.c:33-758`).

## Public symbols

| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `slot_compile_deform(context, desc, ops, natts)` | `LLVMValueRef` function | `:33-758` | Returns the new `v_deform_fn`, or `NULL` for unsupported slot kinds. |

## Internal landmarks

- **Slot-type gate** (`:92-99`):
  - `TTSOpsVirtual` → returns `NULL` immediately (virtual tuples have no underlying heap rep to deform).
  - Anything not in {`TTSOpsHeapTuple`, `TTSOpsBufferHeapTuple`, `TTSOpsMinimalTuple`} → returns `NULL`.
  - For `TTSOpsMinimalTuple` the prologue computes the underlying header by subtracting `MINIMAL_TUPLE_OFFSET` (set up around the slot-pointer arithmetic below).
- **`guaranteed_column_number` (`:82, 110-129`)** — the rightmost attno that is *certain* to be present in every tuple (because `attnullability == ATTNULLABLE_VALID && !atthasmissing && !attisdropped`). Lets us skip a `natts >= attnum + 1` branch up to that index.
- **Function shape** (`:131-200`):
  - Signature: `void deform_<gen>_<n>(TupleTableSlot *)`.
  - `LLVMSetLinkage(... LLVMInternalLinkage)` — never directly called from outside the module; the expr-jit code refers to it by `LLVMValueRef` and inlining can erase the call.
  - `LLVMSetParamAlignment(..., MAXIMUM_ALIGNOF)` — promises LLVM that the slot pointer is `MAXALIGN`-aligned, allowing aligned loads.
- **Per-column "block constellation"** (`:46-57`) — six `LLVMBasicBlock` arrays of size `natts`:
  - `attcheckattnoblocks[i]` — guard "does this attno exist?"
  - `attstartblocks[i]` — entry for column i.
  - `attisnullblocks[i]` — null-bitmap test result branch.
  - `attcheckalignblocks[i]` — alignment-needed test.
  - `attalignblocks[i]` — alignment computation.
  - `attstoreblocks[i]` — actual store to `tts_values[i]` / `tts_isnull[i]`.

  At runtime, control flows roughly `attcheckattno → attstart → attisnull → attcheckalign → (attalign|attstore) → attstore → (next column or b_out)`. The big switch-y middle of the file (`:230-740`) emits these blocks per attno.
- **NULL bitmap test (`:439-484`)** — pulls the relevant byte from `t_bits`, masks the per-column bit, and conditionally branches. On the null side it stores `tts_isnull[i] = 1` and a **zero-Datum sentinel** at `tts_values[i] = 0` (`:478-481`); after a null column we set `attguaranteedalign = false` because pad bytes may be inserted before the next live column.
- **Alignment skipping** (`:495-545`) — three-tier:
  1. `known_alignment` already satisfies the column's `alignto` ⇒ skip alignment entirely.
  2. Varlena column (`attlen == -1`): peek at the next byte. Zero ⇒ pad byte, must align; non-zero ⇒ short-header datum, do not align. The branch is emitted inline.
  3. Otherwise emit an `align_offset = (offset + alignto-1) & ~(alignto-1)` expression.
- **Per-column store + offset increment (`:660-740`)** — fixed-width columns advance by `attlen`; `attlen == -1` calls `varsize_any`; `attlen == -2` calls `strlen` then adds 1 for the trailing NUL; `Assert(false)` for any other value (`:710`).
- **Tail block `b_out` (`:744-753`)** — writes back `slot->tts_nvalid = natts` and `slot->off = current_offset` (truncated to int32) and returns void.

## Invariants & gotchas

- **The function is purely a `slot->tts_values/tts_isnull` mutator** — it does not refcount, it does not toast-detoast, and it MUST NOT be called on a slot whose `tts_tuple` / `tts_minimal_tuple` is not present. The interpreter has the same precondition; `EEOP_*_FETCHSOME` ensures the tuple is materialised first. [verified-by-code, `llvmjit_deform.c:33-99` + caller in `llvmjit_expr.c` at the `EEOP_*_FETCHSOME` cases]
- **Datum sign-extension is critical for narrow types.** Recent fix `6911f80379d` (David Rowley, 2025-10-23) replaced zero-extension with **signed** extension when widening `int16`/`int32` to Datum (sizeof(Datum) ≥ 8 on most platforms). Without this, negative values produced by JIT deforming did not bitwise-match the same values produced by the interpreter, breaking `datum_image_eq` / `datum_image_hash` used by Memoize "binary cache mode" and reportedly elsewhere. [verified-by-code, see `git show 6911f80379d` and `llvmjit_deform.c:269, 294` `LLVMBuildZExt` uses are for non-Datum sizes — pure-Datum widening uses sign extension elsewhere]
- **`attnullability == ATTNULLABLE_VALID` + `!atthasmissing` + `!attisdropped`** is the precise triple that lets us treat a column as guaranteed-present. The big comment at `:114-124` is paranoid-explicit: "Be paranoid and also check !attisdropped, even though the combination of attisdropped && attnotnull shouldn't exist." [verified-by-code, `llvmjit_deform.c:110-129`]
- **`attguaranteedalign` is reset to false** any time we pass a varlena (`:521`) or NULL (`:484`) column. Once lost, alignment must be computed from the live offset for every subsequent column until a fixed-width NOT-NULL one resets `known_alignment`.
- **`v_off` is stored in `tts->off` only on the final `b_out` block**, not after every store. The interpreter keeps the offset register-resident inside the loop; the JIT version mirrors that.
- **`LLVMInternalLinkage`** means the deform function is private to its parent module. After `llvm_compile_module` runs the optimization pipeline (in `llvmjit.c`), simple deformers may be wholly inlined into the expression function and disappear as standalone symbols. [verified-by-code, `llvmjit_deform.c:141`, `llvmjit.c:603-700`]

## Potential issues

- `[ISSUE-undocumented-invariant: callers of slot_compile_deform must NOT pass natts > desc->natts (likely)]` — there's no defensive `Assert(natts <= desc->natts)` at entry, but the loop at `:110-129` runs over `desc->natts` and the column emission loop runs over `natts` independently. If `natts > desc->natts` the per-column arrays still have size `natts` but the per-`CompactAttribute` array doesn't. Callers in `llvmjit_expr.c` (`EEOP_*_FETCHSOME`) take `natts` from the executor step's `last_var`, which is bounded by the planner — but a defensive `Assert` would document the precondition. [verified-by-code, `llvmjit_deform.c:33-130`]
- `[ISSUE-doc-drift: header comment doesn't call out the sign-extension subtlety fixed in 6911f80379d (maybe)]` — a half-sentence about "narrow-Datum values are sign-extended, not zero-extended, to match fetch_att()" would make the contract obvious and prevent the regression from recurring. [verified-by-code, `llvmjit_deform.c:1-17` + commit 6911f80379d]

## Cross-refs

- [[knowledge/subsystems/jit.md]] §2 — tuple-deforming role in the JIT design.
- [[knowledge/files/src/backend/jit/llvm/llvmjit.c.md]] — provides `llvm_mutable_module`, `llvm_expand_funcname`, `llvm_pg_func`, `llvm_copy_attributes`.
- [[knowledge/files/src/backend/jit/llvm/llvmjit_expr.c.md]] — calls `slot_compile_deform` from the `EEOP_*_FETCHSOME` cases.

<!-- issues:auto:begin -->
- [Issue register — `jit`](../../../../../issues/jit.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=9`
