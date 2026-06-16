# `contrib/intarray/_int_tool.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~397
- **Source:** `source/contrib/intarray/_int_tool.c`

Shared utility routines for the `intarray` extension. Provides the
sorted-array set primitives (`inner_int_contains`, `inner_int_overlap`,
`inner_int_union`, `inner_int_inter`) used by both the GIN and GiST
opclasses, the `new_intArrayType` / `resize_intArrayType` /
`copy_intArrayType` constructors, the in-place `_int_unique`
deduplicator, a generic comparator (`isort_cmp`) plus a
`sort_template.h`-generated `isort`, and a `gensign` signature-hash
helper for the intbig opclass. [verified-by-code]

**Cross-reference:** this file is **already covered in
`knowledge/files/contrib/intarray/_int.md`** (combined with `_int.h`).
This standalone doc exists for the sweep-A21 per-file invariant; the
authoritative content (and the deeper signature-hash security
discussion) is in `_int.md`. Issues are registered in
`knowledge/issues/intarray.md` under "_int.h + _int_tool.c (combined)".

## API / entry points

- `inner_int_contains(ArrayType *a, ArrayType *b)` (line 14) —
  returns true iff `b ⊆ a`. Linear merge; assumes both arrays
  sorted + unique. O(na + nb). [verified-by-code]
- `inner_int_overlap(ArrayType *a, ArrayType *b)` (line 49) —
  returns true on first common element. Assumes sorted. [verified-by-code]
- `inner_int_union(ArrayType *a, ArrayType *b)` (line 78) — palloc's
  `na + nb` slots, merges sorted, calls `_int_unique` to collapse
  duplicates. Returns new ArrayType. [verified-by-code]
- `inner_int_inter(ArrayType *a, ArrayType *b)` (line 135) —
  palloc's `Min(na, nb)` slots, sorted-merge intersect with adjacent-
  duplicate suppression. [verified-by-code]
- `rt__int_size(ArrayType *a, float *size)` (line 183) — returns
  `ARRNELEMS(a)` as float, used by rtree-style GiST cost helpers.
- `isort` (line 214) — `sort_template.h`-generated sort. Compare
  arg is a `bool*` for ascending/descending; `isort_cmp` is the
  per-element comparator. Avoids fmgr overhead vs `qsort`.
  [verified-by-code]
- `new_intArrayType(int num)` (line 223) — 1-D int4 array
  constructor; returns empty array for `num == 0`. Hard `Assert
  (num == 0)` to catch negative input. [verified-by-code]
- `resize_intArrayType(ArrayType *a, int num)` (line 251) —
  repalloc's, then walks `ARR_NDIM` setting only the first
  dimension to `num` and the rest to 1 (defensive in case of
  unexpected multi-dim). [verified-by-code]
- `copy_intArrayType(ArrayType *a)` (line 282) — `new_intArrayType
  + memcpy`. [verified-by-code]
- `internal_size(int *a, int len)` (line 294) — sum of ranges
  `[a[2i], a[2i+1]]` skipping duplicate range starts; returns -1
  on int32 overflow (sentinel value, see issue). [verified-by-code]
- `_int_unique(ArrayType *r)` (line 312) — in-place dedup via
  `qunique_arg`. [verified-by-code]
- `gensign(BITVECP sign, int *a, int len, int siglen)` (line 324)
  — signature-hash helper for intbig; uses `HASH(sign, val, siglen)`
  macro which is `val % (siglen * 8)`. [verified-by-code]
- `intarray_match_first` / `intarray_add_elem` /
  `intarray_concat_arrays` / `int_to_intset` (lines 337-396) —
  small helpers used by `_int_op.c`. [verified-by-code]

## Notable invariants / details

- All set primitives assume **input is sorted and unique** —
  documented as comments (`/* arguments are assumed sorted &
  unique-ified */` line 13). The contract is enforced at the
  opclass boundary (each `_int_*_op.c` calls `SORT()` before
  reaching these). No runtime check. [verified-by-code]
  [ISSUE-undocumented-invariant: callers must SORT first; no
  assertion (nit) — already noted in _int.md].
- `internal_size` returns `-1` as overflow sentinel (line 307).
  Callers must check for this; the function does not ereport.
  [ISSUE-api-shape: -1 sentinel overload (nit) — already in
  intarray issue register].
- `new_intArrayType` size arithmetic (line 237):
  `nbytes = ARR_OVERHEAD_NONULLS(1) + sizeof(int) * num`. No
  MaxAllocSize guard; relies on caller's `num` being bounded.
  Realistic int4 arrays can't exceed ~134M elements before
  `nbytes > MaxAllocSize` triggers palloc's own check. [verified-
  by-code] [ISSUE-correctness: no preflight size guard, relies
  on palloc to catch — already in intarray issue register].
- `gensign` uses `HASH = val % (siglen * 8)`. Default siglen=252
  → 2016-bit signature, modulo 2016. This is the security-
  relevant signature-tree hash (already a headline issue in
  `knowledge/issues/intarray.md`; see "Signature-tree mod-hash
  trivially spoofable"). [verified-by-code]
- `resize_intArrayType` (line 273-278) defensively loops over
  `ARR_NDIM(a)` setting only the first dim to `num`; this
  protects against the (now-impossible-via-opclass-boundary) case
  of a multi-dim input array. The comment notes "usually 1-D
  already, but just in case." [verified-by-code]
- `isort_cmp` (line 190): the `arg` parameter is a `bool*` for
  asc/desc. Type-erased via `void*` because `sort_template.h`
  requires it. Inlined at template-expansion time. [verified-by-code]

## Potential issues

All issues for this file are already enumerated in
`knowledge/issues/intarray.md` under the "_int.h + _int_tool.c
(combined)" subsection:

- `gensign` mod-hash spoof (security, maybe — but bound by intbig's
  recheck-safety).
- `internal_size` -1 sentinel overload (api-shape, nit).
- `inner_int_union` / `inner_int_inter` palloc up to `(na+nb)*4`
  bytes with no preflight bound (defense-in-depth, nit).
- `new_intArrayType` size arithmetic lacks explicit
  MaxAllocSize/sizeof(int) guard (correctness, nit).

No new issues surface on this re-read; the file is stable and the
sweep-A13 audit was thorough.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `intarray`](../../../issues/intarray.md)
<!-- issues:auto:end -->
