# btree_gin.c

`source/contrib/btree_gin/btree_gin.c` (978 lines).

## One-line summary

Generic framework letting a GIN index emulate a B-tree on a single scalar column, supporting all B-tree strategies (`<`, `<=`, `=`, `>=`, `>`) for ~24 built-in scalar types (int2/4/8, float4/8, money, oid, timestamps, date, time(tz), interval, macaddr(8), inet, cidr, text, bpchar, char, bytea, bit, varbit, numeric, anyenum, uuid, name, bool) including cross-type comparison operators. The `GIN_SUPPORT(type, leftmostvalue, is_varlena, cvtfns, cmpfns)` macro spits out the three opclass entry points for each type.

## Public API / entry points

- `gin_btree_consistent(check, strategy, query, nkeys, extra, recheck)` — always returns `true` with `recheck=false` (the partial-match step already settled it) — `source/contrib/btree_gin/btree_gin.c:235-243` [verified-by-code]
- Per type, `GIN_SUPPORT(T)` macro emits:
  - `gin_extract_value_T(value, *nentries)` — `btree_gin.c:247-253`
  - `gin_extract_query_T(query, *nentries, strategy, partialmatch, extra_data, searchMode)` — `btree_gin.c:254-261`
  - `gin_compare_prefix_T(partial_key, key, ?, extra)` — `btree_gin.c:262-267`
- `gin_numeric_cmp(a, b)` — handles `PointerGetDatum(NULL)` as leftmost — `btree_gin.c:810-835`
- `gin_enum_cmp(a, b)` — handles `InvalidOid` as leftmost — `btree_gin.c:863-890`
- Internal: `gin_btree_extract_value`, `gin_btree_extract_query`, `gin_btree_compare_prefix` — `btree_gin.c:50-233`

## Key invariants

- **Strategy-number encoding**: low 4 bits = B-tree strategy (`BTLessStrategyNumber=1, BTLessEqualStrategyNumber=2, BTEqualStrategyNumber=3, BTGreaterEqualStrategyNumber=4, BTGreaterStrategyNumber=5`); high bits = RHS type code (0 = same as indexed; 1, 2, ... = cross-type indexed-into-RHS code) — `btree_gin.c:25-32` [verified-by-code]
- `<` / `<=`: start at leftmost value, partial-match=true, scan forward until `cmp > 0` (resp. `cmp >= 0`) — `btree_gin.c:115-119,190-203`
- `>` / `>=`: start at supplied query datum (or converted form), partial-match=true, keep scanning forward — `btree_gin.c:120-122,212-225`
- `=`: start at supplied query datum (or converted form). **If a conversion function applied** → partial-match=true (multiple index entries can match an imprecise converted key). Otherwise partial-match=false, exact equal lookup — `btree_gin.c:124-133,204-211`
- For cross-type comparison, the conversion function produces a Datum of the INDEXED type that is ≤ the actual query value (rounding down). The compare-prefix step then does a precise cross-type comparison via `data->orig_datum` and `data->typecmp` — `btree_gin.c:138-147,283-294`
- `gin_btree_compare_prefix` returns: -1 = keep scanning forward; 0 = match; +1 = end scan — `btree_gin.c:188-230`
- `gin_btree_consistent` returns `true` always with `recheck=false` because by the time we reach consistent, the prefix-match phase has already filtered to matching entries — `btree_gin.c:235-243` [verified-by-code]
- **Detoast on insert**: `gin_btree_extract_value` calls `PG_DETOAST_DATUM` if the indexed type is varlena — `btree_gin.c:57-60`
- **Detoast on query**: `gin_btree_extract_query` detoasts the RHS query datum based on the per-strategy `rhs_is_varlena[rhs_code]` flag — `btree_gin.c:91-96`

## Notable internals

- Numeric and anyenum use a NULL-pointer / `InvalidOid` sentinel for "leftmost value" because there's no real left-most numeric or enum value — special-cased in `gin_numeric_cmp` / `gin_enum_cmp` — `btree_gin.c:800-849, 851-904`
- `cvt_text_name` truncates oversize text via `pg_mbcliplen` to `NAMEDATALEN-1` and assumes "shorter result is less than original" — comment notes this is "a bad assumption in some collations, but fortunately an index on `name` is generally going to use C collation" — `btree_gin.c:934-953` [from-comment] [ISSUE-NAME-TRUNCATE]
- `cvt_timestamp_date`/`cvt_timestamptz_date` etc. use `*_safe` variants with `ErrorSaveContext` and IGNORE errors ("result is useful as-is") — `btree_gin.c:495-553,605-625` [verified-by-code]
- `inet` leftmost = `0.0.0.0/0` (parsed via `inet_in`) — `btree_gin.c:689-693`
- `cidr` shares the same leftmost and compare with inet but its own `is_varlena` array — `btree_gin.c:702-709`
- `text` cross-types: `name` → text via `cvt_name_text` — `btree_gin.c:717-733`
- `bpchar`, `bytea`, `bit`, `varbit` re-use `leftmostvalue_text` (or per-type empty value) — `btree_gin.c:736-799`
- `gin_btree_compare_prefix` has an Assert that `partial_key == data->entry_datum` — defensive check that core GIN didn't change what it passes to compare_prefix — `btree_gin.c:170` [verified-by-code]

## Trust boundary / Phase D surface

