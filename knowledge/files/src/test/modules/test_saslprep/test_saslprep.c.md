---
path: src/test/modules/test_saslprep/test_saslprep.c
anchor_sha: e18b0cb7344
loc: 278
depth: read
---

# src/test/modules/test_saslprep/test_saslprep.c

## Purpose

Test harness for `common/saslprep.h` — the SCRAM/SASL string preparation
routine (RFC 4013) used during SCRAM authentication. Two functions:
`test_saslprep` accepts arbitrary bytea input and returns the SASLprep
result + status code, suitable for table-driven regression of edge
cases; `test_saslprep_ranges` is a set-returning function that walks
every UTF-8 codepoint across the BMP and supplementary planes, calling
`pg_saslprep` on each and yielding `(codepoint, status, input_bytes,
output_bytes)` rows. `[verified-by-code]` `test_saslprep.c:50-55,142-148`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_saslprep(bytea) returns record` | `:57` | Single-shot test; `(output_bytes, status)` |
| `test_saslprep_ranges() returns setof record` | `:150` | SRF; iterates `pg_utf8_test_ranges[]` covering all valid Unicode planes |
| `saslprep_status_to_text(pg_saslprep_rc)` (static) | `:27` | Maps the enum return code to text: `OOM`, `SUCCESS`, `INVALID_UTF8`, `PROHIBITED` |

## Internal landmarks

- `pg_utf8_test_ranges` (`:125-137`) — 9 ranges covering all valid
  Unicode codepoints, **excluding the surrogate gap U+D800–U+DFFF**
  (split into two BMP ranges).
- `test_saslprep_ranges` (`:150`) — standard SRF skeleton:
  `SRF_IS_FIRSTCALL` initializes a `pg_saslprep_test_context`,
  `SRF_PERCALL_SETUP` advances. Each call converts a single codepoint
  with `unicode_utf8len` + `unicode_to_utf8` (`:213-220`), runs
  `pg_saslprep`, formats the codepoint as `U+XXXX` (4 hex) or `U+XXXXXX`
  (6 hex for supplementary planes), and emits a tuple.
- `test_saslprep` (`:57`) — copies the input into a null-terminated
  buffer (SASLprep operates on C strings) before calling `pg_saslprep`;
  packs result back into a bytea so binary contents survive the
  round-trip.

## Invariants & gotchas

- TEST MODULE — pure measurement; no hooks installed.
- The surrogate range `U+D800..U+DFFF` is deliberately skipped because
  UTF-8 encoding of those codepoints is invalid by definition
  (`[verified-by-code]` `:127-128`).
- `pg_saslprep` returns a freshly-`malloc`'d (palloc'd) string in
  `*output` on `SASLPREP_SUCCESS` — the SRF path `pfree`s it after
  copying into the result bytea (`:258`).
- For `INVALID_UTF8` / `PROHIBITED`, `output` is NULL and the result
  column is reported as SQL NULL.

## Cross-refs

- `source/src/common/saslprep.c` — implementation under test.
- `source/src/include/common/saslprep.h` — `pg_saslprep`,
  `pg_saslprep_rc` enum.
- `source/src/include/mb/pg_wchar.h` — `unicode_utf8len`,
  `unicode_to_utf8`.
