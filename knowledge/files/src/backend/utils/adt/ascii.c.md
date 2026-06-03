---
path: src/backend/utils/adt/ascii.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 199
depth: deep
---

# ascii.c

- **Source path:** `source/src/backend/utils/adt/ascii.c`
- **Lines:** 199
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/ascii.h` (declares `ascii_safe_strlcpy`), `src/include/utils/fmgrprotos.h` (`to_ascii_*` prototypes), `src/include/mb/pg_wchar.h` (`PG_LATIN1` etc., `pg_char_to_encoding`, `GetDatabaseEncoding`, `PG_VALID_ENCODING`), `src/include/varatt.h`

## Purpose
Implements the SQL `to_ascii()` family, which transliterates a Latin/Windows
8-bit-encoded string down to 7-bit ASCII by mapping accented letters to their
unaccented base and other high bytes to spaces `[from-comment]` `ascii.c:2-3`. Only
four source encodings are supported: `PG_LATIN1`, `PG_LATIN2`, `PG_LATIN9`,
`PG_WIN1250` `[verified-by-code]` `ascii.c:41-72`. Also provides
`ascii_safe_strlcpy`, an error-free `strlcpy` variant (callable from the
postmaster) that replaces every non-printable / non-ASCII byte with `?`
`[from-comment]` `ascii.c:164-172`.

## Public symbols

| Symbol | file:line | Role |
|---|---|---|
| `to_ascii_encname` | ascii.c:118 | SQL `to_ascii(text, name)`; resolves encoding name then transliterates |
| `to_ascii_enc` | ascii.c:137 | SQL `to_ascii(text, int)`; encoding given as integer code |
| `to_ascii_default` | ascii.c:155 | SQL `to_ascii(text)`; uses `GetDatabaseEncoding()` |
| `ascii_safe_strlcpy` | ascii.c:173 | Non-throwing ASCII-sanitizing `strlcpy`, safe in postmaster |

## Internal landmarks

- **`pg_to_ascii`** `ascii.c:28-94` — the core mapping. Selects a per-encoding
  translation string and a `range` start (128 or 160), then for each byte: keep if
  `< 128`; emit `' '` if `< range` (the "bogus" gap between 128 and range); else
  index `ascii[*x - range]` `ascii.c:85-93`. Unsupported encoding →
  `ERRCODE_FEATURE_NOT_SUPPORTED` `ascii.c:73-80`.
- **Translation tables** are inline string literals, one per encoding:
  LATIN1 `ascii.c:46` (range 160), LATIN2 `ascii.c:54` (range 160), LATIN9
  `ascii.c:62` (range 160), WIN1250 `ascii.c:70` (range 128). `RANGE_128` /
  `RANGE_160` macros `ascii.c:38-39`.
- **`encode_to_ascii`** `ascii.c:103-112` — wraps `pg_to_ascii` writing the result
  **in place** over the input text datum (src == dest). Comment `ascii.c:96-101`
  states this method "cannot support conversions that change the string length."
- **fmgr wrappers** all take `PG_GETARG_TEXT_P_COPY(0)` so the in-place overwrite
  mutates a private copy: `to_ascii_encname` `ascii.c:118-131` (rejects unknown
  name via `pg_char_to_encoding < 0`), `to_ascii_enc` `ascii.c:137-149` (rejects via
  `PG_VALID_ENCODING`), `to_ascii_default` `ascii.c:155-162`.

## Invariants & gotchas

- **In-place rewrite requires a 1:1 byte mapping.** `encode_to_ascii` overwrites the
  source datum and relies on every input byte producing exactly one output byte; the
  comment `ascii.c:96-101` warns any length-changing transliteration would corrupt
  the datum. `pg_to_ascii` honors this — every branch writes exactly one byte
  `ascii.c:87-92`. `[from-comment]` + `[verified-by-code]`.
- **`PG_GETARG_TEXT_P_COPY` is mandatory**, not `PG_GETARG_TEXT_PP`, precisely
  because the conversion mutates the datum in place; using a shared/detoasted
  pointer would clobber the caller's value `ascii.c:121, 140, 158`. `[verified-by-code]`
- **Translation strings must be exactly `256 - range` bytes long.** For range-160
  encodings the table covers bytes 160..255 (96 entries); for range-128 WIN1250 it
  covers 128..255 (128 entries). `pg_to_ascii` indexes `ascii[*x - range]` with no
  bounds check, so a short table is an out-of-bounds read `ascii.c:92`.
  `[verified-by-code]` (the literals are sized to match; verify on any edit).
- **`ascii_safe_strlcpy` must never `ereport`.** It is called from the postmaster
  where error longjmp is unsafe; it only keeps printable ASCII (32..127) plus
  `\n \r \t`, mapping everything else to `?`, and always NUL-terminates (handling
  the `destsiz == 0` corner) `ascii.c:170, 176-198`. `[from-comment]` + `[verified-by-code]`.
- **`to_ascii` is undefined for UTF-8 and most encodings** — only the four 8-bit
  Latin/Windows encodings are wired; anything else errors `ascii.c:73-80`. This is a
  known historical limitation, not a bug. `[verified-by-code]`

## Cross-references

- [[knowledge/files/src/backend/utils/adt/encode.c]] — sibling adt codec file (bytea<->text).
- [[knowledge/files/src/backend/utils/adt/quote.c]] — sibling adt string-function file.
- `src/backend/utils/mb/` — `pg_char_to_encoding`, `GetDatabaseEncoding`,
  `pg_encoding_to_char` used here for encoding resolution.
- [[knowledge/idioms/fmgr-and-spi]] — `to_ascii_*` are PG_FUNCTION_INFO_V1 entry
  points; note the `_COPY` arg-fetch idiom forced by in-place mutation.

## Potential issues

- **[ISSUE-undocumented-invariant: table length is an unchecked precondition for an OOB read]**
  `ascii.c:92` — `ascii[*x - range]` has no bounds check; correctness depends
  entirely on each inline translation string being `256 - range` bytes. The literals
  at `ascii.c:46/54/62/70` are not length-annotated, so an editor adding/trimming a
  character would silently introduce a one-byte OOB read. Severity: maybe.
- **[ISSUE-question: `ascii_safe_strlcpy` keeps byte 127 (DEL) as "printable ASCII"]**
  `ascii.c:187` — the range test is `32 <= ch && ch <= 127`, which admits 0x7F
  (DEL), a non-printable control char, while rejecting all other controls. Likely
  intentional (matches the `< 128` "is ASCII" notion) but inconsistent with the
  "printable" comment. Severity: nit.

## Confidence tag tally

- `[verified-by-code]`: 7
- `[from-comment]`: 4
- `[from-README]`: 0
- `[inferred]`: 0
- `[unverified]`: 0
