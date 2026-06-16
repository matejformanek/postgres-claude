---
path: src/interfaces/ecpg/ecpglib/data.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 962
depth: deep
---

# `data.c` — converts PostgreSQL result values into ECPG C host variables

## Purpose
This file implements the result-side of ECPG's data marshalling: taking a
column value out of a `PGresult` and storing it into the C host variable the
embedded-SQL program declared, doing the per-type ASCII/binary decode,
indicator handling, truncation accounting, and array expansion. The single
public entry point is `ecpg_get_data` (`data.c:194`), a large per-type
`switch` driven by the ECPGt_* host-variable type. It also carries a small set
of hex codec helpers (`ecpg_hex_*`) copied from the backend's `encode.c`, used
to decode `bytea` results. [verified-by-code] Note: despite the routine task
prompt, the *input/bind* side (`ecpg_store_input`) lives in `execute.c`, not
here — this file is purely the get/decode direction. [inferred]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `unsigned ecpg_hex_enc_len(unsigned srclen)` | data.c:116 | `srclen << 1`; encoded length of a hex dump. |
| `unsigned ecpg_hex_dec_len(unsigned srclen)` | data.c:122 | `srclen >> 1`; decoded length from hex. |
| `unsigned ecpg_hex_encode(const char *src, unsigned len, char *dst)` | data.c:179 | Lowercase hex encode; returns `len * 2`. |
| `bool ecpg_get_data(const PGresult *results, int act_tuple, int act_field, int lineno, enum ECPGttype type, enum ECPGttype ind_type, char *var, char *ind, long varcharsize, long offset, long ind_offset, enum ARRAY_TYPE isarray, enum COMPAT_MODE compat, bool force_indicator)` | data.c:194 | The workhorse: decode one (tuple,field) into host var `var` + indicator `ind`, expanding arrays in place. Returns false (after `ecpg_raise`) on error. |

## Internal landmarks
- `array_delimiter` (data.c:19) / `array_boundary` (data.c:32) — classify a
  char for ARRAY (`,` / `}`) vs VECTOR (` ` / `\0`) element separation.
- `garbage_left` (data.c:45) — post-scan trailing-junk check after a
  `strtol`/`strtod`/`PGTYPES*_from_asc`. In INFORMIX mode it tolerates and
  skips a `.frac` tail when reading numeric→int (truncation semantics,
  data.c:54). [verified-by-code]
- `check_special_value` (data.c:89) — recognizes `NaN`/`Infinity`/`-Infinity`
  before `strtod` for float/double columns (data.c:457). Uses
  `pg_strncasecmp` with fixed lengths 3/8/9.
- `get_hex` (data.c:128) / `hex_decode` (data.c:149) — bytea hex-format
  decode, copied from backend `encode.c`; whitespace-skipping.
- Indicator dispatch — repeated `switch (ind_type)` blocks write the NULL flag
  (-1) at data.c:245, and write the *original size* on truncation at data.c:331
  (binary), 528 (bytea), 589/651 (char/string), 694 (varchar). The
  `ECPGt_NO_INDICATOR` arm (data.c:263) routes Informix-style in-band NULLs via
  `ECPGset_noind_null`, or raises `ECPG_MISSING_INDICATOR` when
  `force_indicator` is set.
- Type decode dispatch `switch (type)` (data.c:359) — the heart:
  - signed ints `strtol` (data.c:375); unsigned `strtoul` (data.c:404);
    `long long` `strtoll`/`strtoull` (data.c:431/442).
  - float/double via `check_special_value` + `strtod` (data.c:452), with
    array `"`-quote stripping.
  - bool: only literal `t`/`f` accepted, plus empty+NULL (data.c:486).
  - bytea: hex-decode into `ECPGgeneric_bytea` (data.c:510), `src_size = size - 2`
    to drop the leading `\x`.
  - char/unsigned_char/string (data.c:556): ORACLE_MODE blank-pad path
    (data.c:576), otherwise `strncpy(str, pval, size + 1)`; ECPGt_string does an
    rtrim (data.c:617). `varchar` (data.c:679) fills `ECPGgeneric_varchar`.
  - numeric/decimal (data.c:724), interval (data.c:781), date (data.c:835),
    timestamp (data.c:883) — each temporarily NUL-terminates at the next
    delimiter, calls the matching `PGTYPES*_from_asc`, restores the char, and
    honors INFORMIX in-band-NULL fallbacks.
