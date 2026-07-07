# contrib-intarray (int4[] operators + GIN/GiST opclasses)

- **Source path:** `source/contrib/intarray/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.5` (per `intarray.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

Specialized operators + index support for `int4[]` (single-
dimensional arrays of `int4`) used heavily in legacy
tag/category schemas. Provides:

- **Set operators** — containment (`@>`, `<@`), overlap
  (`&&`), union/intersection (`|`, `&`), equality.
- **Aggregation** — `icount` (cardinality), `idx`
  (find-element), `sort` / `uniq`.
- **Query language** — `query_int` type for boolean queries
  (e.g. `1 & (2 | 3)`).
- **Index opclasses** — `gin__int_ops`, `gist__int_ops`,
  `gist__intbig_ops` for fast containment-search on large
  arrays.

Most use cases have migrated to `jsonb` or proper relational
normalization; intarray remains for compatibility with
existing schemas + workloads where int4[] is the natural
data shape.

## 2. The C files

| File | LOC | What it does |
|---|---|---|
| `_int_op.c` | 436 | Set operators + helpers |
| `_int_gin.c` | 181 | GIN opclass (small arrays) |
| `_int_gist.c` | 638 | GiST opclass (small arrays) |
| `_intbig_gist.c` | 597 | GiST opclass with signature-based compression (large arrays) |
| `_int_bool.c` | 715 | query_int boolean evaluator |
| `_int_tool.c` | 397 | sorting + uniq helpers |
| `_int_selfuncs.c` | 355 | Selectivity estimators for the planner |

[verified-by-code `wc -l source/contrib/intarray/*.c`]

The split between `_int_gist` (small arrays, exact-set
representation) and `_intbig_gist` (large arrays, signature-
based) is the canonical example of "two opclasses per use
case" — pick by array size at index creation.

## 3. SQL surface — operators

| Operator | Meaning |
|---|---|
| `arr1 @> arr2` | arr1 contains arr2 |
| `arr1 <@ arr2` | arr2 contains arr1 |
| `arr1 && arr2` | overlap (any common element) |
| `arr1 = arr2` | equal as sets |
| `arr \| arr` | union |
| `arr & arr` | intersection |
| `arr - arr` | difference |
| `arr @@ query_int` | matches boolean query |

[verified-by-code `_int_op.c:13-19` for the C entry points]

The set-semantics (vs array-semantics) matters: `arr1 = arr2`
true if same elements regardless of order or duplicates.
That's why `intarray` and the core `=` operator on `int[]`
produce different results.

## 4. SQL surface — functions

| Function | Meaning |
|---|---|
| `icount(int[])` | Number of elements |
| `idx(int[], int)` | First-occurrence index (1-based) |
| `sort(int[])` / `sort_asc` / `sort_desc` | Sorted |
| `uniq(int[])` | Deduplicated (requires sorted input) |
| `subarray(int[], offset, count)` | Slice |
| `intarray_push_elem` | Append |
| `intset(int)` | Single-element array |

[verified-by-code `_int_op.c:168-176`]

`uniq` requires sorted input — wrap with `sort()` if not
already. The combination `uniq(sort(arr))` is a common idiom.

## 5. The query_int boolean type

Allows queries like:

```sql
SELECT * FROM tags WHERE arr @@ '1&(2|3)'::query_int;
```

Match: array contains 1 AND (2 OR 3). Index-supported on
GIN / GiST. Parser + evaluator in `_int_bool.c`. Supports `&`,
`|`, `!` operators.

## 6. The two GiST opclass strategies

### `gist__int_ops` — exact

Stores the array verbatim at each index level. Fast for small
arrays (≤ ~100 elements) but indexed entries grow O(N).

### `gist__intbig_ops` — signature compression

Replaces large arrays with a **bit signature** at internal
nodes. False positives possible (rechecked at leaf), but
index size is bounded regardless of array size. Use for
arrays > 100 elements.

Pick at CREATE INDEX time:

```sql
CREATE INDEX ON tags USING gist (arr gist__intbig_ops);
```

## 7. The GIN opclass

`gin__int_ops` (the default for GIN on int[]) stores each
element separately in the inverted index. Fast for "find
arrays containing element X" queries.

GIN is generally **faster than GiST for containment** on
write-heavy workloads, but GiST's signature-based opclass
beats GIN on very-large arrays.

## 8. Selectivity estimation

`_int_selfuncs.c` provides selectivity estimators for the set
operators. The planner uses these to choose between index
scans, bitmap scans, and seq scans on intarray-typed
columns. Without estimators, planner would default to
"unknown selectivity" and possibly choose seq scan.

## 9. Production-use guidance

- **For new schemas**, consider `jsonb` instead — it's more
  general, has the same array semantics, and is the
  canonical PG modern approach.
- **For existing intarray schemas**, the extension is
  production-quality; no plans to deprecate.
- **GIN vs GiST**: GIN for write-once-read-many (read fast,
  insert slow). GiST for write-heavy.
- **Index-size matters**: signature opclass for arrays >100
  elements.

## 10. Invariants

- **[INV-1]** `int4[]` only; not portable to other element
  types.
- **[INV-2]** Set semantics: equal arrays regardless of
  order/duplicates.
- **[INV-3]** `uniq` requires sorted input.
- **[INV-4]** Signature-based GiST is approximate; recheck
  at leaf for correctness.
- **[INV-5]** Trusted extension (CREATE EXTENSION without
  superuser).

## 11. Useful greps

- All operators:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/intarray/_int_op.c`
- GIN entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/intarray/_int_gin.c`
- GiST signature compression:
  `grep -n 'g_int_compress\|g_intbig_compress' source/contrib/intarray/_int*gist.c | head -10`

## 12. Cross-references

- `knowledge/subsystems/access-nbtree.md` — companion AM;
  but intarray uses GIN/GiST, not nbtree.
- `knowledge/subsystems/contrib-btree_gist.md` — sibling
  contrib; mixes btree + gist for scalar types.
- `knowledge/subsystems/contrib-hstore.md` — sibling
  key-value contrib; mostly replaced by jsonb.
- `.claude/skills/access-method-apis.md` — index-AM
  contracts.
- `source/contrib/intarray/` — implementation directory.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**8 files.**

| File |
|---|
| [`contrib/intarray/_int`](../files/contrib/intarray/_int.md) |
| [`contrib/intarray/_int_bool`](../files/contrib/intarray/_int_bool.md) |
| [`contrib/intarray/_int_gin`](../files/contrib/intarray/_int_gin.md) |
| [`contrib/intarray/_int_gist`](../files/contrib/intarray/_int_gist.md) |
| [`contrib/intarray/_int_op`](../files/contrib/intarray/_int_op.md) |
| [`contrib/intarray/_int_selfuncs`](../files/contrib/intarray/_int_selfuncs.md) |
| [`contrib/intarray/_int_tool.c`](../files/contrib/intarray/_int_tool.c.md) |
| [`contrib/intarray/_intbig_gist`](../files/contrib/intarray/_intbig_gist.md) |

<!-- /files-owned:auto -->
