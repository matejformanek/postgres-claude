# citext.c

`source/contrib/citext/citext.c` (412 lines).

## One-line summary

Case-insensitive text type implemented as a thin layer over `text`: every comparison/hash function downcases both operands via `str_tolower(..., DEFAULT_COLLATION_OID)` and then calls `varstr_cmp`/`strcmp`/`hash_any`. **Critically**: `str_tolower` uses `DEFAULT_COLLATION_OID`, not the input collation, while `varstr_cmp` uses the input collation.

## Public API / entry points

- B-tree comparison: `citext_cmp`, `citext_pattern_cmp` — `source/contrib/citext/citext.c:107,124` [verified-by-code]
- Hash: `citext_hash`, `citext_hash_extended` — `citext.c:141,160`
- Equality / inequality: `citext_eq`, `citext_ne` (bitwise compare on lowered strings, no `strcoll`) — `citext.c:186,216`
- Ordering: `citext_lt`/`le`/`gt`/`ge` — `citext.c:246,263,280,297`
- Pattern-class ordering (binary compare on lowered): `citext_pattern_lt`/`le`/`gt`/`ge` — `citext.c:314,331,348,365`
- Aggregates min/max: `citext_smaller`, `citext_larger` — `citext.c:388,401`
- Note: `regexp_*`, `like`, `replace`, `split_part`, `strpos`, `translate`, `repeat`, `concat` are all defined in `citext--*.sql` as wrappers around the built-in `text` functions composed with `lower(citext)`. They are NOT implemented in C in this file.

## Key invariants

- `str_tolower` is **always called with `DEFAULT_COLLATION_OID`**, never the input collation — `citext.c:53-54,80-81,150,170,199-200,229-230` [verified-by-code]
- Comment explains: "We must do our str_tolower calls with DEFAULT_COLLATION_OID, not the input collation as you might expect. This is so that the behavior of citext's equality and hashing functions is not collation-dependent. We should change this once the core infrastructure is able to cope with collation-dependent equality and hashing functions." — `citext.c:45-51` [from-comment]
- After downcasing, equality functions use `strcmp` (NOT `strcoll`/`varstr_cmp`) — `citext.c:206,236` [verified-by-code]
- Ordering functions (`citext_lt` etc.) DO use the input collation via `varstr_cmp(lcstr, llen, rcstr, rlen, collid)` — so ordering IS collation-aware while equality is not — `citext.c:56-58`
- `citext_pattern_cmp` is binary `memcmp` on lowered strings, length-tiebreaker → ordering is "C collation" semantics regardless of input collation — `citext.c:80-99`
- `citext_hash` and `citext_hash_extended` use `hash_any` over lowered cstring — collation-agnostic — `citext.c:141-178`

## Notable internals

- All functions detoast via `PG_GETARG_TEXT_PP` (no copy if not toasted) and call `PG_FREE_IF_COPY` at the end — `citext.c:118-119,131-138,154-156,173-176,209-211,238-241,255-258,...`
- `str_tolower` lives in `utils/adt/formatting.c` (`utils/formatting.h`) — does Unicode case-folding when collation is locale-aware
- `varstr_cmp` lives in `utils/adt/varlena.c` (`utils/varlena.h`) — strcoll/strxfrm with deterministic-collation fast paths
- `hash_any` from `common/hashfn.h` — same hash as built-in `text`
- No locale/collation field in the storage format — `citext` IS `text` on disk; just different operator family

## Trust boundary / Phase D surface

This is **the** collation pathology section. Cross-link strongly to **A7 `pg_locale_icu`** which found ICU 73 "rules" path issues.

- **Equality vs ordering use DIFFERENT collations** — `citext_eq` downcases with `DEFAULT_COLLATION_OID` and then `strcmp`s; `citext_lt` downcases with `DEFAULT_COLLATION_OID` BUT compares with `PG_GET_COLLATION()` (input collation). This means `a = b` and `a < b OR a > b OR a = b` are NOT consistent under all collations. — `citext.c:199-206 vs 53-58,255-260` [verified-by-code]
  - Concrete failure: if the DB default collation lowercases differently than the explicit input collation does case-folding, `citext_eq('I', 'i') COLLATE "tr-TR"` could return true (default-collation lowercases both to "i") while `citext_lt('I', 'i' COLLATE "tr-TR")` is false (Turkish-collation comparison of "i" and "i" returns 0, then `varstr_cmp` may treat dotted-i differently). The HASH is keyed to default-collation lowercase, but the EQUALS-via-`citext_eq` also uses default-collation lowercase, so HASH+EQ are at least internally consistent. The B-tree ordering with a non-default collation is the inconsistent one. [verified-by-code] [ISSUE-COLLATION-MISMATCH]
