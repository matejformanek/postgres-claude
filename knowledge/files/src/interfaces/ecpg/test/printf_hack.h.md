---
path: src/interfaces/ecpg/test/printf_hack.h
anchor_sha: e18b0cb7344
loc: 29
depth: read
---

# src/interfaces/ecpg/test/printf_hack.h

## Purpose

Provides a single static helper, `print_double(double x)`, that produces
**platform-stable `%g` output for a double**. The ecpg regression suite
compares each test's stdout byte-for-byte against `expected/<name>.stdout`,
so any platform-dependent float formatting would cause spurious diff
failures. This shim lets tests that print computed doubles do so portably.
`[verified-by-code]` (`printf_hack.h:5-29`)

The actual portability problem it fixes: **Windows' `printf` emits
three-digit exponents** (e.g. `1e+005`) while every other libc emits two
digits (`1e+05`). On Windows, the helper rewrites the buffer in place to
drop the leading zero. On non-Windows, it is a direct `printf("%g", x)`.
`[from-comment]` (`printf_hack.h:1-3, 8-9`)

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `static void print_double(double x)` | `printf_hack.h:5-29` | header-only static; each `.pgc` that includes it gets its own copy |

## Internal landmarks

- **Windows path** (`printf_hack.h:8-25`): formats into a 128-byte
  `convert[]` buffer, then if the tail looks like `e[+-]0DD` (length ≥ 6,
  `e` at `vallen-5`, `0` at `vallen-3`), shifts the last two exponent
  digits left by one byte and re-NUL-terminates — collapsing `e+005` →
  `e+05`.
- **Non-Windows path** (`printf_hack.h:27`): plain `printf("%g", x)`.

## Invariants & gotchas

- `static` linkage on purpose. Multiple `.pgc` files include this header;
  giving the symbol external linkage would cause duplicate-definition
  linker errors when those test programs link together would be impossible
  — but the suite builds each test as a separate executable, so static
  here is just hygiene.
- The Windows rewrite assumes the exponent has the canonical form
  `e[+-]0DD`. A four-digit exponent (extreme values) would not be
  collapsed; in practice `%g` for a `double` never produces those.
- **Locale dependence is NOT handled here.** `%g` respects `LC_NUMERIC`,
  so a non-C locale would print `1,5` instead of `1.5`. The suite relies
  on `pg_regress` running tests under the default `C`/`POSIX` numeric
  locale.

## Cross-refs

- `knowledge/files/src/interfaces/ecpg/test/pg_regress_ecpg.c.md` — the
  driver whose byte-exact stdout comparison makes this hack necessary.
- `knowledge/files/src/test/regress/pg_regress.c.md` — base framework
  that sets the locale environment under which tests run.
