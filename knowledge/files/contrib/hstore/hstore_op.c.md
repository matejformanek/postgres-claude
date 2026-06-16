# hstore_op.c

## One-line summary

Operators and helper functions for hstore: lookup (`hstoreFindKey`,
`hstore_fetchval` `->`, `hstore_exists` `?`, `?|`, `?&`), modification
(`hstore_delete`, `hstore_delete_array`, `hstore_delete_hstore`,
`hstore_concat` `||`), conversion (`hstore_akeys`, `hstore_avals`,
`hstore_to_array`, `hstore_to_matrix`, `hstore_slice_to_array`,
`hstore_slice_to_hstore`), set-returning functions (`hstore_skeys`,
`hstore_svals`, `hstore_each`), containment (`hstore_contains` `@>`,
`hstore_contained` `<@`), and btree/hash support
(`hstore_cmp`/`_eq`/`_ne`/`_gt`/`_ge`/`_lt`/`_le`, `hstore_hash`,
`hstore_hash_extended`).

Source pin: `4b0bf0788b0`.

## Public API / entry points

### Internal helpers

- `hstoreFindKey(HStore*, *lowbound, char *key, int keylen) -> int`
  (`hstore_op.c:35-70`) [verified-by-code] — binary search over the
  sorted-by-(keylen, key) entries; optional lowbound for amortized scans
  across sorted query keys.
- `hstoreArrayToPairs(ArrayType*, *npairs) -> Pairs*` —
  deconstruct + dedup a text array into a sorted Pairs array
  (`hstore_op.c:72-123`) [verified-by-code]. Guards
  `key_count > MaxAllocSize / sizeof(Pairs)`.

### SQL-callable lookups

- `hstore_fetchval(hstore, text) -> text` (the `->` operator)
  (`hstore_op.c:126-144`) — returns NULL on miss or null value.
- `hstore_exists(hstore, text) -> bool` (`?`) (`hstore_op.c:147-157`).
- `hstore_exists_any(hstore, text[]) -> bool` (`?|`)
  (`hstore_op.c:160-191`).
- `hstore_exists_all(hstore, text[]) -> bool` (`?&`)
  (`hstore_op.c:194-225`).
- `hstore_defined(hstore, text) -> bool`
  (`hstore_op.c:228-240`) — true iff key exists AND value is non-null.

### Modifications

- `hstore_delete(hstore, text) -> hstore` (`-`)
  (`hstore_op.c:243-287`).
- `hstore_delete_array(hstore, text[]) -> hstore` (`-`)
  (`hstore_op.c:290-366`).
- `hstore_delete_hstore(hstore, hstore) -> hstore` (`-`)
  (`hstore_op.c:369-466`).
- `hstore_concat(hstore, hstore) -> hstore` (`||`)
  (`hstore_op.c:469-564`).

### Conversions

- `hstore_slice_to_array(hstore, text[]) -> text[]` — array of values
  in the same shape as the input array (`hstore_op.c:567-625`).
- `hstore_slice_to_hstore(hstore, text[]) -> hstore` — sub-hstore
  restricted to listed keys (`hstore_op.c:628-687`).
- `hstore_akeys(hstore) -> text[]` (`hstore_op.c:690-721`).
- `hstore_avals(hstore) -> text[]` (`hstore_op.c:724-768`) — null
  values preserved.
- `hstore_to_array_internal` (static) + `hstore_to_array` /
  `hstore_to_matrix` (`hstore_op.c:771-838`) — flat 1-D
  (key,val,key,val,...) or 2-D matrix.

### SRFs (set-returning)

- `hstore_skeys(hstore)` (`hstore_op.c:878-909`).
- `hstore_svals(hstore)` (`hstore_op.c:912-957`) — special ugly path
  for null-value emission via `rsi->isDone = ExprMultipleResult`.
- `hstore_each(hstore)` (`hstore_op.c:1019-1071`) — emits records.
- `setup_firstcall` (static, `hstore_op.c:849-875`) — copies hstore into
  the multicall mem context.

### Containment

- `hstore_contains(hstore, hstore) -> bool` (`@>`)
  (`hstore_op.c:960-1005`).
- `hstore_contained(hstore, hstore) -> bool` (`<@`) — calls
  `hstore_contains` with args swapped via `DirectFunctionCall2`
  (`hstore_op.c:1008-1016`).

### Comparison and hashing

- `hstore_cmp(hstore, hstore) -> int4` (`hstore_op.c:1080-1158`) — btree
  three-way compare; explicit `PG_FREE_IF_COPY`.
- `hstore_eq/ne/gt/ge/lt/le` — wrappers over `hstore_cmp`
  (`hstore_op.c:1161-1225`).
- `hstore_hash(hstore) -> int4`, `hstore_hash_extended(hstore, int8) -> int8` —
  hash whole `VARDATA` blob via `hash_any` (`hstore_op.c:1228-1273`).

