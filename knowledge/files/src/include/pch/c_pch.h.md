---
path: src/include/pch/c_pch.h
anchor_sha: e18b0cb7344
loc: 1
depth: read
---

# src/include/pch/c_pch.h

## Purpose

One-line precompiled-header anchor for translation units that need only the
**shared `c.h` prologue**, not the FE or BE wrapper around it. The file is
`#include "c.h"` (`:1`). Used by the small set of source files that compile
with neither `FRONTEND` nor the full backend Datum/Node machinery — chiefly
`src/common/` and `src/port/` sources that link into both libpq and the
backend, plus a handful of self-contained utilities. `[verified-by-code]`

## Public symbols

None — build artifact, not an API.

## Internal landmarks

Single `#include "c.h"` directive. `c.h` is PG's portability prologue:
`<stdio.h>`/`<stdlib.h>`/`<stdint.h>` plus `pg_config*.h`, `Assert`, basic
typedefs (`int32`, `bool`, `Size`), `pg_attribute_*` macros, and the
platform-detection cascade.

## Invariants & gotchas

- **Don't add includes here.** The whole point of this anchor is to mirror
  the *minimum* every common/port .c can rely on. Bringing in `postgres.h`
  or `postgres_fe.h` would force `FRONTEND` one way or the other and break
  the dual-target compile of common/port code.
- **PCH choice is per-target.** A given .c file matches at most one of
  `c_pch.h` / `postgres_pch.h` / `postgres_fe_pch.h`; the meson rule for
  the library / executable decides which PCH to use based on whether
  `FRONTEND` is defined for that target. `[verified-by-code]`
- **PCH is opt-in via meson** (`-Db_pch=true`). Default builds ignore.

## Cross-refs

- `knowledge/files/src/include/pch/postgres_pch.h.md` — backend equivalent.
- `knowledge/files/src/include/pch/postgres_fe_pch.h.md` — frontend
  equivalent.
- `knowledge/files/src/include/c.h.md` — the actual prologue this anchor
  pulls in.
