---
path: src/test/locale/test-ctype.c
anchor_sha: e18b0cb7344
loc: 79
depth: read
---

# src/test/locale/test-ctype.c

## Purpose

Self-contained diagnostic C program that exercises the `<ctype.h>`
classification macros (`isalnum`, `isalpha`, `iscntrl`, `isdigit`,
`islower`, `isgraph`, `isprint`, `ispunct`, `isspace`, `isupper`,
`isxdigit`) and the case-folding pair `toupper` / `tolower` against
whatever locale the environment selects (LC_ALL / LANG / LC_CTYPE).
For each of the 256 byte values 0..255 it prints a row showing how
the C library classifies that byte. Used by PG developers to sanity-
check libc / locale behavior on an exotic platform when collation
or upper/lower-casing bugs are suspected. NOT run by the automated
regression suite. `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `char *flag(int b)` | `test-ctype.c:32-40` | maps 0/non-zero to `" "/"+"` (or `"no"/"yes"` with `LONG_FLAG`) |
| `void describe_char(int c)` | `test-ctype.c:42-57` | prints one row for one codepoint |
| `int main()` | `test-ctype.c:59-79` | calls `setlocale(LC_ALL, "")`, then iterates 0..255 |

## Internal landmarks

- Default flag style is the compact `"+"` / `" "` — `LONG_FLAG` is
  `#undef`'d at `:30` so the verbose `"yes"/"no"` arm is dead code
  unless edited.
- The header row at `:74` lists column names; the format string at
  `:56` lines columns up using fixed widths (`%6s`, `%4c`).
- Bytes whose category-folded form is not printable get replaced with
  a space (`:49-54`) so the output stays grep-friendly.
- `setlocale(LC_ALL, "")` (`:65`) means: use the environment. If that
  fails the program prints a help message about LANG / LC_CTYPE
  and returns 1 (`:69-72`).

## Invariants & gotchas

- Standalone — no `postgres.h`, no libpq link. Compiles with a plain
  `cc test-ctype.c`. There is NO `Makefile` here for an automated
  build target; the file is shipped as a developer diagnostic.
  `[verified-by-code]`
- The `<ctype.h>` macros take an `int` that must be representable
  as an `unsigned char` or `EOF`; passing a signed `char` directly
  is undefined behavior on most libcs. This file does NOT trip that
  trap because it iterates `c` of type `short` from 0..255 and casts
  to `unsigned char` (`cp`, `up`, `lo` at `:45-47`) for printing.
- Copyright: PhiloSoft Design / Oleg Bartunov, NOT under standard PG
  license — but explicitly redistributable under the listed terms
  (`:11-15`).

## Cross-refs

- `knowledge/subsystems/locale-collation.md` — how PG drives libc
  locale calls in the backend.
- `knowledge/files/src/backend/utils/adt/pg_locale.c.md` — the actual
  in-backend locale machinery this diagnostic helps debug.
