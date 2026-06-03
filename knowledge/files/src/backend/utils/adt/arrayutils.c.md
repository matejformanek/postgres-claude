---
path: src/backend/utils/adt/arrayutils.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 264
depth: deep
---

# arrayutils.c

- **Source path:** `source/src/backend/utils/adt/arrayutils.c`
- **Lines:** 264
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/array.h` (`MaxArraySize`, `ArrayType`, `ARR_NDIM`/`ARR_ELEMTYPE`, `deconstruct_array_builtin`, declarations of these helpers), `src/include/common/int.h` (`pg_add_s32_overflow`), `src/include/catalog/pg_type.h` (CSTRINGOID), `src/include/utils/memutils.h`

## Purpose
Low-level subscript/dimension arithmetic shared by `arrayfuncs.c` and the array subscripting/slicing machinery [from-comment `arrayutils.c:3-4`]. Functions split into two camps: those that *assume the caller already range-checked* and therefore skip overflow checks (`ArrayGetOffset`, the `mda_*` helpers), and those that *must* overflow-check because they validate user-supplied dimensionality (`ArrayGetNItems[Safe]`, `ArrayCheckBounds[Safe]`) [verified-by-code `arrayutils.c:25-30`, `46-55`, `104-115`, `147-205`]. `ArrayGetIntegerTypmods` is a higher-level helper turning a `cstring[]` into an int32 array of typmods [verified-by-code `arrayutils.c:227-264`].

## Public symbols
| Symbol | file:line | Role |
|---|---|---|
| `ArrayGetOffset` | `arrayutils.c:31` | subscript list → linear element index (no overflow check) |
| `ArrayGetNItems` | `arrayutils.c:56` | dims → element count (throwing wrapper) |
| `ArrayGetNItemsSafe` | `arrayutils.c:66` | dims → element count; soft-error capable, returns -1 on error |
| `ArrayCheckBounds` | `arrayutils.c:116` | validate lower bounds (throwing wrapper) |
| `ArrayCheckBoundsSafe` | `arrayutils.c:126` | validate lower bounds; soft-error capable |
| `mda_get_range` | `arrayutils.c:152` | slice endpoints → span per dim |
| `mda_get_prod` | `arrayutils.c:166` | dims → subscript scale factors (products) |
| `mda_get_offset_values` | `arrayutils.c:182` | products+spans → per-dim step distances |
| `mda_next_tuple` | `arrayutils.c:207` | odometer increment over an n-tuple subscript |
| `ArrayGetIntegerTypmods` | `arrayutils.c:232` | `cstring[]` → palloc'd int32 typmod array |

## Internal landmarks
- `ArrayGetNItemsSafe` is the real implementation; `ArrayGetNItems` is a thin throwing wrapper passing `escontext = NULL` [verified-by-code `arrayutils.c:56-60`, `66-102`]. Same wrapper pattern for `ArrayCheckBounds`/`ArrayCheckBoundsSafe` [verified-by-code `arrayutils.c:116-120`, `126-145`].
- `ArrayGetNItemsSafe` overflow guard: accumulates the running product in `int64 prod`, casts back to `int32 ret`, and detects truncation via `(int64) ret != prod`; also rejects negative `dims[i]` (which signals an earlier UB-LB overflow) and a final `ret > MaxArraySize` check [from-comment + verified-by-code `arrayutils.c:77-101`].
- `ArrayCheckBoundsSafe` uses `pg_add_s32_overflow(dims[i], lb[i], &sum)` to reject lower bounds that would make the last subscript overflow `int32`; `sum` is `PG_USED_FOR_ASSERTS_ONLY` (only the overflow flag is consumed) [from-comment + verified-by-code `arrayutils.c:104-145`].
- `mda_next_tuple` is a mixed-radix odometer: it advances the least-significant subscript mod its span, carrying upward, and returns the position of the dimension it advanced (or -1 when the whole space is exhausted) [from-comment + verified-by-code `arrayutils.c:197-225`].
- `ArrayGetIntegerTypmods` enforces `CSTRINGOID` element type, 1-D, and no-nulls before deconstructing and `pg_strtoint32`-converting each element [verified-by-code `arrayutils.c:239-261`].

## Invariants & gotchas
- **Two-tier overflow contract.** `ArrayGetOffset`, `mda_get_range`, `mda_get_prod`, `mda_get_offset_values`, `mda_next_tuple` all assume the caller validated dimensions/subscripts and perform plain `int` arithmetic with NO overflow check — calling them on unvalidated user input can silently overflow [from-comment `arrayutils.c:25-30`, `147-151`, `161-165`, `176-181`, `197-206`].
- **`ArrayGetNItems` must run before `ArrayCheckBounds`.** `ArrayCheckBoundsSafe` relies on `ArrayGetNItems[Safe]` having already eliminated negative (overflowed) `dims[]` values [from-comment `arrayutils.c:112-115`].
- **int64 multiplication assumption.** The `ArrayGetNItemsSafe` overflow check only works where native `int64` arithmetic exists; PG accepts this as true on essentially all modern platforms rather than paying for check-divides [from-comment `arrayutils.c:52-54`].
- **`MaxArraySize` is the hard ceiling.** Element count is bounded by `MaxArraySize`; exceeding it raises `ERRCODE_PROGRAM_LIMIT_EXCEEDED` [verified-by-code `arrayutils.c:96-100`].
- **Last subscript = INT_MAX is disallowed** by design: `ArrayCheckBounds` insists `dims[i] + lb[i]` be computable without overflow, so an array whose last subscript equals INT_MAX is rejected [from-comment `arrayutils.c:104-115`].
- **`ArrayGetIntegerTypmods` rejects nulls/multi-dim/wrong-eltype** with distinct SQLSTATEs; callers get a palloc'd result and `*n` set, and must not pass a non-`cstring[]` array [verified-by-code `arrayutils.c:239-263`].

## Cross-references
- [[knowledge/files/src/backend/utils/adt/arrayfuncs.c.md]] — primary consumer of these helpers (construct/deconstruct, slicing, subscripting).
- [[knowledge/files/src/backend/utils/adt/array_userfuncs.c.md]], [[knowledge/files/src/backend/utils/adt/array_typanalyze.c.md]] — sibling array adt files.
- [[knowledge/idioms/error-handling.md]] — `ereturn`/`escontext` soft-error pattern vs throwing wrappers.
- [[knowledge/idioms/memory-contexts.md]] — `palloc` of the result arrays.

## Potential issues
None surfaced. The unchecked-arithmetic helpers are explicitly documented as caller-validated; the int64 platform assumption is a known, documented PG-wide stance.

## Confidence tag tally
- [verified-by-code]: 9
- [from-comment]: 8
- [inferred]: 0
- [unverified]: 0
