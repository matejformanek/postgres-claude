---
path: src/tutorial/funcs.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 147
depth: deep
---

# `src/tutorial/funcs.c` — canonical "write a C-language SQL function" example

## Purpose

The reference C module for the SQL tutorial's *user-defined function* chapter.
It demonstrates the four argument/return passing conventions a C function must
handle — by-value, by-reference fixed-length, by-reference variable-length, and
composite (row) types — plus how to call another backend function via fmgr.
Bound to the backend through `CREATE FUNCTION ... LANGUAGE C` in the tutorial's
`funcs.sql` / `advanced.sql` scripts. This is the smallest worked example of the
version-1 calling convention, so it serves as the live checklist for the
"add a SQL-callable C function" task.

## Public symbols (all version-1 `Datum f(PG_FUNCTION_ARGS)`)

| Function | Lines | Passing convention demonstrated |
|---|---|---|
| `add_one` | 25-31 | **By value** — `PG_GETARG_INT32` / `PG_RETURN_INT32`. |
| `add_one_float8` | 37-44 | **By ref, fixed length** — `float8` macros hide its pass-by-reference nature. |
| `makepoint` | 48-59 | By-ref fixed length composite-ish — builds a `Point` via `palloc_object`. |
| `copytext` | 65-87 | **By ref, variable length** — the `text` / varlena copy idiom. |
| `concat_text` | 91-105 | Varlena concatenation. |
| `t_starts_with` | 111-124 | **fmgr call-through** — `DirectFunctionCall2Coll(text_starts_with, …)` with a collation. |
| `c_overpaid` | 130-147 | **Composite type** — `GetAttributeByName(t, "salary", &isnull)`. |

## Internal landmarks / idioms shown

- **Varlena construction (the canonical recipe).** `copytext` (funcs.c:65-87)
  is the textbook pattern: allocate `VARSIZE_ANY_EXHDR(t) + VARHDRSZ`, then
  `SET_VARSIZE(new, len + VARHDRSZ)`, then `memcpy(VARDATA(new),
  VARDATA_ANY(t), VARSIZE_ANY_EXHDR(t))`. The comments at funcs.c:70-85 are the
  clearest in-tree explanation of why you read the source through
  `VARDATA_ANY`/`VARSIZE_ANY_EXHDR` (the input may be a *short* 1-byte-header
  datum) but write a full `VARHDRSZ` header. `[from-comment]`
- **`PG_GETARG_TEXT_PP`** (the "PP" = packed pointer) is used for the varlena
  inputs (funcs.c:68,94-95) — the detoast-but-don't-unpack accessor, paired
  with the `_ANY` macros.
- **Collation propagation.** `t_starts_with` pulls `PG_GET_COLLATION()`
  (funcs.c:116) and forwards it via `DirectFunctionCall2Coll`, the correct way
  to call a collation-sensitive builtin from C.
- **Composite access.** `c_overpaid` takes a `HeapTupleHeader`
  (`PG_GETARG_HEAPTUPLEHEADER`) and reads a named column with
  `GetAttributeByName`, returning the `isnull` flag by out-param (funcs.c:138).

## Invariants & gotchas

- **Never write through `VARDATA` of a *short* datum.** The whole point of the
  `copytext` comment block is that the destination is always a freshly
  `palloc`'d full-header varlena, while the source is read through the `_ANY`
  accessors. Mixing these up (e.g. `VARSIZE` instead of `VARSIZE_ANY_EXHDR` on
  a toasted/short input) is a classic varlena bug. `[from-comment]`
- `add_one_float8` exists specifically to make the point that `float8` is
  pass-by-reference internally even though the `PG_GETARG_FLOAT8` /
  `PG_RETURN_FLOAT8` macros make it look by-value (funcs.c:40). On 64-bit
  builds `float8` is in fact pass-by-value via `FLOAT8PASSBYVAL`; the comment
  reflects the historically-portable framing.
- Result varlenas/points are `palloc`'d in the current context and returned;
  the function does not free them (fmgr owns the lifetime). See
  [[idioms/memory-contexts]].

## Cross-refs

- [[idioms/fmgr-and-spi]] — version-1 calling convention, `DirectFunctionCall*`,
  `GetAttributeByName`.
- [[knowledge/files/src/tutorial/complex.c]] — sibling tutorial module (a full
  base type rather than standalone functions).
- [[idioms/memory-contexts]] — varlena allocation in per-call context.

## Potential issues

(none — minimal teaching code; the varlena handling is correct and is itself
the reference pattern.)