- **Coverage asymmetry vs `btree_gist`** (A13-3): A quick comparison — `btree_gin` covers `anyenum`, `numeric`, `uuid`, `bool`, `name`. `btree_gist` covers `enum`, `numeric`, `uuid`, `bool`, but lacks `name`. Both cover the integer/float/money/date/time/interval/macaddr/inet/cidr/text/bpchar/bytea/bit/varbit families. The differences mainly come from GiST needing a "distance" operator that's harder for some types. No asymmetry that exposes user data — both are read-only opclasses over the underlying type's compare function.
- **`partial_match` cross-type cliff**: when the RHS conversion is imprecise (e.g. float8 query against float4 index), GIN starts the scan up to one entry too early and the per-entry compare filters out false hits. Comment at `btree_gin.c:182-186` explains: for `=` cases this can stop early; for `>` and `>=` must continue scanning. **This is the well-known "GIN compare_partial" gotcha** — any future addition of a cross-type compare must implement the same continuation logic. — `btree_gin.c:182-225` [verified-by-code]
- **NULLs in indexed values**: `gin_extract_value_T` is called with a non-NULL value (GIN handles NULLs in the framework before calling extract). For multi-valued GIN indexes (e.g. on `int4[]`), NULLs in the array become `GIN_KEY_NULL` entries — but `btree_gin` is single-value, so this doesn't apply. **However**: if a `btree_gin` opclass is used as a member of a multi-column GIN, the index entry stored per non-null column value is the value itself; an actual SQL NULL is handled by GIN's own NULL bitmap. — `btree_gin.c:50-64`
- **`cvt_text_name` truncation**: shortening to `NAMEDATALEN-1` and assuming the result is less than original is only correct in C collation. For ICU/libc collations with non-byte-comparison ordering, this could incorrectly position the converted key. Comment acknowledges this. Cross-link to A7 `pg_locale_icu`. — `btree_gin.c:941-947` [from-comment] [ISSUE-NAME-TRUNCATE]
- **`leftmostvalue_inet` calls `inet_in`** on the cstring `"0.0.0.0/0"` every time. Repeated allocations per scan — wasteful but not exploitable. — `btree_gin.c:689-693`
- **`leftmostvalue_uuid`**: returns the all-zeros UUID. This is a valid UUID; an indexed column containing the all-zeros UUID would have it sorted first — but `gin_compare_prefix` does the precise cross-type compare, so correctness is preserved. — `btree_gin.c:907-916`
- **`leftmostvalue_macaddr`/`leftmostvalue_macaddr8`**: `palloc0`'d structs — all-zero MAC. Same observation. — `btree_gin.c:657-687`
- **`leftmostvalue_timetz`**: hardcoded `zone = -24 * 3600`, with comment "XXX is that true?" — the canonical timetz range is `±15:59:00`, so -24h is past valid; the compare function uses this as a sentinel. Could theoretically conflict with a valid time at exactly -24h. — `btree_gin.c:579-588` [from-comment] [ISSUE-TIMETZ]
- **`gin_btree_consistent` returns `true` blindly**: the contract relies on the partial-match step having pruned. If a future core change to GIN sends `consistent` with check[]=false (no matches), this still returns true → no rows returned, harmless. But the `recheck=false` means GIN trusts the result fully. Auditable: a bug in `compare_prefix` would manifest as "wrong rows returned". — `btree_gin.c:235-243`
- **`Assert(partial_key == data->entry_datum)`** is a Datum equality check. For pass-by-value types it compares the int64 directly; for pass-by-ref it compares pointers. A pass-by-ref type whose `extract_query` returned a freshly allocated Datum that GIN then copies would fail this Assert — defensive but could fire spuriously on future GIN refactors. — `btree_gin.c:170`

## Cross-references

- `access/gin/*` — generic GIN framework (`GIN_SEARCH_MODE_*`, partial-match protocol, `compare_partial`)
- `access/stratnum.h` — `BT*StrategyNumber`
- `utils/numeric.c` — `numeric_cmp`, `Numeric` type
- A7 `pg_locale_icu` — collation issues affect `text`/`bpchar`/`name` opclasses
- A11 contrib top-4 — `btree_gist` is the sister opclass set (A13-3)
- `nodes/miscnodes.h` — `ErrorSaveContext` (soft-error context)

## Issues spotted

- [ISSUE-NAME-TRUNCATE: `cvt_text_name` truncates to NAMEDATALEN-1 and assumes truncation produces a smaller value — only valid in C collation, documented in comment (Low — pre-existing, code-comment-acknowledged)]
- [ISSUE-TIMETZ: hardcoded "zone = -24*3600" for `leftmostvalue_timetz` with FIXME comment "XXX is that true?" since 1990s (Low)]
- [ISSUE-CONVERSION-ASYMMETRIC: cross-type `=` with imprecise conversion always sets partial-match=true, but the per-row recheck guarantees correctness — performance footgun if a user expects O(log N) exact-match lookups (Info)]
- [ISSUE-CONSISTENT-CONST-TRUE: `gin_btree_consistent` returns true unconditionally; relies on prefix-match correctness — auditable but fragile against future GIN refactors (Info)]
- [ISSUE-ASSERT-FRAGILE: `Assert(partial_key == data->entry_datum)` compares Datums by value for pass-by-ref types, comparing pointers; future GIN refactor that copies the Datum will fire this Assert (Low)]
- [ISSUE-LEFTMOST-INET-COST: `leftmostvalue_inet` calls `inet_in` per scan, allocating fresh memory (Trivial perf)]
