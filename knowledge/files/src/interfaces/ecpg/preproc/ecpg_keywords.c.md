---
path: src/interfaces/ecpg/preproc/ecpg_keywords.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 54
depth: deep
---

# `ecpg_keywords.c` — ECPG-specific keyword lookup dispatcher

## Purpose

Implements `ScanECPGKeywordLookup`, the single entry point the ECPG
lexer (`pgc.c`) calls to classify an identifier-shaped token. The function
first probes the backend's SQL keyword table (`ScanKeywords` / `ScanKeywordLookup`)
and, on a miss, probes the ECPG-specific table (`ScanECPGKeywords`) backed by
`ecpg_kwlist.h`. This two-pass design means ECPG reuses the complete backend
keyword list (≈500 keywords) while adding its own ~40 ECPG-only tokens without
any risk of collisions being silently swallowed.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `ScanECPGKeywordLookup(const char *text)` | `ecpg_keywords.c:37` | Returns bison token value for `text`, or `-1` if unknown. Declared `extern` in `preproc_extern.h`. |
| `ECPGScanKeywordTokens[]` (file-static) | `ecpg_keywords.c:21-23` | `uint16` array mapping ECPG keyword index → bison token; populated via the `PG_KEYWORD` X-macro over `ecpg_kwlist.h`. |

## Internal landmarks

- **`ecpg_kwlist_d.h` inclusion** (`ecpg_keywords.c:16`): This is a *build-generated*
  file produced by `gen_keywordlist.pl --varname ScanECPGKeywords ecpg_kwlist.h`
  (see `Makefile` target `ecpg_kwlist_d.h`). It defines the `ScanECPGKeywords`
  `ScanKeywordList` struct and the perfect-hash function
  `ScanECPGKeywords_hash_func`. The source file is not checked in; it appears
  only in the build directory.
- **`ECPGScanKeywordTokens[]` population** (`ecpg_keywords.c:20-24`): The array
  is built by `#define PG_KEYWORD(kwname, value) value,` and then
  `#include "ecpg_kwlist.h"`, the canonical X-macro pattern used throughout PG.
- **First-pass: backend SQL keywords** (`ecpg_keywords.c:42-44`): Calls
  `ScanKeywordLookup(text, &ScanKeywords)` from `src/common/keywords.c`.
  On match, returns `SQLScanKeywordTokens[kwnum]`, the ECPG-local token value
  for that backend keyword (see `keywords.c` doc for why the token numbers differ).
- **Second-pass: ECPG keywords** (`ecpg_keywords.c:47-49`): Calls
  `ScanKeywordLookup(text, &ScanECPGKeywords)`. On match, returns
  `ECPGScanKeywordTokens[kwnum]`.
- **Miss path** (`ecpg_keywords.c:51`): Returns `-1`; lexer treats the token as
  a plain identifier.

## Invariants & gotchas

- **Backend-first priority** (`ecpg_keywords.c:42-44`): If a token appears in
  both the backend kwlist and `ecpg_kwlist.h` the backend entry wins. In practice
  the lists are disjoint, but any future overlap would silently use the backend
  token value. [verified-by-code]
- **Case-folding** (`ecpg_keywords.c:31` comment): Backend's `ScanKeywordLookup`
  performs case-insensitive matching (lowercase fold before hash). ECPG keywords
  in `ecpg_kwlist.h` are also lowercase and matched via the same
  `ScanKeywordLookup` path, so ECPG keywords are also case-insensitive. [verified-by-code]
- **Token-number remapping** (`ecpg_keywords.c:43`, `keywords.c`): `SQLScanKeywordTokens`
  does NOT use backend `gram.h` token values; it uses ECPG's own `preproc.h`
  token values. The comment in `keywords.c` makes this explicit. [verified-by-code]
- **`ECPGScanKeywordTokens` is static** (`ecpg_keywords.c:21`): Unlike
  `SQLScanKeywordTokens` (declared `extern` in `preproc_extern.h`), the ECPG
  token array has internal linkage; it is accessed only via `ScanECPGKeywordLookup`.

## Cross-refs

- `src/interfaces/ecpg/preproc/ecpg_kwlist.h` — X-macro source for `ECPGScanKeywordTokens[]` and for the generated `ScanECPGKeywords` struct.
- `src/interfaces/ecpg/preproc/keywords.c` — builds `SQLScanKeywordTokens[]` from the backend's `parser/kwlist.h` with ECPG token numbers.
- `src/interfaces/ecpg/preproc/c_keywords.c` — sibling for C-language keywords (struct, unsigned, etc.); uses a case-*sensitive* hash, unlike this file.
- `src/common/keywords.c` — defines `ScanKeywords` (backend SQL keyword table) and `ScanKeywordLookup`.
- `src/include/common/keywords.h` — declares `ScanKeywordList`, `ScanKeywordLookup`.
- `src/interfaces/ecpg/preproc/preproc_extern.h` — `extern int ScanECPGKeywordLookup(const char *text);` declaration consumed by `pgc.c`.
- `src/interfaces/ecpg/preproc/parser.c` — the ECPG parser driver that feeds tokens from `pgc.c`.

## Potential issues

None identified. The file is small and mechanically correct; the two-table lookup order is intentional and documented.
