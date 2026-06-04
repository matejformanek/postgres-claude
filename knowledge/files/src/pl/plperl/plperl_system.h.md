---
path: src/pl/plperl/plperl_system.h
anchor_sha: 4b0bf0788b0
loc: 197
---

# plperl_system.h

- **Source path:** `source/src/pl/plperl/plperl_system.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 197

## One-line summary

Wrapper header that includes Perl's `<EXTERN.h>` / `<perl.h>` (and
optionally `<XSUB.h>`) while shielding the surrounding PG code from
the macro mess Perl unconditionally inflicts on `printf`, `snprintf`,
`_`, `isnan`, and `bool`. Also conditionally pulls in `ppport.h`
for cross-version Perl portability.
[verified-by-code, plperl_system.h:1-15, 80-86, 175-183]

## Role in PG

`plperl.h` includes this header (plperl.h:25); no PG code should
include `<perl.h>` directly. The wrapper exists exclusively to:

1. Tell GCC that everything inside is a system header
   (`#pragma GCC system_header`, plperl_system.h:26-28), suppressing
   `-Wdeclaration-after-statement` and `-Wshadow=compatible-local`
   warnings that Perl headers trip.
2. `#undef` PG's `vsnprintf` / `snprintf` / `vsprintf` / `sprintf` /
   `vfprintf` / `fprintf` / `vprintf` / `printf` / `_` macros before
   `<perl.h>` so Perl's redefinitions take effect, then `#undef` them
   *again* afterwards and reinstall `pg_*` versions (plperl_system.h:45-57,
   123-156).
3. Pre-declare `HAS_BOOL 1` so Perl doesn't redefine `bool`
   (we already included `<stdbool.h>` via `c.h`)
   (plperl_system.h:75-78).
4. Enable `PERL_NO_GET_CONTEXT` (plperl_system.h:84) so per-call
   `dTHX` is required — keeps interpreter context explicit, which is
   what makes MULTIPLICITY-mode work.
5. Optionally bring in `<XSUB.h>` (plperl_system.h:93-121) only inside
   `.xs` translation units that `#define PG_NEED_PERL_XSUB_H` —
   regular `.c` files do NOT see XSUB.h because, on some platforms,
   it redefines libc functions in ways that don't play well with
   the backend.

## Public API / exports

Macros (defined here, visible to every TU that includes `plperl.h`):

- `PERL_UNUSED_DECL` → `pg_attribute_unused()`
  (plperl_system.h:37-39) — overrides Perl's broken version which
  doesn't satisfy GCC.
- `HAS_BOOL 1` (plperl_system.h:78) — Perl reads this and skips its
  own `bool` typedef.
- `PERL_NO_GET_CONTEXT` (plperl_system.h:84) — selects MULTIPLICITY-safe
  Perl API mode.
- `WIN32IO_IS_STDIO` on Windows (plperl_system.h:31-33) — stops Perl
  from hijacking stdio with its own implementations.
- `AV_SIZE_MAX` (plperl_system.h:191-195) — `SSize_t_MAX` on Perl ≥
  5.19.4 (where Perl widened array indices), `I32_MAX` on older Perl.
  This is the cap used by `plperl_spi_execute_fetch_result` to reject
  oversized result sets before `av_extend` (plperl.c:3223-3227).
- `HeUTF8` (plperl_system.h:179-183) — a fallback definition because
  ppport.h doesn't supply one. Reads the UTF-8 flag from a hash entry.
- `GvCV_set(gv, cv)` (plperl_system.h:186-188) — fallback definition;
  used in `plperl_trusted_init` to NULL out DynaLoader CVs
  (plperl.c:1015).
- `__builtin_expect` defined as `(expr)` under MSVC + Strawberry Perl
  ≥ 5.30 (plperl_system.h:71) — works around an interaction between
  the two.
- Re-installed `printf`-family macros at plperl_system.h:149-156:
  `vsnprintf → pg_vsnprintf`, `snprintf → pg_snprintf`, `sprintf →
  pg_sprintf`, `vsprintf → pg_vsprintf`, `vfprintf → pg_vfprintf`,
  `fprintf → pg_fprintf`, `vprintf → pg_vprintf`, `printf →
  pg_printf` (variadic). This must match `src/include/port.h`
  (plperl_system.h:123).
