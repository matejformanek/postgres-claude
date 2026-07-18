---
path: src/include/port/win32_msvc/sys/param.h
anchor_sha: e18b0cb7344
loc: 1
depth: read
---

# src/include/port/win32_msvc/sys/param.h

## Purpose

Empty placeholder header. POSIX `<sys/param.h>` is a grab-bag historically
holding `MAXPATHLEN`, `MAX`/`MIN` macros, `BSD`-flavour endian bits, etc.;
MSVC has no native equivalent. PG defines its own `MAXPGPATH` (1024) in
`pg_config_manual.h` and `Max`/`Min` macros in `c.h`, so nothing needs to
come from `<sys/param.h>` — this stub just satisfies the `#include`.
`[inferred]`

## Public symbols

None — file body is empty. `[verified-by-code]`

## Internal landmarks

One comment line: `/* src/include/port/win32_msvc/sys/param.h */`. No
guard, no declarations.

## Invariants & gotchas

- Active only on the Microsoft VC toolchain.
- If a translation unit needs `MAXPATHLEN`, use PG's `MAXPGPATH`
  (defined in `src/include/pg_config_manual.h`). Don't add it here.
- Do not delete: portability code that does `#include <sys/param.h>`
  on every platform needs this stub on MSVC.

## Cross-refs

- `knowledge/subsystems/port-layer.md` — Windows portability strategy.
- `src/include/pg_config_manual.h` — `MAXPGPATH` and similar limits.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../../subsystems/port.md)