## Key invariants

- All multi-pair operators (concat, delete_array, delete_hstore, contains)
  exploit the (keylen, key) sort invariant to do a single linear merge
  in O(n + m) (`hstore_op.c:327-330, 408-412, 517-520` etc.)
  [verified-by-code, from-comment].
- `hstoreFindKey` returns the index `i` of the matching pair (NOT the
  entry offset — multiply by 2 for entries[]) or -1 on miss
  (`hstore_op.c:55-69`) [verified-by-code].
- `hstore_concat` overwrites s1's value with s2's for duplicate keys
  ("we take s2 for equal keys" — `hstore_op.c:519-520`) [from-comment].
- `hstore_delete_array` / `hstore_delete_hstore` produce a copy of the
  source minus the deletes; preserves source ordering implicitly because
  the source is already sorted.
- `hstore_cmp` is explicitly documented (`hstore_op.c:1075-1078`) as
  "btree sort order for hstores isn't intended to be useful; we really
  only care about equality vs non-equality" [from-comment]. It compares
  the entire string buffer first (memcmp), then breaks ties on count,
  then on per-entry endpos and null bits.
- `hstore_hash` / `hstore_hash_extended` hash the WHOLE `VARDATA` (entry
  array + string buffer); the assertion at `hstore_op.c:1242-1246`
  ensures the varlena size equals the format-required size (no slop) —
  meaning hash is stable.
- Both hash functions and `hstore_cmp` call `PG_FREE_IF_COPY` — the
  comment at `hstore_op.c:1152-1154` notes "this is one of the few
  places where memory needs to be explicitly freed" — a long-running
  btree/hash op would leak detoasted copies otherwise.

## Notable internals

### `hstoreFindKey` binary search

`hstore_op.c:35-70` [verified-by-code]. Classic `stopLow/stopHigh`
binary search; `lowbound` is an in/out cursor used by callers iterating
a sorted query (e.g. `hstore_exists_all`, `hstore_contains`,
`hstore_slice_to_hstore`) to start each subsequent search from where the
previous one ended. Amortized O(n + m) instead of O(m log n).

### Concat / delete merge-sort pattern

All three multi-pair modifiers use a `difference < 0 / = 0 / > 0` switch
to advance pointers and emit. For each, the over-allocation strategy is
`palloc(VARSIZE(s1) + VARSIZE(s2))` for concat or `palloc(VARSIZE(hs))`
for deletes (`hstore_op.c:251, 295, 375, 475`) — then `HS_FINALIZE`
trims the actual size at the end.

### `hstore_concat` zero-count shortcuts (`hstore_op.c:492-508`)

Both `s1count == 0` and `s2count == 0` are special-cased to a direct
`memcpy(out, ...)` of the input. **Note `HS_FIXSIZE(out, sNcount)` is
called AFTER the memcpy — so the memcpy includes the source HEntries,
and HS_FIXSIZE recomputes the varlena length from the count + last
endpos.** The intermediate `SET_VARSIZE(out, VARSIZE(s1) + VARSIZE(s2) -
HSHRDSIZE)` on line 489 is dead (overwritten by HS_FIXSIZE), although
harmless. `[ISSUE-correctness: hstore_concat early SET_VARSIZE at line
489 is dead code overwritten by HS_FIXSIZE; harmless but reduces
auditability (nit)]`.

### `hstore_contains` containment semantics

`hstore_op.c:960-1005` [verified-by-code]. For each key in template:
- Lookup in val via `hstoreFindKey` (with `lowbound` cursor optimization
  — `hstore_op.c:973, 984`).
- If found AND values are byte-equal (or both null), match continues;
  otherwise return false.
- If not found, return false.

NULL handling: an hstore with `k => NULL` contains `k => NULL` but does
NOT contain `k => 'x'` and vice versa. (`hstore_op.c:990-998`)
[verified-by-code]. This is the intended semantics for `@>`.

### `hstore_cmp` byte-comparison

