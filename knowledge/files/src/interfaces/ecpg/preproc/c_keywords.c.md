---
path: src/interfaces/ecpg/preproc/c_keywords.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 66
depth: deep
---

# `c_keywords.c` — C-keyword lookup for the ECPG preprocessor

## Purpose

Provides `ScanCKeywordLookup()`, the single entry point used by the ECPG
preprocessor's lexer to decide whether a bare identifier (appearing in a C
host-variable declaration or elsewhere in embedded SQL source) is a reserved C
keyword. The lookup is case-sensitive (unlike the backend's SQL-keyword lookup),
uses a generated perfect-hash function, and returns a bison token-value integer
or -1 on no match. The keyword table itself is sourced from `c_kwlist.h` via an
X-macro include, and the generated hash machinery lives in `c_kwlist_d.h`
(produced by `gen_keywordlist.pl` at build time).

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `ScanCKeywordLookup(const char *text)` | `c_keywords.c:36` | Returns bison token value or -1; sole public function in this file |
| `ScanCKeywordTokens[]` | `c_keywords.c:20` | `static` array mapping hash bucket index → bison token value; populated via `PG_KEYWORD` X-macro expansion of `c_kwlist.h` |

## Internal landmarks

- **X-macro bootstrap** (`c_keywords.c:18-22`): `PG_KEYWORD(kwname, value)` is
  defined locally as `value,` before including `c_kwlist.h`, which expands to a
  comma-separated list of bison token integers filling `ScanCKeywordTokens[]`.
  The `#undef PG_KEYWORD` at `c_keywords.c:24` cleans up so the macro does not
  leak to subsequent headers.

- **`c_kwlist_d.h`** (`c_keywords.c:13`): generated header that defines
  `ScanCKeywords` (a `ScanKeywordList` struct containing `num_keywords`,
  `max_kw_len`, and a pointer to the sorted keyword strings) and
  `ScanCKeywords_hash_func()` (the perfect-hash function). This file is produced
  by `gen_keywordlist.pl` from `c_kwlist.h` during the build.

- **Length short-circuit** (`c_keywords.c:46-48`): `strlen(text)` is compared
  against `ScanCKeywords.max_kw_len` before hashing. Any string longer than the
  longest C keyword is rejected immediately with no hash computation.

- **Perfect-hash dispatch** (`c_keywords.c:54`): `ScanCKeywords_hash_func(text,
  len)` maps the string to a bucket index. Because the hash is perfect, the
  function can return values in `[0, num_keywords)` only for strings that are
  candidates; anything outside that range means no match (`c_keywords.c:57-58`).

- **Verification step** (`c_keywords.c:60-63`): `GetScanKeyword(h,
  &ScanCKeywords)` retrieves the canonical keyword string at bucket `h`, then
  `strcmp(kw, text)` confirms an exact case-sensitive match before returning
  `ScanCKeywordTokens[h]`.

- **Case-sensitivity distinction** (`c_keywords.c:33`): the comment explicitly
  notes that this differs from `ScanKeywordLookup()` (the SQL-keyword version),
  which does case-folding. C keywords are matched as-is. This matters for
  `VARCHAR` vs. `varchar` — both appear in `c_kwlist.h` (`c_kwlist.h:27,50`)
  mapped to the same token `VARCHAR`, so both strings must be present as
  distinct entries.

## Invariants & gotchas

- **ASCII-sorted kwlist required** (`c_kwlist.h:23`): `gen_keywordlist.pl`
  requires entries in ASCII order. Violating this order will cause the generated
  perfect hash in `c_kwlist_d.h` to be incorrect, producing silent lookup
  failures. There is no runtime assertion enforcing sorted order.

- **`PG_KEYWORD` macro contract**: the macro must be defined before `c_kwlist.h`
  is included and undefined after. The file defines it at `c_keywords.c:18`,
  includes at `c_keywords.c:21`, and undefines at `c_keywords.c:24`. Breaking
  this sequence (e.g., including `c_kwlist.h` without a prior `PG_KEYWORD`
  definition) will produce compile errors.

- **`ScanCKeywordTokens[]` index alignment**: the array is indexed by the same
  hash bucket number used by `GetScanKeyword()`. The two data structures
  (`ScanCKeywords` string table and `ScanCKeywordTokens[]`) must be rebuilt
  together whenever `c_kwlist.h` changes; a stale `c_kwlist_d.h` will cause
  token mismatches. [verified-by-code]

- **No case folding**: C identifiers in ECPG host-variable sections are
  case-sensitive by C language rules, so the absence of `pg_tolower()` here is
  correct and intentional. [from-comment `c_keywords.c:33`]

## Cross-refs

- `src/interfaces/ecpg/preproc/c_kwlist.h` — the X-macro keyword list this file
  includes twice (once for `ScanCKeywordTokens[]`, the generated hash uses it
  for string data).
- `src/interfaces/ecpg/preproc/ecpg_keywords.c` — sibling file providing
  `ScanECPGKeywordLookup()` for SQL/ECPG keywords; uses the same pattern but
  over `ecpg_kwlist.h`.
- `src/backend/parser/keywords.c` — backend analog providing
  `ScanKeywordLookup()` with case-insensitive matching over the full SQL keyword
  set.
- `src/include/common/keywords.h` — declares `ScanKeywordList`, `GetScanKeyword`,
  and the shared lookup infrastructure used here.
- `src/tools/gen_keywordlist.pl` — build-time script that reads `c_kwlist.h` and
  emits `c_kwlist_d.h`.

## Potential issues

- **[ISSUE-undocumented-invariant: ASCII sort order not runtime-checked]**
  `c_kwlist.h:23` — The comment states entries must be ASCII-ordered for
  `gen_keywordlist.pl`, but there is no `static_assert` or runtime check in
  `c_keywords.c` to verify sorted order. If a developer adds a keyword out of
  order without running the generator, the mismatch between the stale
  `c_kwlist_d.h` and the updated `c_kwlist.h` will produce wrong lookups rather
  than a build error. Severity: low (caught by regression tests that exercise the
  affected keyword, and the build system regenerates `c_kwlist_d.h`
  automatically under normal builds).
