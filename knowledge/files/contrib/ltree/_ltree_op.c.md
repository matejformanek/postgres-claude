# _ltree_op.c

## One-line summary

Operator suite for `ltree[]`: thin OR-folding wrappers around the scalar `ltree` operators (`ltree_isparent`, `ltree_risparent`, `ltq_regex`, `ltxtq_exec`, `lca_inner`) that iterate one-dim `ltree[]` arrays via `array_iterator`. Some variants (`_ltree_extract_*`) additionally return the FIRST matching array element (palloc'd copy) for `extract`-style queries.

## Public API / entry points

All `PG_FUNCTION_INFO_V1`:

OR-fold predicates (returning bool):

- `_ltree_isparent(ltree[], ltree)` (line 71) — true if any element is a parent of the query.
- `_ltree_r_isparent` (line 83) — commutator via `DirectFunctionCall2`.
- `_ltree_risparent`, `_ltree_r_risparent` (lines 92, 104) — reverse-isparent.
- `_ltq_regex(ltree[], lquery)` (line 113), `_ltq_rregex` (line 125).
- `_lt_q_regex(ltree[], lquery[])` (line 134), `_lt_q_rregex` (line 168) — `ltree[]` vs `lquery[]`, both-array variants; OR of OR-folds.
- `_ltxtq_exec(ltree[], ltxtquery)` (line 178), `_ltxtq_rexec` (line 190).

Extract-style (return first matching element or NULL):

- `_ltree_extract_isparent` (line 200), `_ltree_extract_risparent` (line 223), `_ltq_extract_regex` (line 246), `_ltxtq_extract_exec` (line 269).

LCA:

- `_lca(ltree[])` (line 292) — variadic LCA over an `ltree[]` array.

Internal:

- `static bool array_iterator(ArrayType *la, PGCALL2 callback, void *param, ltree **found)` (line 37) — iterates one-dim, non-NULL-bearing array; calls `callback(item, param)` per element; sets `*found` to the first matching element if `found != NULL`.

## Key invariants

- INV-NO-NULLS-NO-MULTIDIM: every entry point that touches an `ltree[]` array validates `ARR_NDIM(la) > 1` and `array_contains_nulls(la)` (lines 43-50 in `array_iterator`, and also in `_lt_q_regex` lines 143-150, and in `_lca` lines 301-308). All hard `ereport(ERROR)`. **No soft-error path.** `[verified-by-code]`
- INV-NEXTVAL-INTALIGN: array elements are walked using `NEXTVAL(x) = (ltree*)( (char*)(x) + INTALIGN(VARSIZE(x)) )` (line 35) — `INTALIGN` (4-byte) matches `pg_type.typalign='i'`. `[verified-by-code]`
- INV-OR-SHORT-CIRCUIT: `array_iterator` returns true on first matching callback (line 60-63). Subsequent elements not examined.
- INV-EXTRACT-COPIES: `_ltree_*_extract_*` functions palloc + memcpy the found element (e.g. line 215-216) — the result is independent of the input array's lifetime. `[verified-by-code]`

## Notable internals

- `array_iterator` is the central helper — all OR-fold variants reduce to it with different `callback` and `param`.
- `_lt_q_regex` (line 134) is the only variant doing `array × array`: outer loop over `lquery[]`, inner loop via `array_iterator` over `ltree[]`. Total cost = O(num_lqueries × num_ltrees).
- `_lca` (line 292) builds an `ltree **a` pointer array of `num` entries (line 310-315), then calls `lca_inner` (defined in `ltree_op.c:525`). For each element in `la`, computes a pointer via `NEXTVAL`. **Note: the loop populates `a[num--]` from highest index to lowest**, but `lca_inner` doesn't care about order. `[verified-by-code]`
- The `callback` is invoked via `DirectFunctionCall2(callback, PointerGetDatum(item), PointerGetDatum(param))` (line 56). The callback is a `PG_FUNCTION_INFO_V1` `Datum`-returning function pointer. Note: `array_iterator`'s `*found` capture works because the inner function returns its bool answer without consuming/freeing `item` — but `ltree_isparent` does call `PG_FREE_IF_COPY(c, 1); PG_FREE_IF_COPY(p, 0)` (`ltree_op.c:243-244`). As in `lquery_op.c:306-317` (see that file's ISSUE), `PG_FREE_IF_COPY` is effectively a no-op in `DirectFunctionCall2` because `flinfo` isn't set up for detoasting. Safe but subtle.

## Trust boundary / Phase D surface

- **Array iteration is O(num_elements)** — bounded by `MaxAllocSize / sizeof(min-ltree)` ≈ 85M elements per array. Per element, the callback cost varies:
  - `ltree_isparent`: O(min(numlevel_a, numlevel_b)) — fast.
  - `ltq_regex`: **O(exponential in worst case)** — see `lquery_op.c.md`. Per-element call could be very expensive.
  - `ltxtq_exec`: O(query_size × ltree_levels) — moderate.
