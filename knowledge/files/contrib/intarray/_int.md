# _int.h + _int_tool.c

Covers `source/contrib/intarray/_int.h` (187 lines) and `source/contrib/intarray/_int_tool.c` (397 lines).

## One-line summary

Shared header and utility code for the `intarray` contrib module: declares `QUERYTYPE`/`ITEM` (the parsed `query_int` polish-notation tree), `GISTTYPE` (signature-tree key), macros for signature bit-manipulation, and the sort/union/intersect/contains/overlap primitives that operate on sorted-unique `int4[]`.

## Public API / entry points

- Macros for sorted-int4-array manipulation: `ARRPTR`, `ARRNELEMS`, `CHECKARRVALID`, `ARRISEMPTY`, `SORT`, `PREPAREARR`, `QSORT` — `source/contrib/intarray/_int.h:26-46,180-185` [verified-by-code]
- Signature-tree bit macros: `GETBYTE`, `GETBITBYTE`, `CLRBIT`, `SETBIT`, `GETBIT`, `HASHVAL(val,siglen)=val % SIGLENBIT(siglen)`, `HASH(sign,val,siglen)=SETBIT(sign, HASHVAL(...))` — `source/contrib/intarray/_int.h:74-81` [verified-by-code]
- `QUERYTYPE`/`ITEM` polish-notation tree types — `source/contrib/intarray/_int.h:140-152` [verified-by-code]
- `BooleanSearchStrategy = 20` — `source/contrib/intarray/_int.h:134` [verified-by-code]
- Utility functions (defined in `_int_tool.c`):
  - `inner_int_contains(a,b)` — `source/contrib/intarray/_int_tool.c:14-46`
  - `inner_int_overlap(a,b)` — `source/contrib/intarray/_int_tool.c:49-76`
  - `inner_int_union(a,b)` — `source/contrib/intarray/_int_tool.c:78-133`
  - `inner_int_inter(a,b)` — `source/contrib/intarray/_int_tool.c:135-181`
  - `isort` (generated via `lib/sort_template.h`) — `source/contrib/intarray/_int_tool.c:214-220`
  - `new_intArrayType(num)`, `resize_intArrayType`, `copy_intArrayType` — `source/contrib/intarray/_int_tool.c:223-291`
  - `internal_size(a,len)` — sum of range widths for compressed key — `source/contrib/intarray/_int_tool.c:294-309`
  - `_int_unique(r)` — runs `qunique_arg` in place over a sorted array — `source/contrib/intarray/_int_tool.c:312-322`
  - `gensign(sign,a,len,siglen)` — `source/contrib/intarray/_int_tool.c:324-335`

## Key invariants

- `CHECKARRVALID` rejects NULL elements via `ARR_HASNULL && array_contains_nulls` (NULL-element arrays raise `ERRCODE_NULL_VALUE_NOT_ALLOWED`) — `source/contrib/intarray/_int.h:30-36` [verified-by-code]
- All operators in `_int_tool.c` (`inner_int_contains/overlap/union/inter`) assume **sorted, unique-ified** inputs — `source/contrib/intarray/_int_tool.c:13,48,82-84` [from-comment]
- Signature hash uses **modulo siglen**, deterministic across hosts: `HASHVAL(val) = ((unsigned int) val) % SIGLENBIT(siglen)` — `source/contrib/intarray/_int.h:80` [verified-by-code]
- `internal_size` returns -1 on int32 overflow (sum of compressed ranges exceeds `INT_MAX`) — `source/contrib/intarray/_int_tool.c:306-308` [verified-by-code]
- `_int_unique` uses `qunique_arg` ascending comparator; arrays must already be sorted before this call — `source/contrib/intarray/_int_tool.c:312-322` [verified-by-code]
- Default GiST `numranges` = 100, max = `(GISTMaxIndexKeySize-VARHDRSZ)/(2*sizeof(int32))` — `source/contrib/intarray/_int.h:11-13` [verified-by-code]
- Default `intbig` siglen = 63*4 = 252 bytes (2016 bits), max = `GISTMaxIndexKeySize` (≈8 KB) — `source/contrib/intarray/_int.h:62-63` [verified-by-code]

## Notable internals