- Array loop — outer `do { … } while (*pval != '\0' && !array_boundary(...))`
  (data.c:318/959) advances `act_tuple` and walks `pval` past the next element,
  tracking `"`-quoted strings (data.c:938-957).

## Invariants & gotchas
- `var + offset * act_tuple` and `ind + ind_offset * act_tuple` are the storage
  addresses; in array mode `act_tuple` is incremented per element (data.c:943),
  so `offset`/`ind_offset` must be the per-element stride. Breaking the stride
  arithmetic corrupts adjacent host array slots. [verified-by-code]
- The numeric/interval/date/timestamp arms **mutate `pval` in place**: they
  write `'\0'` at `endptr` then restore the saved char (data.c:727-730 etc.).
  `pval` points into libpq's `PGresult` buffer, so this is a transient write to
  libpq-owned memory; the restore at data.c:730/789/843/891 must run on every
  path or the result buffer is left corrupted. [verified-by-code]
- Char copy uses `strncpy(str, pval, size + 1)` (data.c:614) which copies the
  terminating NUL only because the caller is asserted to have storage that
  exactly fits when `varcharsize > size`. When `varcharsize == 0` the code
  assumes "storage exactly fits" and uses `charsize = size + 1` (data.c:636) —
  there is no bound from the library side, the generated preprocessor code is
  trusted to size the buffer. [verified-by-code]
- `varchar` arm with `varcharsize == 0` does `strncpy(variable->arr, pval, len)`
  with no `+1` and no explicit NUL — `ECPGgeneric_varchar` carries its own
  `len`, so the array is intentionally not NUL-terminated here (data.c:685).
  [inferred]
- Float/numeric parsing uses libc `strtod` / `PGTYPESnumeric_from_asc`. ECPG
  results come back in the connection's number format; `strtod` here is locale
  sensitive (`LC_NUMERIC`) unless ECPG has forced the C locale upstream. This is
  a known ECPG concern but is NOT handled in this file. [inferred]
- `get_hex` guards with `if (c > 0 && c < 127)` (data.c:143) — note it excludes
  `c == 0` and `c == 127`, returning -1 (so `v1|v2` yields garbage bits, not a
  crash) for out-of-range hex chars; `hex_decode` does not validate that both
  nibbles are valid, it just ORs them. [verified-by-code]

## Cross-refs
- [[execute.c]] — owns `ecpg_store_input` (the bind/input direction) and is the
  primary caller path that fetches results then invokes `ecpg_get_data`.
- [[descriptor.c]] — descriptor-area GET also funnels column values through
  `ecpg_get_data`.
- [[ecpglib_extern.h]] — declares `ecpg_get_data`, `ecpg_raise`,
  `ecpg_internal_regression_mode`, `ECPGset_noind_null`.
- pgtypeslib (`PGTYPESnumeric_from_asc`, `PGTYPESdate_from_asc`,
  `PGTYPESinterval_from_asc`, `PGTYPEStimestamp_from_asc`) — the typed ASCII
  parsers invoked per arm.

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-overflow: hex_decode returns -1 as unsigned]** `data.c:170` —
  `hex_decode` returns `(unsigned)-1` when `s >= srcend` after consuming the
  first nibble (odd-length / truncated hex). That value is stored directly into
  `variable->len` at `data.c:521`, yielding a huge bogus length the caller may
  trust. Low severity (server-produced bytea is always well-formed) but a
  malformed/forged result row would mislead the host program. [inferred]
- **[ISSUE-truncation: signed narrowing on int decode]** `data.c:387/390` —
  `strtol` result is cast to `(short)`/`(int)` with no range check, so a value
  exceeding the host type silently wraps. Matches documented ECPG behavior
  (no overflow detection on integer fetch) but is a real precision/sign
  footgun. Low severity. [verified-by-code]
- **[ISSUE-locale: strtod under LC_NUMERIC]** `data.c:458` — `strtod` parsing
  of float columns is locale-dependent; if the process `LC_NUMERIC` expects a
  comma decimal separator, a server `.`-formatted float mis-parses (and
  `garbage_left` may then reject it). Not mitigated in this file. Low/medium
  severity depending on caller locale hygiene. [inferred]
