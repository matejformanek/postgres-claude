# hstore_gin.c

## One-line summary

GIN opclass (`gin_hstore_ops`) for hstore: indexes both keys and values as
flagged text items (`K`<key>, `V`<value>, `N`<empty>) and implements the
GIN extract/query/consistent triad for the four hstore strategy numbers
(`@>` Contains, `?` Exists, `?|` ExistsAny, `?&` ExistsAll).

Source pin: `4b0bf0788b0`.

## Public API / entry points

- `gin_extract_hstore(hstore, *nentries) -> Datum*` — emits `2*count`
  flagged text items (`hstore_gin.c:43-77`) [verified-by-code].
- `gin_extract_hstore_query(query, *nentries, strategy, ..., *searchMode)
  -> Datum*` — strategy-specific query extractor
  (`hstore_gin.c:81-146`) [verified-by-code].
- `gin_consistent_hstore(check[], strategy, query, nkeys, extra, *recheck,
  ...) -> bool` — combines per-key matches into the final answer
  (`hstore_gin.c:150-212`) [verified-by-code].

## Key invariants

- Storage scheme uses a 1-byte flag prefix on every indexable text:
  `KEYFLAG='K'`, `VALFLAG='V'`, `NULLFLAG='N'` (`hstore_gin.c:20-22`)
  [verified-by-code]. Comment notes: "As of 9.1 it might be better to
  store null values as nulls, but we'll keep it this way for on-disk
  compatibility" (`hstore_gin.c:15-19`) [from-comment] — this is an
  on-disk format lock-in.
- `nentries = 2 * count` for `gin_extract_hstore` (every key + every value
  becomes an item) (`hstore_gin.c:54`) [verified-by-code].
- Contains is INEXACT — `gin_consistent_hstore` sets `*recheck = true` on
  the Contains path (`hstore_gin.c:166-182`) [verified-by-code] because
  the index cannot distinguish which key a value goes with.
- Exists / ExistsAny / ExistsAll are EXACT — `*recheck = false`
  (`hstore_gin.c:186, 193, 198`) [verified-by-code].
- Empty Contains query (`@> '{}'::hstore`) triggers a full index scan via
  `GIN_SEARCH_MODE_ALL` (`hstore_gin.c:96-98`) [verified-by-code].
- Empty ExistsAll triggers full scan (`hstore_gin.c:136-137`)
  [verified-by-code] — degenerate case "all of nothing is everything".

## Notable internals

### `makeitem` (`hstore_gin.c:27-41`) [verified-by-code]

Allocates `VARHDRSZ + len + 1` bytes; sets the flag byte at `VARDATA(item)`,
then memcpy's the key/value bytes after it. So an item for `KEYFLAG` is
`[varhdr][K][key bytes...]`. Note: `len + 1` is the only place where +1
matters; the 1 is for the flag byte itself, not a null terminator.

### Query extractor strategy dispatch

- `HStoreContainsStrategyNumber (7)`: directly recurses via
  `DirectFunctionCall2(gin_extract_hstore, ...)` to extract both K and V
  items from the query hstore. NULL return ⇒ full index scan
  (`hstore_gin.c:89-99`) [verified-by-code].
- `HStoreExistsStrategyNumber (9)`: single text query, one K-flagged item
  emitted (`hstore_gin.c:100-109`) [verified-by-code].
