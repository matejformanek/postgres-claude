---
path: src/include/pch/postgres_pch.h
anchor_sha: e18b0cb7344
loc: 1
depth: read
---

# src/include/pch/postgres_pch.h

## Purpose

One-line precompiled-header anchor for **backend** translation units. The
file is `#include "postgres.h"` (`:1`). The build system precompiles this
header once and reuses the AST when compiling every backend .c that starts
with the mandatory `#include "postgres.h"` first line. This is the bulk of
the source tree: `src/backend/**`, plus extensions and contrib modules built
in the backend style. `[verified-by-code]`

## Public symbols

None — build artifact, not an API.

## Internal landmarks

Single `#include "postgres.h"` directive. `postgres.h` is the canonical
backend prologue: defines `BUILDING_DLL` discipline, pulls `c.h` plus the
Datum/varlena/Node infrastructure backend code expects.

## Invariants & gotchas

- **Don't add includes here.** Backend code is *required* to start with
  exactly `#include "postgres.h"`, and `postgres.h` already drags in the
  shared prologue. Anything added to this PCH anchor would either be
  redundant (already pulled in by `postgres.h`) or would change the
  visibility set of every backend TU, breaking `cpluspluscheck` and PCH
  consistency rules. `[verified-by-code]`
- **Frontend code must not use this PCH.** Frontend TUs start with
  `postgres_fe.h`, never `postgres.h`. Pulling in this PCH from frontend
  code would compile the backend-only Datum/Node machinery into client
  binaries.
- **PCH is opt-in via meson** (`-Db_pch=true`). Non-PCH builds ignore this
  file.

## Cross-refs

- `knowledge/files/src/include/pch/postgres_fe_pch.h.md` — frontend
  equivalent.
- `knowledge/files/src/include/pch/c_pch.h.md` — `c.h`-only minimal PCH.
- `knowledge/files/src/include/postgres.h.md` — the actual prologue this
  anchor pulls in.