- **`_lt_q_regex` is the worst case**: `num_lqueries × num_ltrees × per-call-cost`. With both arrays at 85M elements and a pathological lquery, **cumulative cost is unbounded for practical purposes**. Mitigation: `CHECK_FOR_INTERRUPTS()` inside `checkCond` (`lquery_op.c:191`) lets cancel work, BUT only on a per-`checkCond` basis; `array_iterator` has no `CHECK_FOR_INTERRUPTS()` in its loop (line 54-66). Net: cancellable but slow.
- **No per-array element-count cap**: same as `_ltree_gist.c.md`. A 1-GB `ltree[]` is legal input.
- **`array_contains_nulls` + `ARR_NDIM > 1` checks**: defend against NULL injection and >1-dim arrays. Multidim could in principle cause `NEXTVAL` to wander off the end of `ARR_DATA_PTR` because the array iteration assumes flat layout. Both hard-errors. `[verified-by-code]`
- **`array_iterator` returns ltree* into the input array**: `*found = item` (line 61) is a pointer INTO the input array's data region. The extract variants then `palloc + memcpy(item, found, VARSIZE(found))` (e.g. lines 215-216). Critical: the input array is held alive by `PG_GETARG_ARRAYTYPE_P` until the function returns; the extract calls `PG_FREE_IF_COPY(la, 0)` AFTER the palloc-copy at lines 218-219. Correct ordering. `[verified-by-code]`
- **`DirectFunctionCall2` for `_*_r_*` reverse variants**: the swapped-arg dispatch is a thin wrapper. No DoS or correctness boundary.

## Cross-references

- `source/contrib/ltree/ltree_op.c:236,248,487` — `ltree_isparent`, `ltree_risparent`, `lca_inner`.
- `source/contrib/ltree/lquery_op.c:263` — `ltq_regex` (the matcher with exponential backtracking class).
- `source/contrib/ltree/ltxtquery_op.c:82` — `ltxtq_exec`.
- `source/contrib/ltree/_ltree_gist.c` — GiST opclass for `ltree[]`.
- `source/src/include/utils/array.h` — `ARR_NDIM`, `ARR_DIMS`, `ARR_DATA_PTR`, `ArrayGetNItems`, `array_contains_nulls`.

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `array_iterator` has no `CHECK_FOR_INTERRUPTS()` in its loop (lines 54-66). Per-element callbacks (`ltq_regex`) do, but the outer loop doesn't add its own. So cancellation reaches into the matcher's inner loop but only fires when control returns from there. With many small arrays it works; with one big array of pathological lqueries it's coarse. (nit — partially mitigated by callback-internal checks)] — `source/contrib/ltree/_ltree_op.c:54-66`.
- [ISSUE-security: `_lt_q_regex` (line 134) is the worst-case cost site: `num_lqueries × num_ltrees × per-call-cost`. No interrupt check between iterations of the outer `num--` loop (line 152-161). With a pathological lquery, can run for many seconds per element. (likely — see `lquery_op.c.md` headline)] — `source/contrib/ltree/_ltree_op.c:152-161`.
- [ISSUE-correctness: `_lca` (line 292) builds the `a[]` pointer array by decrementing `num` (lines 311-315): `a[num] = item; item = NEXTVAL(item);`. The first iteration stores the FIRST item at `a[num-1]` (the highest index), the second at `a[num-2]`, etc. **The order is reversed.** `lca_inner` (`ltree_op.c:525`) doesn't care about order — it computes a commutative operation. So the result is correct. But this is non-obvious; a comment or a forward loop would be clearer. (nit)] — `source/contrib/ltree/_ltree_op.c:311-316`.
- [ISSUE-cost: `array_iterator`'s `DirectFunctionCall2` (line 56) carries per-call FunctionCallInfoBaseData setup overhead. For an 85M-element array, that's 85M `DirectFunctionCall2` invocations. Comparable to any array-iteration pattern in PG, no specific bug. (verification only)] — `source/contrib/ltree/_ltree_op.c:54-66`.
- [ISSUE-correctness: `_ltree_extract_isparent` (line 200) — comment is missing. The function returns NULL when no match (`PG_RETURN_NULL` at line 212), else palloc-copies the found element. The behavior is documented in the SQL extension but not at the C function. (nit)] — `source/contrib/ltree/_ltree_op.c:200-221`.
- [ISSUE-API-shape: `_lca` and `lca` (`ltree_op.c:562`) are two different LCA entry points: `lca` is variadic (up to FUNC_MAX_ARGS scalar `ltree` args), `_lca` takes an `ltree[]`. Both ultimately call `lca_inner`. Consistent. (verification only)] — `source/contrib/ltree/_ltree_op.c:292-326`.
