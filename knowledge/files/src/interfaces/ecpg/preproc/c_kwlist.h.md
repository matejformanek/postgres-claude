---
path: src/interfaces/ecpg/preproc/c_kwlist.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 52
depth: read
---

# `c_kwlist.h` — X-macro list of C keywords recognized by the ECPG preprocessor

## Purpose

A pure data file: an ordered list of `PG_KEYWORD(name, token)` invocations
covering the C-language keywords (and a small set of SQL interval field names)
that the ECPG preprocessor's lexer must distinguish from ordinary identifiers in
host-variable declarations. It contains no logic. Callers `#define PG_KEYWORD`
to whatever expansion they need, `#include` this file, then `#undef PG_KEYWORD`.
The same file is consumed by `gen_keywordlist.pl` to produce `c_kwlist_d.h`
(the perfect-hash lookup tables). [from-comment `c_kwlist.h:5-8`]

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `PG_KEYWORD(kwname, value)` invocations | `c_kwlist.h:27-51` | 26 entries; each caller supplies its own macro definition |

There are no C declarations in this file — it is pure macro-invocation data.

## Internal landmarks

- **No include guard** (`c_kwlist.h:18`): deliberately omitted so the file can
  be `#include`d multiple times within the same translation unit with different
  `PG_KEYWORD` definitions. `c_keywords.c` exploits this: one include fills
  `ScanCKeywordTokens[]`, and `gen_keywordlist.pl` also reads it for string
  data.

- **ASCII-sort requirement** (`c_kwlist.h:23`): entries must appear in ASCII
  collation order. This is not enforced by C but is a hard requirement of
  `gen_keywordlist.pl`, which uses the order to build the perfect hash.

- **Keyword set** (`c_kwlist.h:27-51`): 26 entries covering:
  - C storage-class specifiers: `auto`, `const`, `extern`, `register`,
    `static`, `volatile` (`c_kwlist.h:28,31,33,40,44,51`)
  - C type keywords: `bool`, `char`, `enum`, `float`, `int`, `long`, `short`,
    `signed`, `struct`, `union`, `unsigned` (`c_kwlist.h:29,30,32,34,36,37,42,43,45,48,49`)
  - Identifier declaration: `typedef` (`c_kwlist.h:47`)
  - ECPG varchar extension: `VARCHAR` (uppercase) and `varchar` (lowercase),
    both mapped to token `VARCHAR` (`c_kwlist.h:27,50`)
  - SQL interval field names used in ECPG datetime host types: `hour`, `minute`,
    `month`, `second`, `to`, `year` (`c_kwlist.h:35,38,39,41,46,52`)

- **Duplicate token value** (`c_kwlist.h:27,50`): `VARCHAR` and `varchar` are
  distinct entries (different ASCII strings) mapping to the same bison token
  `VARCHAR`. This is the canonical way to make the C-keyword lookup
  case-insensitive for this one token while keeping all other lookups
  case-sensitive.

## Invariants & gotchas

- **ASCII sort order is a hard invariant** (`c_kwlist.h:23`): `gen_keywordlist.pl`
  reads the file and constructs a perfect hash assuming sorted input. Inserting
  a keyword out of order silently breaks the generated hash. The sort is by ASCII
  value, not locale: uppercase letters sort before lowercase (e.g., `VARCHAR`
  before `auto`). [from-comment]

- **No include guard by design** (`c_kwlist.h:18`): adding an `#ifndef` guard
  would break the multi-include pattern. Do not add one.

- **`PG_KEYWORD` must be defined by the caller**: this file will not compile
  standalone. It is always included inside a context that first defines
  `PG_KEYWORD`. [inferred from file structure]

- **Interval field names are not C keywords**: `hour`, `minute`, `month`,
  `second`, `to`, `year` are SQL concepts included here so the ECPG lexer can
  tokenize them properly when they appear in embedded-SQL interval type
  declarations (e.g., `INTERVAL HOUR TO MINUTE`). Their presence in a C-keyword
  list is ECPG-specific and would be surprising outside this context. [inferred]

## Cross-refs

- `src/interfaces/ecpg/preproc/c_keywords.c` — the only C file that `#include`s
  this header; defines `PG_KEYWORD` twice with different expansions.
- `src/interfaces/ecpg/preproc/c_kwlist_d.h` — generated output from this file
  via `src/tools/gen_keywordlist.pl`; contains `ScanCKeywords` struct and
  `ScanCKeywords_hash_func()`.
- `src/interfaces/ecpg/preproc/ecpg_kwlist.h` — sibling file listing SQL/ECPG
  keywords; follows the identical X-macro pattern.
- `src/backend/parser/kwlist.h` — backend SQL keyword list using the same
  `PG_KEYWORD` X-macro convention.
- `src/tools/gen_keywordlist.pl` — build tool that consumes this file.

## Potential issues

No issues. The file is a straightforward data table with 26 entries. The
ASCII-sort invariant is documented in the file itself (`c_kwlist.h:23`) and is
the only non-obvious constraint.

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new SQL keyword](../../../../../scenarios/add-new-sql-keyword.md)

<!-- scenarios:auto:end -->
