---
path: src/interfaces/ecpg/preproc/keywords.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 38
depth: deep
---

# `keywords.c` — backend SQL keyword token-number bridge for ECPG

## Purpose

Builds `SQLScanKeywordTokens[]`, the `uint16` array that maps backend SQL
keyword indices to ECPG's own bison token values. The backend's
`src/common/keywords.c` provides the `ScanKeywords` `ScanKeywordList` struct
(the keyword strings + perfect-hash) and `ScanKeywordLookup`; this file
supplies the parallel token-number table so that when `ScanECPGKeywordLookup`
finds a match in the backend table it can return the right token for ECPG's
grammar (`preproc.y`), not the backend's grammar (`gram.y`). The file contains
no functions — it is a data-only translation unit.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `SQLScanKeywordTokens[]` | `keywords.c:31-33` | `extern const uint16`; declared in `preproc_extern.h:67`. Indexed by `kwnum` from `ScanKeywordLookup`. |

## Internal landmarks

- **`PG_KEYWORD` macro redefinition** (`keywords.c:29`): `#define PG_KEYWORD(kwname, value, category, collabel) value,` extracts only the second argument (the bison token name) from each 4-argument `PG_KEYWORD` entry in `parser/kwlist.h`. The backend's `kwlist.h` uses the 4-argument form; this differs from `ecpg_kwlist.h`'s 2-argument `PG_KEYWORD(kwname, value)`.
- **Backend kwlist inclusion** (`keywords.c:32`): `#include "parser/kwlist.h"` pulls in `src/include/parser/kwlist.h` — the authoritative list of all SQL keywords the backend recognizes. The search path resolves this against the PostgreSQL include tree.
- **Token-number remapping** (`keywords.c:20-25` comment): The comment explains the subtlety: the token names (e.g., `SELECT`, `FROM`) are the same strings that appear in both `gram.h` and `preproc.h`, but their numeric values differ because bison assigns token numbers independently per grammar. By including `preproc.h` (via `preproc_extern.h`) rather than `gram.h`, each token name resolves to the ECPG grammar's value. [verified-by-code]
- **No include guard**: Like `ecpg_kwlist.h`, `parser/kwlist.h` has no guard and is designed for repeated inclusion with different `PG_KEYWORD` definitions.

## Invariants & gotchas

- **Token-name parity required** (`keywords.c:23-25` comment): ECPG's `preproc.y` must define `%token` for every keyword name that appears in `parser/kwlist.h`, otherwise the compile of `keywords.c` fails with undefined-symbol errors. When the backend adds a new keyword to `kwlist.h`, ECPG's grammar must be updated in lockstep. [from-comment]
- **Table length tied to backend kwlist**: The length of `SQLScanKeywordTokens[]` is implicitly determined by the number of `PG_KEYWORD` entries in `parser/kwlist.h` at build time. `ScanKeywords.num_keywords` (set in `src/common/keywords.c`) must equal this count; the build will produce wrong behavior (array out-of-bounds) if they diverge — but in practice they cannot diverge because both files are included in the same build from the same source tree. [inferred]
- **4-argument vs 2-argument `PG_KEYWORD`** (`keywords.c:29` vs `ecpg_keywords.c:20`): The two macro definitions differ in arity to match their respective kwlist files. A maintainer copying macro definitions between files must match the right form to the right kwlist. [verified-by-code]
- **`SQLScanKeywordTokens` is `extern`** (`keywords.c:31`, `preproc_extern.h:67`): Unlike `ECPGScanKeywordTokens` in `ecpg_keywords.c` which is `static`, this array is shared across translation units — `ecpg_keywords.c` references it directly in `ScanECPGKeywordLookup`. [verified-by-code]

## Cross-refs

- `src/interfaces/ecpg/preproc/ecpg_keywords.c` — the dispatcher; consumes `SQLScanKeywordTokens[]` at `ecpg_keywords.c:43`.
- `src/interfaces/ecpg/preproc/ecpg_kwlist.h` — the sibling ECPG-specific keyword list; uses the 2-argument `PG_KEYWORD` form.
- `src/include/parser/kwlist.h` — backend SQL keyword list (4-argument `PG_KEYWORD`); the data source `#include`d here.
- `src/common/keywords.c` — provides `ScanKeywords` (the `ScanKeywordList` struct with the perfect-hash) and `ScanKeywordLookup`.
- `src/interfaces/ecpg/preproc/preproc_extern.h` — declares `extern const uint16 SQLScanKeywordTokens[]` at line 67.
- `src/interfaces/ecpg/preproc/c_keywords.c` — sibling for C-language keywords; does NOT use `kwlist.h` or this pattern.
- `src/interfaces/ecpg/preproc/parser.c` — ECPG parser driver that invokes `ScanECPGKeywordLookup` (which uses this table).

## Potential issues

None identified. The file is a mechanical data-only translation unit; the token-remapping trick is well-documented in the file's comment and the pattern is stable.