`hstore_op.c:1101-1147` [verified-by-code]. Compares the FULL string
buffer first, NOT the structured (key, value) sequence. Two hstores
with the same logical content but different insertion orders (which
shouldn't happen — input always sorts — but COULD if you forge a value)
would compare differently if the string buffers differ. Since all
documented input paths sort, this is fine; but a forged hstore via
`hstoreUpgrade`'s compat path can theoretically produce a "valid"
new-format hstore whose string buffer order differs from sort order.
`[ISSUE-correctness: hstore_cmp depends on canonical (sorted) string-
buffer layout; a forged hstore that passes validation but has
non-canonical layout would compare unequal to logically-equal hstores
(maybe)]`.

### `hstore_hash` strict size check

`hstore_op.c:1242-1246` Assert that `VARSIZE(hs)` matches exactly
`CALCDATASIZE(count, lastEndPos)`. If a value has slop (per
`hstoreValidNewFormat`'s "valid=1" outcome), it gets normalized via
`HS_FIXSIZE` in `hstoreUpgrade` before reaching hash. So the assert
documents that invariant. In an assert-disabled build this is silent —
a slop'd hstore (post-upgrade, pre-fixsize) would hash a possibly
different result than a normalized one. `[ISSUE-defense-in-depth:
hstore_hash uses Assert-only validation of the canonical-size invariant;
in production builds an off-spec hstore would silently hash to a
different value than its canonical sibling, causing hash-index lookup
miss (maybe, mitigated by hstoreUpgrade)]`.

### SRF `setup_firstcall` copying

`hstore_op.c:849-875` [verified-by-code]. The hstore is `palloc`'d in
`multi_call_memory_ctx` and copied. Comment from a previous maintainer
(AG) admits "there was no explanatory comment in the original code" —
the working theory is the original Datum could be toasted and the
multicall outlives the temporary detoast context. This is correct PG-
SRF practice.

### `hstore_svals` null-value ugly path

`hstore_op.c:935-944` [verified-by-code]. Comment: "ugly ugly ugly. why
no macro for this?" — to emit a NULL row from an SRF, the code has to
manually advance `funcctx->call_cntr++` and set
`rsi->isDone = ExprMultipleResult`. Functional but a code smell.

## Trust boundary / Phase D surface

### Memory bounds in `hstore_concat`

`palloc(VARSIZE(s1) + VARSIZE(s2))` (`hstore_op.c:475`) — sum of two
1 GiB hstores would exceed MaxAllocSize and `palloc` rejects. But:
**summing TWO ~512 MB hstores into a 1 GB concat works** and produces
a result that downstream functions then operate on. Not unbounded.

### `hstore_delete_array` zero-keys quirk

`hstore_op.c:317-324`: if `nkeys == 0`, returns a copy of input via
`memcpy(out, hs, VARSIZE(hs))` then `HS_FIXSIZE`. The previous
`SET_VARSIZE(out, VARSIZE(hs))` is overwritten by `HS_FIXSIZE`. Same
dead-code pattern as `hstore_concat`. Harmless.

### `hstore_each` SRF memory growth

`setup_firstcall` copies the input hstore into multicall context once
(`hstore_op.c:858-859`). For each call, the per-call memory churn is
the `cstring_to_text_with_len` outputs (one or two text values). For an
hstore with 1M pairs, that's 1M short text allocations across the SRF
lifetime — bounded by multicall context.

### `hstore_slice_to_array` allows nulls in input array

`hstore_op.c:594-602`: a NULL key in the input array becomes `idx = -1`
which gets `out_nulls[i] = true`, `out_datums[i] = 0`. So
`slice(hs, ARRAY['a', NULL, 'b'])` returns `{val_a, NULL, val_b}`.
Different from `hstore_delete_array` which silently drops NULLs via
`hstoreArrayToPairs`. `[ISSUE-api-shape: NULL-key handling is
inconsistent across hstore_op.c — slice_to_array preserves NULL slots;
delete_array drops them; concat/contains can't see NULLs at all (nit)]`.

### `hstore_contains` for index recheck

Used by GiST/GIN as the recheck function for `@>`. The function is
self-contained (no SPI, no external state), so safe to call from index
AMs. `[verified-by-code]`.

### `hstore_hash` and `hstore_hash_extended` with PG_FREE_IF_COPY

Both call `PG_FREE_IF_COPY(hs, 0)` (`hstore_op.c:1248, 1271`)
[verified-by-code]. Required because hash functions are called many
times per index probe and a detoasted copy would otherwise leak.
`hstore_cmp` similarly. None of the OTHER functions in this file
(fetchval, exists, concat, etc.) call PG_FREE_IF_COPY — they rely on
the executor-level memory context to reclaim. This is the standard PG
pattern.

### Operator side effects (PROMPT-SPECIFIC)

Per task prompt: `||` (concat), `->` (key access); palloc behavior on
huge keys?

- `->` (`hstore_fetchval`): one `cstring_to_text_with_len` palloc
  per call, size = vallen. Bounded by HSTORE_MAX_VALUE_LEN (1 GiB) via
  the original hstore's validation. Single-shot palloc; no doubling.
- `||` (`hstore_concat`): single `palloc(VARSIZE(s1) + VARSIZE(s2))`,
  bounded by `MaxAllocSize`. Then merge into the buffer (no further
  palloc). No O(n^2) accumulation.

No `repalloc`/doubling in `hstore_op.c` (unlike `hstore_io.c`'s
`hstore_in` parse buffer). `[verified-by-code]`. The Phase-D concern
about "uncapped growth" doesn't materialize in this file's modification
paths.

### `hstore_to_array_internal` ndims=2 specifics

`hstore_op.c:771-818` [verified-by-code]. When `ndims == 2`,
`out_size = {count, 2}` (count rows of 2 columns = key, value). When
`ndims == 1`, `out_size = {count*2}`. Empty hstore returns
`construct_empty_array`. Allocs `2*count` Datums + bools; for 1B
hstore that's 32 GB for the Datum array alone — but the source hstore
itself is capped at MaxAllocSize so count is ~26M max in practice.

### Embedded-NUL behavior in fetchval / exists

`hstore_fetchval` returns `cstring_to_text_with_len(val, vallen)` —
includes any embedded NULs. `hstore_exists` uses raw memcmp via
`hstoreFindKey`. So binary-input hstore values with NULs work
correctly here. `[verified-by-code]`.

### `hstore_delete_array` overflow

`hstoreArrayToPairs` already does the `MaxAllocSize / sizeof(Pairs)`
check. After dedup, the resulting `nkeys` is bounded. The output
hstore allocates `VARSIZE(hs)` — bounded.

## Cross-references

- `hstore.h.md` — Pairs, HEntry, ARRPTR/STRPTR/HSTORE_KEY/etc.
- `hstore_io.c.md` — `hstoreUniquePairs` and `hstorePairs` constructors
  used here.
- `hstore_subs.c.md` — the subscripting path duplicates concat's merge.
- `funcapi.h` — `SRF_FIRSTCALL_INIT`, `SRF_PERCALL_SETUP`,
  `SRF_RETURN_NEXT`, `SRF_RETURN_DONE`.
- `common/hashfn.h` — `hash_any`, `hash_any_extended`.
- A12 contrib security bundle — array-of-text input pattern.
- A7 record_recv DoS findings — comparison point for the bounded-input
  helpers here.

<!-- issues:auto:begin -->
- [Issue register — `hstore`](../../../issues/hstore.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-correctness: hstore_concat early SET_VARSIZE at line 489 is
  dead code overwritten by HS_FIXSIZE; harmless but lowers
  auditability. Same pattern at hstore_delete_array:309-310 and
  hstore_delete_hstore:389-390 (nit)]`
- `[ISSUE-correctness: hstore_cmp depends on canonical (sorted) string-
  buffer layout; a forged hstore that passes hstoreValidNewFormat but
  has non-canonical bytes would compare unequal to logically-equal
  hstores. Mitigated because all SQL-input paths produce sorted output
  (maybe)]`
- `[ISSUE-defense-in-depth: hstore_hash and hstore_hash_extended rely
  on Assert for the canonical-size invariant; in production builds an
  off-spec hstore would silently hash differently than its canonical
  sibling, causing hash-index lookup miss (maybe)]`
- `[ISSUE-api-shape: NULL-key handling is inconsistent across this
  file — slice_to_array preserves NULL slots in the output;
  delete_array drops them; concat/contains can't see NULLs at all
  because keys can't be NULL in a valid hstore. Worth documenting at
  the function-comment level (nit)]`
- `[ISSUE-documentation: hstore_svals' "ugly ugly ugly. why no macro
  for this?" comment (hstore_op.c:939) is a long-standing complaint
  about SRF NULL emission — the comment dates from pre-9.x SRF API and
  the situation hasn't materially improved (nit)]`
- `[ISSUE-audit-gap: setup_firstcall (hstore_op.c:849-875) lacks an
  explanatory comment beyond the maintainer's speculation "(At least I
  assume that's why; there was no explanatory comment in the original
  code. --AG)" — the actual reason is "detoasted Datum has lifetime of
  the calling executor context, multicall outlives it". Documentation
  gap (nit)]`
- `[ISSUE-correctness: hstore_to_array_internal with ndims=1 produces
  output `{key1, val1, key2, val2, ...}` interleaved — null values are
  preserved as array-null entries, but null KEYS can't exist so this
  is safe. The function comment doesn't make this explicit (nit)]`
- `[ISSUE-error-handling: hstore_populate_record (in hstore_io.c, but
  pairs with this file) uses `lookup_rowtype_tupdesc_domain` with
  noError=false; a renamed/dropped composite type during execution
  would error confusingly. Generic PG issue, not hstore-specific (nit)]`
- `[ISSUE-correctness: hstore_each emits null values via standard
  SRF_RETURN_NEXT with a properly-nulls-marked tuple; but hstore_svals
  uses the manual ExprMultipleResult path (line 941). Two different
  ways to emit null in the same file (nit)]`
- `[ISSUE-defense-in-depth: hstoreFindKey takes a `char *key, int
  keylen` — the lowbound parameter is in/out; no bounds-check on
  `*lowbound` (caller is trusted to pass 0..HS_COUNT(hs)). A misuse
  would walk off the entries[] array. Internal API; current call sites
  are correct (nit)]`
