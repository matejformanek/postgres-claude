---
path: src/port/pgstrcasecmp.c
anchor_sha: e18b0cb7344
loc: 125
depth: read
---

# src/port/pgstrcasecmp.c

## Purpose

Locale-independent ASCII case-folding comparison primitives. PG **must not**
use libc `strcasecmp` for SQL identifier folding, keyword matching, or
catalog name lookups: libc's behavior shifts under the active LC_CTYPE locale
(famously, Turkish locale folds `i ↔ I` differently), which would silently
change which identifiers match — a security-relevant invariant. This file
implements the SQL-style compromise: ASCII letters use a hard-wired
`'a' - 'A'` shift, only high-bit-set bytes consult `tolower()`/`isupper()`.
The header comment notes the code must match `downcase_truncate_identifier()`
in `scansup.c`. `[from-comment]` `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pg_strcasecmp(const char *s1, const char *s2)` | `pgstrcasecmp.c:32` | Null-terminated case-independent compare |
| `int pg_strncasecmp(const char *s1, const char *s2, size_t n)` | `pgstrcasecmp.c:65` | Bounded variant |
| `unsigned char pg_toupper(unsigned char ch)` | `pgstrcasecmp.c:101` | Single-char fold to upper |
| `unsigned char pg_tolower(unsigned char ch)` | `pgstrcasecmp.c:118` | Single-char fold to lower |

## Internal landmarks

- Inner loop (`:36-53`, `:69-86`) — fast path on `ch1 == ch2`; only on
  mismatch does it do the per-byte ASCII or high-bit fold. The two branches
  are independent so two distinct locale-dependent calls can happen per
  mismatched pair, but only when both bytes are >= 0x80.
- The high-bit arm uses libc `tolower()`/`toupper()`, so for non-ASCII bytes
  this **is** locale-dependent. Pure-ASCII identifiers (the common case)
  remain locale-independent. `[verified-by-code]`

## Invariants & gotchas

- **Catalog and keyword name comparisons use these, never libc strcasecmp.**
  Identifier folding for `Foo` ≡ `foo` ≡ `FOO` is part of SQL's case rules;
  if it depended on LC_CTYPE, a database created in en_US could fail to
  resolve identifiers when reopened in tr_TR. The hard ASCII shift is the
  fix.
- `pg_toupper`/`pg_tolower` are safe to call on any byte (unlike libc's
  versions on some platforms which require `isupper()`-true input). The
  header comment flags them as "a bit bogus for multibyte character sets" —
  these are byte-level, not codepoint-level. `[from-comment]`
- The match-with-scansup invariant means changes to identifier folding rules
  must touch both this file and `src/backend/parser/scansup.c`. `[from-comment]`

## Cross-refs

- `source/src/backend/parser/scansup.c` — `downcase_truncate_identifier`.
- `source/src/include/port.h` — prototypes.
- `knowledge/idioms/` — identifier-folding invariant.
