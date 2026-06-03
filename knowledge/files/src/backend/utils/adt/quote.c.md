---
path: src/backend/utils/adt/quote.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 135
depth: read
---

# quote.c

- **Source path:** `source/src/backend/utils/adt/quote.c`
- **Lines:** 135
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/builtins.h` (declares `quote_identifier`, `quote_literal_cstr`, and the `SQL_STR_DOUBLE`/`ESCAPE_STRING_SYNTAX` macros), `src/backend/utils/adt/ruleutils.c` (`quote_identifier` lives there), `src/include/varatt.h`

## Purpose
Implements the SQL-injection-relevant quoting builtins `quote_ident`, `quote_literal`, and `quote_nullable`, plus the C helper `quote_literal_cstr`. `[from-comment]` `quote.c:3-4`. `quote_ident` delegates the identifier-quoting policy to `quote_identifier()` (defined in ruleutils.c); this file only handles literal quoting itself. `[verified-by-code]` `quote.c:31-33`.

## Public symbols
| Symbol | file:line | Role |
|--------|-----------|------|
| `quote_ident` | `quote.c:24` | SQL `quote_ident(text)`: wraps `quote_identifier()` |
| `quote_literal` | `quote.c:75` | SQL `quote_literal(text)`: single-quote + double embedded quotes/backslashes |
| `quote_literal_cstr` | `quote.c:100` | C-string variant returning a palloc'd NUL-terminated string |
| `quote_nullable` | `quote.c:127` | SQL `quote_nullable(anyelement)`: NULL → text `'NULL'`, else `quote_literal` |
| `quote_literal_internal` (static) | `quote.c:44` | Shared core for both literal variants |

## Internal landmarks
- **`quote_literal_internal`** `quote.c:44-69` — the actual escaping. First it scans the input for any backslash; if found, it emits a leading `ESCAPE_STRING_SYNTAX` ('E') so the literal is interpreted with escape semantics even under `standard_conforming_strings = off`. `quote.c:50-57`. Then it wraps the body in single quotes, doubling each character for which `SQL_STR_DOUBLE(*src, true)` is true. `quote.c:59-66`. Returns bytes written. The `true` arg means "treat backslash as needing doubling too." `[verified-by-code]`
- **Worst-case allocation** in `quote_literal` `quote.c:86` is `len*2 + 3 + VARHDRSZ`: `len*2` if every char doubles, +1 for the optional leading `E`, +2 for the outer quotes. `quote_literal_cstr` `quote.c:109-114` matches with an extra +1 for the NUL terminator. `[verified-by-code]`
- **NULL handling** is only in `quote_nullable` `quote.c:127-135`: a strict-style check `PG_ARGISNULL(0)` returns the literal text `NULL` (note: the four characters NULL, *not* quoted), otherwise it forwards to `quote_literal` via `DirectFunctionCall1`. The function must therefore be declared non-strict in pg_proc. `[verified-by-code]`

## Invariants & gotchas
- **`quote_literal` must remain safe for old/remote servers.** The header note `quote.c:40-42` requires output that works with `standard_conforming_strings = off` (used by dblink to ship SQL to another server). This is *why* the leading `E` is conditionally emitted rather than relying on the modern default. `[from-comment]`
- **The leading `E` is emitted on the *first* backslash and the scan `break`s.** `quote.c:52-56`. Emitting it more than once would be wrong; the `break` guarantees at most one `E`. `[verified-by-code]`
- **Doubling covers both `'` and `\`.** `SQL_STR_DOUBLE(*src, true)` `quote.c:62` is the single source of truth for which characters get doubled; the SQL-injection safety of `quote_literal` rests entirely on that macro (defined in builtins.h) plus the `E` prefix. Any character it fails to double is an injection vector. `[verified-by-code]`
- **`quote_nullable` is non-strict by contract** `quote.c:130` — it inspects arg-0 nullness itself; marking it STRICT in the catalog would make it return NULL instead of `'NULL'`. `[inferred]` from the explicit `PG_ARGISNULL` usage.
- **`quote_ident` correctness is not in this file.** All identifier-quoting rules (reserved words, case folding, special chars) live in `quote_identifier()` in ruleutils.c; this file is a pure pass-through. `[verified-by-code]` `quote.c:31-33`.

## Cross-references
- [[knowledge/files/src/backend/utils/adt/encode.c]] — sibling adt codec file.
- [[knowledge/files/src/backend/utils/adt/ascii.c]] — sibling fmgr V1 text file.
- `ruleutils.c` `quote_identifier` — the real identifier-quoting logic (not yet documented); also the `SQL_STR_DOUBLE`/`ESCAPE_STRING_SYNTAX` definitions in `builtins.h`.
- [[knowledge/idioms/fmgr-and-spi]] — `quote_nullable` uses `DirectFunctionCall1` to reach `quote_literal`; `PG_ARGISNULL` for non-strict null handling.

## Potential issues
None identified. The allocation bounds, the at-most-one-`E` invariant, and the doubling logic are all internally consistent and the SQL-injection-relevant escaping is fully delegated to `SQL_STR_DOUBLE` + the conditional `E` prefix.

## Confidence tag tally
- `[verified-by-code]`: 8
- `[from-comment]`: 2
- `[inferred]`: 1
- `[from-README]`: 0
- `[unverified]`: 0
