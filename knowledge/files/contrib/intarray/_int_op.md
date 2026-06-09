# _int_op.c

`source/contrib/intarray/_int_op.c` (436 lines).

## One-line summary

SQL-callable operator functions and array-helper functions for `int4[]`: `@>`/`<@`/`&&` containment + overlap, `&`/`|` (intersect, union), `#` (cardinality / position-of), `sort`/`uniq`/`subarray`/`push`/`del`. Hosts the module's `PG_MODULE_MAGIC_EXT`.

## Public API / entry points

- `PG_MODULE_MAGIC_EXT` (intarray) — `source/contrib/intarray/_int_op.c:8-11` [verified-by-code]
- Set/array operators:
  - `_int_contains(a,b)` (`@>`), `_int_contained(a,b)` (`<@`) — `source/contrib/intarray/_int_op.c:13-46`
  - `_int_overlap(a,b)` (`&&`) — `_int_op.c:103-123`
  - `_int_union` (`|`), `_int_inter` (`&`) — `_int_op.c:126-165`
  - `_int_same` (`=`), `_int_different` (`<>`) — `_int_op.c:14,49-97`
- Helpers:
  - `intset(int4)`, `icount(int[])`, `sort(int[],text)`, `sort_asc`/`sort_desc`, `uniq`, `idx(int[],int)`, `subarray(int[],int,int)` — `_int_op.c:168-324`
  - `intarray_push_elem`/`intarray_push_array` (concat), `intarray_del_elem` — `_int_op.c:326-378`
  - `intset_union_elem`, `intset_subtract` — `_int_op.c:380-436`

## Key invariants

- All operators take **independent palloc'd copies** via `PG_GETARG_ARRAYTYPE_P_COPY` and may sort them in place (`PREPAREARR`/`SORT`/`QSORT`) — `_int_op.c:33-35,79-80,105-106,128-129,149-151,201-203,253-256,395-411` [verified-by-code]
- `_int_contains` PREPAREARRs both operands (sort+uniq), then calls `inner_int_contains` — order-independent — `_int_op.c:31-46`
- `_int_same` is sorted-by-content equality, NOT permutation equality of original array — sorts both before compare — `_int_op.c:56-97`
- `sort()` accepts only `"ASC"` (or NULL → ASC default) or `"DESC"`, case-insensitively, **exactly 3 or 4 chars** — anything else → `ERRCODE_INVALID_PARAMETER_VALUE` — `_int_op.c:211-225`
- `subarray` 1-based start, negative start = from-end; len ≤ 0 truncates differently (0 means "to end", negative means "stop N from end") — `_int_op.c:286-322` [verified-by-code]
- `intset_union_elem` returns sorted-unique result; `intset_subtract` requires both sides sorted-unique before the merge-subtract — `_int_op.c:380-436`

## Notable internals

- `intarray_del_elem` does an in-place compaction (no second buffer) and `resize_intArrayType` at the end — `_int_op.c:351-378` [verified-by-code]
- `intset_subtract` allocates `new_intArrayType(ca)` (size of left side) and resizes down — guaranteed sufficient — `_int_op.c:416,432`
- `_int_contained` is implemented as `DirectFunctionCall2(_int_contains, b, a)` — `_int_op.c:21-28`
- `icount` is just `ARRNELEMS()`, doesn't validate NULL-free (no `CHECKARRVALID`) — silently returns count including NULL slots if present (cf. `_int_contains` which would have rejected) — `_int_op.c:188-196` [verified-by-code]
- `idx` returns 1-based position of first match, 0 if not found — linear scan (no requirement that input be sorted) — `_int_op.c:262-274,337-351`

## Trust boundary / Phase D surface

- **`|` (union) and `&` (intersect) palloc-DoS** — both `_int_union` and `_int_inter` call `inner_int_union`/`inner_int_inter` which `new_intArrayType(na+nb)` or `Min(na,nb)`. For two adversary-supplied 134M-element arrays (max int4[] size), `_int_union` would attempt `palloc(2 * 134M * 4)` = ~1 GB which palloc rejects. Reachable from any context where a user can pass two large `int4[]` values to `|`. Mitigation: bounded by MaxAllocSize. — `_int_op.c:126-165`, `_int_tool.c:78-181`
- **`intarray_concat_arrays` no upfront cap**: `new_intArrayType(ac + bc)` then two memcpys. Same OOM ceiling. — `_int_op.c:370-385`
- **`PG_GETARG_ARRAYTYPE_P_COPY` semantics on toasted args**: forces detoast + copy. Combined with `PREPAREARR` (in-place sort/unique), this is safe but doubles memory transiently. Worst case: 2× peak vs the toasted bytes. — `_int_op.c:34-35`
- **`icount` skips `CHECKARRVALID`**: returns `ARRNELEMS` of a possibly-NULL-containing array — caller sees a count without learning whether NULLs are present. Most other ops error on NULLs, so this is a slight semantic inconsistency. [verified-by-code] [ISSUE-CONSISTENCY] — `_int_op.c:188-196`
- **`sort()` string parsing**: `dc == 3` for "ASC"/"asc" and `dc == 4` for "DESC"/"desc" — exact length match. Trailing whitespace or longer-than-4 strings → error. Could be silently confusing for users — `_int_op.c:211-225`
- **`_int_contains` always PREPAREARRs both sides**: O(n log n) every time; an attacker calling `@>` on two big arrays does the sort work per row. Cross-link to `_int_selfuncs.c` — the planner uses MCE-based estimates that may under-cost this. — `_int_op.c:31-46`
- **Selectivity wrappers** live in `_int_selfuncs.c` — these operator functions don't read pg_statistic directly.

## Cross-references

- `_int_tool.c` — all the `inner_*` workers
- `_int_selfuncs.c` — selectivity routing
- `utils/array.h` — `ArrayType` macros
- A11 contrib top-4 (intagg etc., similar copy-everything operator semantics)

## Issues spotted

- [ISSUE-DOS: `_int_union` / `_int_inter` / `intarray_concat_arrays` palloc up to `(na+nb)*4` bytes with no upfront cap (Low — palloc errors)]
- [ISSUE-CONSISTENCY: `icount` does not `CHECKARRVALID`; counts NULL-bitmap entries without erroring (Low)]
- [ISSUE-PERF: `_int_contains` re-sorts both sides on every call; high-cardinality joins on `@>` pay O(n log n) per row not amortised (Info)]
- [ISSUE-USABILITY: `sort()` rejects "asc " (trailing space) with a generic "must be ASC or DESC" error (Trivial)]