- `HStoreExistsAnyStrategyNumber (10)` / `ExistsAll (11)`: text-array
  query, deconstructed to one K-flagged item per non-null array element
  (`hstore_gin.c:110-138`) [verified-by-code]. Null array elements are
  silently dropped (comment: "Nulls in the array are ignored, cf
  hstoreArrayToPairs").

### Consistency logic

Contains: every key MUST be present (`check[i]` true) — if any is missing,
short-circuit `false`. But `recheck=true` because the index doesn't link
keys to specific values. (`hstore_gin.c:166-182`).

ExistsAll: same all-must-be-present logic, but `recheck=false` since
existence is exact.

ExistsAny: `res = true` if every check[i] passed — wait, looking again at
`hstore_gin.c:189-194`: it just returns `res = true` unconditionally,
because GIN itself only invokes the consistent function when at least one
search key matched. `[verified-by-code]` — and that's the correct
behavior; GIN's contract is that consistent is called when there's a
candidate row to confirm.

## Trust boundary / Phase D surface

### `gin_extract_hstore_query` input from user array

When strategy is ExistsAny or ExistsAll, the query is an `ArrayType*`
deconstructed via `deconstruct_array_builtin(query, TEXTOID, ...)`. Each
array element's `VARSIZE - VARHDRSZ` is the key length. No bounds check
beyond what `text` provides — but `text` doesn't enforce hstore's
`HSTORE_MAX_KEY_LEN`. The flag-prefixed text item passed to GIN can
theoretically be `1 + 2^30` bytes (any text input length). GIN's per-item
size cap (page-fit) ultimately kills oversize items with
`index row size XX exceeds maximum 8191 ...` — but the failure is
deferred to GIN insert / search rather than caught at the extractor.
`[ISSUE-defense-in-depth: extract_hstore_query does not bound query key
length; GIN's index-key-size limit is the only backstop (nit)]`.

### Memory bound on extract

`gin_extract_hstore` palloc's `sizeof(Datum) * 2 * count`
(`hstore_gin.c:56`). The HStore was validated by `hstoreUpgrade`, so
`count ≤ ~128M`. At 8 bytes per Datum that's ~2 GB, but `MaxAllocSize`
clamps both palloc and the source hstore's actual size — so the
practical ceiling is whatever the source hstore was, times O(count)
makeitems. Each makeitem is `VARHDRSZ + keylen + 1 + palloc overhead`.
Should be fine.

### Null-key in array silently dropped

`hstore_gin.c:127-129`: `if (key_nulls[i]) continue;` — but the comment
admits this matches `hstoreArrayToPairs`. The decremented `j` count means
`*nentries = j` (line 134) reflects only non-null keys. ExistsAll with
`{a, NULL}::text[]` would silently become ExistsAll with `{a}`, NOT a
type-mismatch error. `[ISSUE-api-shape: NULL elements in
ExistsAny/ExistsAll arrays silently ignored; no errror or warning (nit)]`.

### KEYFLAG/VALFLAG collisions

The 1-byte prefix scheme means a key whose first byte is `K`, `V`, or `N`
indistinguishable from a value byte sequence whose first byte is also
`K`... wait, no, because the flag is a SEPARATE byte at the start of the
text item, BEFORE the original key/value bytes. Re-reading `makeitem`:
the flag byte is at `VARDATA(item)`, the original bytes start at
`VARDATA(item) + 1`. So `key='K_foo'` becomes item `[K][K][_][f][o][o]`,
vs `value='K_foo'` becomes `[V][K][_][f][o][o]` — distinguishable. OK,
no collision.

But: GIN's btree-of-items internal comparator on TEXTOID compares the
whole prefixed string, so the K/V/N separation is intentional ordering.
Phase D angle: a value that starts with `N` (e.g. `'NULL'`) sorts adjacent
to actual nulls in the index — no security issue, just an indexing-
efficiency curiosity.

## Cross-references

- `access/gin.h` — GIN_SEARCH_MODE_ALL constant.
- `access/stratnum.h` — strategy number conventions.
- `hstore.h.md` — strategy numbers (Contains=7, Exists=9, etc.).
- A12 contrib security bundle — similar inexact-index-with-recheck
  pattern in pg_trgm, btree_gin.
- `hstore_gist.c.md` — sibling GiST opclass; lossier but supports more
  queries.

<!-- issues:auto:begin -->
- [Issue register — `hstore`](../../../issues/hstore.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-defense-in-depth: extract_hstore_query does not bound query
  key length; GIN's index-key-size limit is the only backstop (nit)]`
- `[ISSUE-api-shape: NULL elements in ExistsAny/ExistsAll text arrays are
  silently dropped without warning (nit)]`
- `[ISSUE-documentation: comment hstore_gin.c:15-19 acknowledges the
  null-as-flag scheme is sub-optimal "As of 9.1" — the comment is now
  ancient and the on-disk-compat lock-in deserves a clearer note (nit)]`
- `[ISSUE-correctness: gin_extract_hstore_query Contains path forwards
  NULL entries pointer-as-return; the call site sees entries == NULL
  meaning the empty-query full-scan branch — the comment "if (entries ==
  NULL)" relies on gin_extract_hstore returning NULL for count==0, which
  it does because palloc is gated by `if (count) entries = palloc(...)`
  (hstore_gin.c:55-56). Subtle but correct (nit)]`
