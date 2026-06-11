# `src/backend/utils/mb/wstrncmp.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~77
- **Source:** `source/src/backend/utils/mb/wstrncmp.c`

Three small BSD-derived (FreeBSD 2.2.1) wide-character utilities:
length-bounded compare of two `pg_wchar` strings, length-bounded
compare of `char` against `pg_wchar`, and a strlen for `pg_wchar`.
Compiled into both frontend and backend (uses `postgres_fe.h`). [verified-by-code]

## API

- `pg_wchar_strncmp(const pg_wchar *s1, const pg_wchar *s2, size_t n)`
  — `strncmp(3)` semantics over 4-byte wide chars. Stops at `n`
  comparisons or first NUL. [verified-by-code]
- `pg_char_and_wchar_strncmp(const char *s1, const pg_wchar *s2,
  size_t n)` — same, with `s1` as narrow string; widens each `*s1`
  through `(unsigned char)` cast then `(pg_wchar)` before comparing,
  fixing the signed-char ambiguity present in `wstrcmp.c`. [verified-by-code]
- `pg_wchar_strlen(const pg_wchar *str)` — count of non-NUL `pg_wchar`s
  before the first 0. [verified-by-code]

## Notable invariants / details

- Both bounded compares are correct on `n == 0` (return 0 without
  touching `s1`/`s2`). [verified-by-code]
- The 2-string version (`pg_wchar_strncmp`) does *not* go through an
  unsigned cast: since both operands are `pg_wchar` (typically
  `unsigned int`), the subtraction at line 47 is well-defined.
  [verified-by-code]
- Note the slightly tricky post-increment pattern: `*s1 != *s2++`
  evaluates `*s1` (current pos), increments `s2` to next pos, so the
  later `s2 - 1` walks back to the just-compared position. Matches
  the BSD original and is intentional. [verified-by-code]
- No CHECK_FOR_INTERRUPTS; trivial routine, but `pg_wchar_strlen` on
  an unbounded string is O(n) uncancellable if a caller ever fed it
  attacker-supplied wide data without a known terminator. In practice
  PG callers always control the wide string. [inferred]

## Potential issues

- File-line: wstrncmp.c:39-52, 54-67. The "fix signed-char by casting
  via `(unsigned char)`" pattern used in `pg_char_and_wchar_strncmp`
  is **absent** in `wstrcmp.c`'s unbounded variant — see issue there.
  [ISSUE-doc-drift: divergence between the two sibling files in how
  they widen `char` → `pg_wchar` (nit)]
