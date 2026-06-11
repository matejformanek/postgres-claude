# `src/backend/utils/mb/wstrcmp.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~47
- **Source:** `source/src/backend/utils/mb/wstrcmp.c`

One-function file derived from Berkeley/Chris-Torek BSD `strcmp`,
specialised to compare a `char *` against a `pg_wchar *` (4-byte wide
character) in lockstep until a difference or a shared NUL terminator.
The header carries the BSD 3-clause notice unchanged. Compiled into
both frontend and backend (uses `postgres_fe.h`). [verified-by-code]

## API

- `pg_char_and_wchar_strcmp(const char *s1, const pg_wchar *s2)` —
  returns `*(unsigned char *)s1 - *(pg_wchar *)(s2-1)` at the first
  mismatched position, or 0 if both strings end together. The advance
  pattern is the canonical "compare then increment" BSD loop. [verified-by-code]

## Notable invariants / details

- `s1` is read as `unsigned char` for the return-value subtraction
  (line 46) so the result sign is well-defined when `s1` contains
  bytes ≥ 0x80, but the loop comparison at line 43 casts via
  `(pg_wchar) *s1` — a *signed*-to-unsigned conversion happens
  implicitly through the value of `*s1` if `char` is signed on the
  platform. For ASCII strings this is fine, but for high-bit bytes
  the loop comparison and the return-difference use slightly
  different conversion paths. [inferred] [ISSUE-correctness:
  loop compares signed-promoted `*s1` against `pg_wchar`; return
  uses unsigned cast — asymmetric promotion for bytes ≥ 0x80 (nit)]
- No length cap: caller must guarantee one of the strings is NUL
  terminated; otherwise read past end. [inferred]
  [ISSUE-undocumented-invariant: caller responsibility for NUL
  termination is implicit (nit)]
- The only in-tree caller for this routine is historically inside
  `regc_pg_locale.c` / regex parts; verifying current callers needs a
  grep. [unverified]

## Potential issues

- File-line: wstrcmp.c:43 vs :46. Asymmetric char-to-wchar promotion
  may yield a positive vs negative result depending on the platform's
  signed-char setting if a high-bit byte sits in `s1`. In practice
  PG's mb code uses unsigned byte interpretation throughout. [ISSUE-correctness:
  signed-vs-unsigned promotion mismatch (nit)]