- Re-installed `_(x)` macro at plperl_system.h:166: `dgettext(TEXTDOMAIN, x)`
  (rather than core's `gettext(x)`) so loadable modules with their
  own `TEXTDOMAIN` translate against their own catalogs.
- `setlocale_perl(category, locale)` macro on Linux/macOS
  (plperl_system.h:307 in plperl.c is the corresponding `#else`) —
  in this header it's just the macro shim `setlocale_perl(a,b) →
  Perl_setlocale(a,b)`.

## Key invariants

- INV-1: Every PG `*printf` symbol in scope after this header must
  resolve to a `pg_*` variant. Perl's startup tries to redefine them
  (plperl_system.h:42-44, comment "Perl scribbles on our *printf
  macros"); the explicit `#undef`-then-redefine on the way out
  guarantees the final state matches `port.h`.
  [verified-by-code, plperl_system.h:123-156]
- INV-2: `bool` is the C99 `_Bool` (from `<stdbool.h>` via `c.h`),
  not Perl's int-typedef. Guaranteed by `#define HAS_BOOL 1` before
  `<perl.h>` (plperl_system.h:75-78).
- INV-3: `<XSUB.h>` is included iff `PG_NEED_PERL_XSUB_H` is defined.
  Only `SPI.xs` and `Util.xs` define this. Regular C code must NOT
  define it. The Win32 block at plperl_system.h:98-117 `#undef`s 18
  libc-and-socket functions (accept, bind, connect, fopen, fstat,
  kill, listen, lseek, lstat, mkdir, open, putenv, recv, rename,
  select, send, socket, stat, unlink) before letting XSUB.h
  redefine them, then no restoration — meaning XS code under WIN32
  uses Perl's versions.
- INV-4: `__inline__` is mapped to `inline` under MSVC
  (plperl_system.h:66) — needed because ActivePerl 5.18+ headers were
  MinGW-built and use GCC's `__inline__` keyword.

## Notable internals

### Why this is a separate header from `plperl.h`

The comment at plperl_system.h:5-15 explains: "No Postgres-specific
declarations should be put here. However, we do include some stuff
that is meant to prevent conflicts between our code and Perl." The
separation is so that the `system_header` pragma (which suppresses
warnings) covers *only* the Perl-headers chunk and not PG's own
declarations in `plperl.h`.

### Locale dance

Despite the file's purpose (header glue), the actual locale-save logic
lives in `plperl.c`'s `plperl_init_interp` (plperl.c:719-763,
864-870). This header only defines the macro shim
`setlocale_perl` for older WIN32 Perl, with the cross-platform
case using `Perl_setlocale` directly. [verified-by-code]

### isnan re-definition

Under MSVC, Perl may `#define isnan ...`. The header `#undef`s it
before perl.h (plperl_system.h:67-69) and re-installs `_isnan` after,
*only if perl didn't put one back* (plperl_system.h:168-173). The
ifdef chain assumes MSVC has `_isnan` available in `<float.h>`.

## Trusted vs untrusted boundary

This header is build-time only — it ships the same macros for trusted
and untrusted PL/Perl. The trust posture has no effect on which
perl-API macros are visible.

`PERL_NO_GET_CONTEXT` is the security-relevant flag here: it forces
every Perl-API call in plperl.c to take an explicit `pTHX` /
`dTHX`-derived context (plperl_system.h:81-84). This means a code
path that "happens to call into Perl" without first activating an
interpreter via `activate_interpreter` will not silently land in the
wrong interpreter — instead `dTHX` would dereference a stale
`my_perl` pointer and crash. The pattern enforces interpreter
discipline by making it a compile-time requirement.

## Issues spotted (inline)

- [ISSUE-defense-in-depth: WIN32 + XSUB.h block (plperl_system.h:97-117)
  unconditionally `#undef`s 18 libc/socket macros and never restores
  them. Code AFTER `#include <plperl_system.h>` in a `.xs` TU under
  Windows that subsequently tries to call e.g. `socket()` will see
  Perl's version, not PG's `win32_port.h` shim. The comment says
  this avoids warnings; the side-effect is silent — there's no
  `#pragma push_macro` / `pop_macro` pair (nit)]
  `source/src/pl/plperl/plperl_system.h:97-117`
- [ISSUE-api-shape: `AV_SIZE_MAX` fallback to `I32_MAX` for Perl <
  5.19.4 caps result-set size at 2^31-1 rows; that's fine, but the
  cap is silent — the caller `plperl_spi_execute_fetch_result`
  raises `ERRCODE_PROGRAM_LIMIT_EXCEEDED` only on overflow against
  this version-dependent constant, so the *limit* itself differs
  between Perl versions in a way that's invisible to users (nit)]
  `source/src/pl/plperl/plperl_system.h:190-195`,
  `source/src/pl/plperl/plperl.c:3223-3227`
- [ISSUE-documentation: the `#pragma GCC system_header` (plperl_system.h:27)
  suppresses ALL warnings inside this file. Bugs in this file's
  own macros (e.g. an off-by-one in `HeUTF8`) would be invisible
  to GCC warnings. The fallback `HeUTF8` macro has a triple-nested
  ternary that's harder to audit (nit)]
  `source/src/pl/plperl/plperl_system.h:26-28, 179-183`
- [ISSUE-defense-in-depth: `__builtin_expect(expr, val) (expr)`
  (plperl_system.h:71) silently drops the branch-prediction hint in
  MSVC builds; this affects compiled Perl module quality (Perl uses
  the hint heavily) but is a Perl-side perf concern, not a PG
  correctness issue (nit)]
  `source/src/pl/plperl/plperl_system.h:70-72`

## Cross-references

- `source/src/include/port.h` — the canonical pg_* printf macro set;
  must stay in sync with plperl_system.h:149-156.
- `source/src/include/c.h` — pulls in `<stdbool.h>`, which is the
  reason `HAS_BOOL 1` is safe here.
- `source/src/pl/plperl/ppport.h` — Perl's `Devel::PPPort`-generated
  cross-version portability shims. ~18k LOC of generated code, NOT
  PostgreSQL-authored; included unconditionally at
  plperl_system.h:176.
- `source/src/pl/plperl/plperl.h` — the only PG header that pulls in
  `plperl_system.h`.
- `source/src/pl/plperl/SPI.xs`, `Util.xs` — the only TUs that
  `#define PG_NEED_PERL_XSUB_H` before including plperl.h.
