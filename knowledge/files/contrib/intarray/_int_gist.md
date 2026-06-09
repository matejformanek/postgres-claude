# _int_gist.c

`source/contrib/intarray/_int_gist.c` (638 lines).

## One-line summary

`gist__int_ops` GiST opclass for `int4[]`: stores **range-compressed** sorted int arrays as leaf/internal keys (alternating `[start,end]` pairs once they exceed `2*num_ranges` elements), implements consistent/union/compress/decompress/penalty/picksplit/same/options.

## Public API / entry points

- `g_int_consistent(entry, query, strategy, subtype, recheck)` — `source/contrib/intarray/_int_gist.c:30,46-121` [verified-by-code]
- `g_int_union(entryvec, *size)` — `source/contrib/intarray/_int_gist.c:31,123-158`
- `g_int_compress(entry)` — `source/contrib/intarray/_int_gist.c:32,163-287`
- `g_int_decompress(entry)` — `source/contrib/intarray/_int_gist.c:33,289-359`
- `g_int_penalty(orig, new, *result)` — `source/contrib/intarray/_int_gist.c:34,364-382`
- `g_int_picksplit(entryvec, splitvec)` — Guttman poly-time split — `source/contrib/intarray/_int_gist.c:35,442-624`
- `g_int_same(a,b,*result)` — `source/contrib/intarray/_int_gist.c:36,386-417`
- `g_int_options(relopts)` — `numranges` reloption — `source/contrib/intarray/_int_gist.c:37,626-638`

## Key invariants

- Leaf keys are plain sorted-unique `int4[]`; internal keys are RANGE-encoded as `[s1,e1,s2,e2,...]` pairs once length ≥ `2 * num_ranges` — `source/contrib/intarray/_int_gist.c:184-188,211-287` [verified-by-code]
- `MAXNUMELTS` = `Min(MaxAllocSize/sizeof(Datum), (MaxAllocSize-ARR_OVERHEAD_NONULLS(1))/sizeof(int)) / 2` — caps expansion of a compressed key — `source/contrib/intarray/_int_gist.c:24` [verified-by-code]
- Leaf-side `g_int_compress` rejects arrays with `≥ 2*num_ranges` elements at insert time → "use gist__intbig_ops opclass instead" — `source/contrib/intarray/_int_gist.c:184-188`
- `g_int_decompress` rejects too-sparse compressed key (`internal_size > MAXNUMELTS`) — `source/contrib/intarray/_int_gist.c:336-339`
- `recheck` is true only for `RTSameStrategyNumber`; consistent is exact for `&&`, `@>`, and `@@` on signature-trees handled in `_intbig_gist.c` — `source/contrib/intarray/_int_gist.c:59,75-118` [verified-by-code]
- `<@` (contained-by) branch is unreachable since intarray 1.4; kept for old SQL definition compatibility — `source/contrib/intarray/_int_gist.c:99-114` [from-comment]

## Notable internals

- **Range compression** (`g_int_compress`): walks the sorted array right-to-left, merging consecutive ints into `[start,end]` ranges, but only as many as needed (`lenr = len - num_ranges` is the budget). Then if still too many ranges, greedily merges the smallest gap pair until length ≤ `num_ranges*2`. `int64` is used in the gap comparison to avoid signed overflow — `source/contrib/intarray/_int_gist.c:212-268` [verified-by-code]
- **Decompression** expands each `[s,e]` back to `e-s+1` ints, using `int64 j` inside the loop because `e` can be `INT_MAX` (otherwise `for(j=...; j<=INT_MAX; j++)` would never terminate) — `source/contrib/intarray/_int_gist.c:347` [verified-by-code + from-comment]
- **Penalty** = size-of-union(orig, new) − size-of-orig, both via `rt__int_size = (float) ARRNELEMS` — `source/contrib/intarray/_int_gist.c:374-378`
- **PickSplit** = Guttman quadratic-cost: pick the two entries with max wasted space, then iteratively assign each remaining entry to the side that grows least. `WISH_F(nl, nr, 0.01)` is a tie-breaker biased toward balance — `source/contrib/intarray/_int_gist.c:442-624`
- **`g_int_union` is naive**: copies every input entry into a single big array, then sorts and uniqs. O((Σnᵢ)·log(Σnᵢ)) per page. — `source/contrib/intarray/_int_gist.c:123-158`
- `g_int_same` compares element-by-element with no sorting — relies on the invariant that both leafkeys are already sorted/unique — `source/contrib/intarray/_int_gist.c:399-414`
- `numranges` default 100, allowed range `[1, G_INT_NUMRANGES_MAX]` ≈ `[1, ~1000]` (depends on `GISTMaxIndexKeySize`) — `source/contrib/intarray/_int_gist.c:632-636`

