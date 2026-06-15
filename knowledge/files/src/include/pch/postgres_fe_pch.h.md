---
path: src/include/pch/postgres_fe_pch.h
anchor_sha: e18b0cb7344
loc: 1
depth: read
---

# src/include/pch/postgres_fe_pch.h

## Purpose

One-line precompiled-header anchor for **frontend** translation units. The
file consists solely of `#include "postgres_fe.h"` (`:1`). When the build
system is asked to produce a PCH for frontend code (psql, pg_dump, libpq
clients, pg_basebackup, …), it compiles this header once and reuses the
resulting AST on every subsequent .c that starts with the same include.
Keeping the PCH input down to a single canonical include avoids the
combinatorial-PCH problem (one PCH per unique include prefix) and makes the
cache effective. `[verified-by-code]`

## Public symbols

None — file is a build artifact, not an API surface. It exists to be the
argument to `gcc -include` / `clang -include-pch` / `msvc /Yu`.

## Internal landmarks

Single `#include "postgres_fe.h"` directive. `postgres_fe.h` is the
mandatory frontend prologue (defines `FRONTEND`, then includes `c.h`).

## Invariants & gotchas

- **Don't add includes here.** The whole point is that this file mirrors the
  *minimal* prefix every frontend .c is required to start with
  (`postgres_fe.h` as the very first PG include). Anything else would force
  every frontend TU to re-parse the same wider header set, defeating the PCH
  benefit, and would silently introduce includes that frontend code is not
  supposed to assume.
- **Backend code must not use this PCH.** Backend TUs start with
  `postgres.h`, not `postgres_fe.h`, so they need the sibling
  `postgres_pch.h` instead. Cross-wiring leaks `FRONTEND` into the backend
  build and breaks the FE/BE separation.
- **PCH is opt-in via meson** (`-Db_pch=true` etc.). Builds without PCH
  ignore this file entirely.

## Cross-refs

- `knowledge/files/src/include/pch/postgres_pch.h.md` — backend equivalent.
- `knowledge/files/src/include/pch/c_pch.h.md` — minimal `c.h`-only PCH for
  shared library code.
- `knowledge/files/src/include/postgres_fe.h.md` — the actual prologue this
  anchor pulls in.
