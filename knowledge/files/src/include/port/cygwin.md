# `src/include/port/cygwin.h`

## Role

Cygwin compatibility shim. Two responsibilities:

1. Define `PGDLLIMPORT` to `__declspec(dllimport)` or `dllexport`
   depending on whether we're building the core backend or a loadable
   module — Cygwin uses Windows DLL semantics
   `[verified-by-code]` `source/src/include/port/cygwin.h:5-15`.
2. Declare `HAVE_BUGGY_STRTOF 1` because Cygwin's `strtof()` is just
   `(float)strtod()` — produces misrounding and silent over/underflow
   `[from-comment]` `source/src/include/port/cygwin.h:17-23`. PG's
   `strtof` wrapper restores the error checks (misrounding remains).

## Public API

- `PGDLLIMPORT` — backend-only (`#ifndef FRONTEND`).
- `HAVE_BUGGY_STRTOF 1`.

## Invariants

1. Backend-only `PGDLLIMPORT`; frontend code on Cygwin uses no
   markings (works because exec model is different)
   `[verified-by-code]` `source/src/include/port/cygwin.h:9,15`.
2. `BUILDING_DLL` controls dllexport vs dllimport — set when building
   `postgres.exe`, unset when building a module.

## Cross-refs

- `source/src/include/port/win32.h` — parallel `PGDLLIMPORT`
  treatment for native Windows.
- `source/src/port/strtof.c` — the wrapper that consumes
  `HAVE_BUGGY_STRTOF`.

## Issues

- (none)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