- **ICU 73 "rules" path** — A7 corpus finding: `pg_locale_icu` has open issues around tailored collations with custom rules. `citext_cmp`/`citext_lt` all flow through `varstr_cmp` which routes to `pg_locale_icu` for ICU collations. If a column has an ICU collation with custom rules, the str_tolower may follow a different code path than the subsequent varstr_cmp. Result: case-folding can produce a different string than collation-equality expects. [inferred from A7 cross-link]
- **ASCII vs full Unicode case-folding**: `str_tolower` honors locale — for the default C locale it's ASCII-only; for libc/icu locales it's full Unicode (German ß → ss, Turkish dotless i, etc.). Two `citext` values that are equal in one collation may not be equal in another **on the same indexed column** if the index was built with a different DB default. — `citext.c:53` [inferred]
- **`citext_pattern_cmp` ignores collation entirely** — it lowercases with default collation then `memcmp`s. So `citext_pattern_ops` operator family produces C-collation ordering regardless of indexed-column collation. This is intentional (parallel to text's `~~` pattern ops) but a footgun when mixed with `citext_ops`. — `citext.c:71-99`
- **`regexp_*` family is NOT in this file** — defined in citext--1.x.sql as wrappers that call `lower(input::citext)` then the built-in `text` regexp. The regex engine does NOT case-fold per-char; it operates on the pre-lowered string. So `'Foo' ~ 'F'` returns FALSE on a citext column (because the column was lowered to `'foo'`, then matched against the regex literal `'F'`). Users routinely confused by this — but it's an SQL-level concern, not a C-code bug. [from-comment + SQL-script]
- **`PG_FREE_IF_COPY` after `pfree`**: in some operator functions (`citext_eq`, `citext_ne`), `pfree(lcstr)` is called BEFORE `PG_FREE_IF_COPY(left, 0)`. Since `lcstr` is a distinct alloc made by `str_tolower`, this is fine — they're independent allocations. — `citext.c:208-211`
- **No bounded input check** — citext functions accept arbitrarily large `text` values up to `MaxAllocSize`. `str_tolower` allocates a new buffer that can be larger than input (Unicode upper→lower can grow bytes, e.g. uppercase German letter "İ" → "i" + combining dot). DoS-by-large-input is no different from built-in `text`. — `citext.c:53`
- **`citext_smaller` and `citext_larger` return the ORIGINAL detoasted input**, not the lowered form — so aggregate min/max preserves the user's casing while comparing case-insensitively. Reasonable but means two equal-by-citext values can produce visibly different aggregate outputs depending on input order. — `citext.c:391-411` [verified-by-code]

## Cross-references

- `utils/formatting.h` (`str_tolower`)
- `utils/varlena.h` (`varstr_cmp`)
- `common/hashfn.h` (`hash_any`, `hash_any_extended`)
- A7 `pg_locale_icu` — collation-handling issues that ripple into citext via `varstr_cmp`
- `catalog/pg_collation.h` (`DEFAULT_COLLATION_OID`)
- `citext--*.sql` — where `regexp_*` etc. are composed in SQL

## Issues spotted

- [ISSUE-COLLATION-MISMATCH: `citext_eq` and `citext_lt` use different collations (DEFAULT for downcase, input for compare); breaks the equality-implies-not-less-and-not-greater invariant under tailored collations (Med — pre-existing, documented limitation)]
- [ISSUE-ICU-RULES: cross-link to A7 — `varstr_cmp` against an ICU collation with custom rules may interact unpredictably with `str_tolower(DEFAULT)` (Low-Med, depends on A7's resolution)]
- [ISSUE-PATTERN-OPS-CONFUSION: `citext_pattern_cmp` does memcmp-on-lower, ignoring collation, while `citext_cmp` is collation-aware — two opclasses on same column give different orderings (Doc / Footgun)]
- [ISSUE-REGEX-CASE: `~`/`!~` on citext lowercases ONLY the left side (in SQL wrappers) — `column ~ 'A'` always returns false on lowered storage (User-error / Doc)]
- [ISSUE-NO-LENGTH-LIMIT: citext functions accept up to MaxAllocSize inputs; `str_tolower` allocates a fresh buffer (Info — same as text)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-citext.md](../../../subsystems/contrib-citext.md)