- `QUERYTYPE` is varlena and uses a postfix (reverse-polish) `ITEM[]` layout; `ITEM.left` is a 16-bit signed offset to the left operand (binary ops) or -1 (unary `!`) — `source/contrib/intarray/_int.h:140-152` [from-comment + verified-by-code]
- `QUERYTYPEMAXITEMS = (MaxAllocSize - HDRSIZEQT) / sizeof(ITEM)` (≈134M items on 64-bit with 8-byte `ITEM`) — `source/contrib/intarray/_int.h:156` [verified-by-code]
- `ALLISTRUE` flag short-circuits signature comparison when every bit is set; size collapses to `GTHDRSIZE` only — `source/contrib/intarray/_int.h:100-105` [verified-by-code]
- `new_intArrayType(0)` returns a zero-dimensional empty array (`construct_empty_array`); ≥1-element arrays are 1-D with `ARR_LBOUND[0]=1` — `source/contrib/intarray/_int_tool.c:230-249` [verified-by-code]
- `inner_int_union` over-allocates `na+nb` and `resize`s after merging; final dedupe via `_int_unique` — `source/contrib/intarray/_int_tool.c:103-131` [verified-by-code]

## Trust boundary / Phase D surface

- **Hash collisions in `gensign`** — `HASHVAL(val,siglen) = ((unsigned int) val) % (siglen * 8)`. With default siglen=252 → 2016 bits, a malicious indexer can construct values that all hash to the same bit, making `intbig` signatures degenerate (effectively useless filtering, full recheck on every query). Negative `int32` values map to large unsigned then modulo — no special handling. Same risk in `_int_gist`'s compressed-range key (no hashing there, but range merging is deterministic and inputs influence sparseness — see `_int_gist.md`). [verified-by-code] `source/contrib/intarray/_int.h:80`, `source/contrib/intarray/_int_tool.c:324-335` [ISSUE-COLLISION: deterministic mod-prime-free hash makes intbig signatures spoofable for false-positive amplification (Med)]
- **`internal_size` overflow path**: when the sum of compressed ranges exceeds `INT32_MAX`, returns -1, which callers must check or they reject by erroring. Both call sites (`_int_gist.c:274-277,336-339`) do check, but a future caller forgetting the `< 0` test would treat -1 as a tiny valid size. [verified-by-code] `source/contrib/intarray/_int_tool.c:294-309` [ISSUE-API: `internal_size` returns a magic -1 sentinel rather than out-param + bool; easy to misuse (Low)]
- **`inner_int_union` allocates `na+nb` ints, no MaxAllocSize check up front**: caller must already have bounded inputs. For arbitrary user-supplied `int[]` arguments passed to the `|` (union) operator, two 0.5 GB arrays would attempt a 1 GB palloc — palloc throws ereport so no UAF, just OOM-DoS. — `source/contrib/intarray/_int_tool.c:103-104` [verified-by-code] [ISSUE-DOS: no upfront size cap on union/intersect palloc; backend OOMs on adversarial input arrays (Low — palloc rejects cleanly)]
- **`new_intArrayType` integer-overflow**: `nbytes = ARR_OVERHEAD_NONULLS(1) + sizeof(int) * num`. For `num ≈ INT32_MAX/4`, `sizeof(int)*num` wraps int. The macro callers all pass either `ARRNELEMS()` of a validated array or a sum of two, so practically bounded by `MaxAllocSize/sizeof(int)`, but no explicit check. `source/contrib/intarray/_int_tool.c:237` [verified-by-code] [ISSUE-OVERFLOW: nbytes computation in new_intArrayType lacks explicit overflow guard (Low)]

## Cross-references

- `access/gist/*` — generic GiST framework that drives `_int_gist.c`/`_intbig_gist.c`
- `access/gin/*` — drives `_int_gin.c`
- `lib/sort_template.h`, `lib/qunique.h` — generic sort/unique primitives used here
- `utils/array.h` — `ArrayType` macros (`ARR_NDIM`, `ARR_DIMS`, `ARR_DATA_PTR`, `construct_empty_array`)
- A11 contrib top-4 (postgres_fdw / dblink) — comparable trust boundary around composite-type echo

## Issues spotted

- [ISSUE-COLLISION: signature-tree mod hash is trivially spoofable; intbig opclass on attacker-influenced int4 columns will degenerate (Med)]
- [ISSUE-API: `internal_size` overload of -1 as overflow sentinel (Low)]
- [ISSUE-DOS: `|` / `&` (`_int_union`, `_int_inter`) over arbitrary user arrays will palloc up to `na+nb` ints with no preflight bound (Low — palloc throws)]
- [ISSUE-OVERFLOW: `new_intArrayType` size arithmetic lacks explicit `if (num > MaxAllocSize/sizeof(int)) ereport` guard (Low)]
