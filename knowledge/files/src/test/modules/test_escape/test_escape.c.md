---
path: src/test/modules/test_escape/test_escape.c
anchor_sha: e18b0cb7344
loc: 967
depth: read
---

# src/test/modules/test_escape/test_escape.c

## Purpose

Standalone **libpq client** binary that fuzzes the family of
string-escape functions exposed by libpq (`PQescapeLiteral`,
`PQescapeIdentifier`, `PQescapeStringConn`, `PQescapeStringInternal`)
and the FE_UTILS / jsonapi escape paths, plus the `psqlscan` lexer
treatment of double-quoted strings. Runs a Cartesian product of
hand-curated test vectors (covering quoting, embedded NULs, multi-byte
sequences, invalid UTF-8, ascii-overlap encodings) against the entire
set of escape functions, validating that each function either succeeds
with a well-formed escaped string or reports a documented error.
`[verified-by-code]` `test_escape.c:1-7,38-71`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `main` | (end) | CLI entry; `--conninfo` mandatory; iterates `pe_test_vectors[]` × `pe_test_escape_funcs[]` |
| `pe_test_escape_funcs[]` (static) | `:396` | Table of escape functions under test, each with `reports_errors` / `supports_only_valid` / `supports_only_ascii_overlap` / `supports_input_length` flags |
| `pe_test_vectors[]` (static) | `:445` | Hand-curated test inputs paired with the `client_encoding` they target |
| `test_one_vector_escape` (static) | `:632` | Runs one (vector, escape-fn) combination and reports pass/fail |
| `test_one_vector` (static) | `:861` | Wraps the per-vector loop over `pe_test_escape_funcs` |

## Internal landmarks

- `escapify` (`:100`) — pretty-printer for raw bytes; backslash-escapes
  control bytes and non-ASCII as `\xNN`. Comment notes the format
  could be improved.
- `pe_test_config` (`:24-33`) — verbosity, an open `PGconn`, and rolling
  pass/fail counters used to set the exit code.
- Each `pe_test_escape_func` flag drives different validation:
  - `reports_errors = false` → function is allowed to produce garbage on
    invalid input; the test just confirms it doesn't crash.
  - `supports_only_valid = true` → don't run with invalidly-encoded
    input unless `--force-unsupported` is passed.
  - `supports_only_ascii_overlap = true` → only test on encodings where
    multi-byte chars contain no ASCII bytes (i.e. UTF-8 etc.).
  - `supports_input_length = true` → the escape function accepts an
    explicit length, so tests embedded NULs.
- `NEVER_ACCESS_STR` sentinel (`:35`) — a string the escape function
  should never read past; placed beyond the declared length so a
  length-respecting function won't touch it.

## Invariants & gotchas

- FRONTEND program — links libpq, not a backend extension. Requires
  `--conninfo` to set up a real `PGconn` because some escape variants
  consult the connection's `client_encoding` and `standard_conforming_strings`.
- The test deliberately tries malformed encodings. Functions whose
  contract is "must be given valid input" (`supports_only_valid`) are
  skipped by default; `--force-unsupported` runs them anyway to see what
  breaks.
- Exit code is non-zero if any failure was recorded. Used by
  `t/001_test_escape.pl` (or equivalent) to pass/fail the build.
- `--verbosity` controls how many bytes of context the printer dumps for
  passing tests; failures are always verbose.

## Cross-refs

- `source/src/interfaces/libpq/fe-exec.c` — `PQescape*` functions under
  test.
- `source/src/fe_utils/string_utils.c` — `fmtId`, `appendStringLiteral`,
  related escape helpers.
- `source/src/common/jsonapi.c` — JSON string escape.
- `source/src/include/fe_utils/psqlscan.h` — flex lexer hooks; the
  `test_scan_callbacks` table is empty placeholder.
