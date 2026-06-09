# `utils/pg_locale_c.h` — hard-wired C/POSIX character-class table

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/pg_locale_c.h`)

## Role

Static 128-entry lookup table mapping each ASCII code point to a bitmask of
character classes (`PG_ISDIGIT`, `PG_ISALPHA`, `PG_ISALNUM`, `PG_ISUPPER`,
`PG_ISLOWER`, `PG_ISGRAPH`, `PG_ISPRINT`, `PG_ISPUNCT`, `PG_ISSPACE`). Used
by the C/POSIX locale fast path to avoid calling libc `isXxx()` (which
depends on the process locale and the lc-ctype category, neither of which
the C-locale fast path wants to consult).

## Public API

- 8 class bits — `source/src/include/utils/pg_locale_c.h:19-27`:
  `PG_ISDIGIT 0x01`, `PG_ISALPHA 0x02`, `PG_ISALNUM (PG_ISDIGIT|PG_ISALPHA)`,
  `PG_ISUPPER 0x04`, `PG_ISLOWER 0x08`, `PG_ISGRAPH 0x10`, `PG_ISPRINT 0x20`,
  `PG_ISPUNCT 0x40`, `PG_ISSPACE 0x80`.
- `static const unsigned char pg_char_properties[128]` — `:29-158`. Static
  (file-scope per translation unit that includes this header), so
  `#include`s effectively get private copies.

## Invariants

- Indexed by raw `unsigned char`; only the low 128 entries are populated.
  Callers MUST gate on `c < 128` before lookup. [inferred from array size]
- Mapping matches POSIX C locale semantics: digits 0-9, letters A-Z/a-z,
  punctuation, and the ASCII whitespace set `{\t \n \v \f \r ' '}`.
  [verified-by-code, `:39-43,62`]
- The space character (0x20) is both `PG_ISPRINT` and `PG_ISSPACE` but
  NOT `PG_ISGRAPH` — matches POSIX. [verified-by-code, `:62`]
- DEL (0x7F) has zero class bits. [verified-by-code, `:157`]
- Header has no .c — the table is `static const` and inlined per TU,
  so every source file that includes it gets a private 128-byte copy.
  Trades a little binary size for branch-free access. [inferred]

## Notable internals

128-byte lookup. Trivial to verify by inspection but extremely hot — used
in every C/POSIX-locale comparison and in many parser fast paths.

## Trust-boundary / Phase D surface

- `static const` inside a header means multiple TUs get the same table
  copied; benign but bloats `.rodata`. Not a security issue.
  [ISSUE-resource: every TU including pg_locale_c.h gets its own 128-byte
  `pg_char_properties` copy (nit)]
- Callers must not pass `unsigned char > 127`; nothing in the header
  enforces this — a `signed char` sign-extended to int and indexed yields
  out-of-bounds read for any byte ≥ 0x80. [ISSUE-correctness: no array-
  bounds guard; callers must check `c < 128` (maybe)]
- The table encodes a fixed view of "what C locale means" — any divergence
  from libc's actual C locale (e.g. an exotic libc) would not be visible
  here. PG explicitly chooses this hard-wiring to make the C locale
  identical everywhere. [from-naming inference] — not an ISSUE, a
  deliberate decision.

## Cross-refs

- `knowledge/files/src/include/utils/pg_locale.h.md` — the broader locale
  abstraction this header backstops.

## Issues

1. [ISSUE-correctness: no bounds guard for `c >= 128`; callers must check
   themselves (maybe)] — `source/src/include/utils/pg_locale_c.h:29`.
2. [ISSUE-resource: `static const` table copied per translation unit
   (nit)] — `source/src/include/utils/pg_locale_c.h:29`.