## Trust boundary / Phase D surface

- **`_intbig_gist` escape hatch is the only path for big arrays** — once any `int4[]` value has ≥ `2*num_ranges` (default 200) elements, `g_int_compress` throws `ERRCODE_PROGRAM_LIMIT_EXCEEDED`. An attacker who can `INSERT INTO t VALUES (array_of_201_ints)` into a GiST-indexed column triggers a hard error — no silent loss of data, but DoS for the INSERT path. — `source/contrib/intarray/_int_gist.c:184-188` [verified-by-code]
- **Sparse data DoS** — `internal_size` over a compressed key can return > `MAXNUMELTS` (≈ 256M), at which point `g_int_decompress` throws `ERRCODE_PROGRAM_LIMIT_EXCEEDED`. Reachable by inserting arrays that, after compression to `num_ranges` pairs, still span billions of integers (e.g., `{1, INT_MAX}`) — but `internal_size` itself returns -1 on int32 overflow, also caught (`< 0`). Result: clean error, not crash. — `source/contrib/intarray/_int_gist.c:336-339`
- **`g_int_union` palloc for big pages** — each GiST page union sums `ΣARRNELEMS(entries)`. Worst case 100 entries × ~200 ints = 20k ints (small). But if `numranges` is set very high and compressed keys decompressed first, this can grow. `new_intArrayType(totlen)` and `_int_unique` both depend on `totlen` fitting `MaxAllocSize/4`. — `source/contrib/intarray/_int_gist.c:130-152` — palloc errors cleanly; not an exploit, but a DoS via OOM if `numranges` mis-tuned.
- **`g_int_picksplit` is O(maxoff²)** for the seed-pair selection (every pair compared). For a default GiST page (~120 tuples), that's 7200 pair comparisons each doing union+inter+free — not a vector for an attacker (they need page-fan-out to be huge), but inserting one row triggers split with at most page-tuple count. Bounded by page size. [verified-by-code] `source/contrib/intarray/_int_gist.c:485-515`
- **Selectivity not affected by GiST encoding**: `_int_selfuncs.c` reads `pg_statistic` MCE, not the index; so attacker-controlled values **can** influence the planner via ANALYZE-collected MCEs but not via GiST keys — handled in `_int_selfuncs.md`.
- **No signature collision here** (range encoding is exact down to integer level; false positives only on the lossy ALL_FALSE/internal range overlaps, and the `recheck` flag handles `=`). The signature-tree variant with hash collisions is `_intbig_gist.c` — see that doc.

## Cross-references

- `_int_tool.c` — provides `inner_int_overlap`, `inner_int_contains`, `inner_int_union`, `inner_int_inter`, `_int_unique`, `new_intArrayType`, `resize_intArrayType`, `internal_size`
- `_int_bool.c` — `execconsistent` for `@@` Boolean queries on exact leaf keys
- `_intbig_gist.c` — the "big" variant used when arrays exceed `2*num_ranges`
- `access/gist/*` — `GistEntryVector`, `GIST_SPLITVEC`, `GIST_LEAF`, generic split framework
- `access/reloptions.h` — `init_local_reloptions`, `add_local_int_reloption`

## Issues spotted

- [ISSUE-DOS: inserting >`2*num_ranges` elements into a `gist__int_ops`-indexed column hard-errors INSERT path; attacker can write-DoS by including a 201-element array (Low — explicit error)]
- [ISSUE-COMPLEXITY: pickSplit O(maxoff²) over `inner_int_union/inter`; not a useful attack vector but a perf cliff if page fanout grows (Info)]
- [ISSUE-UNREACHABLE: `<@` branch in `g_int_consistent:96-115` is documented as dead since intarray 1.4 — candidate for deletion (Cleanup)]
