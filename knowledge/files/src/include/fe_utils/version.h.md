---
path: src/include/fe_utils/version.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 23
depth: read
---

# `src/include/fe_utils/version.h`

- **File:** `source/src/include/fe_utils/version.h` (23 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Declares the helper that reads a data directory's `PG_VERSION` file and returns its numeric
version, plus a macro to extract the major-version number from a `PG_VERSION_NUM`-style value.
Used by tools (e.g. pg_rewind, pg_upgrade-adjacent code) that must verify a cluster's catalog
version before operating on it. Implementation in [[knowledge/files/src/fe_utils/version.c]].
`[from-comment]` (:1-11)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `GET_PG_MAJORVERSION_NUM(v)` | :19 | `((v) / 10000)` — extract the major number from a packed version int. |
| `get_pg_version` | :21 | Read `<datadir>/PG_VERSION`; return `uint32` version + `*version_str`. |

## Internal landmarks

- The header guard is `PG_VERSION_H` (`:12`) — note this is the *fe_utils* version helper, not
  the generated `pg_config`-style `PG_VERSION` string macro; the name reuse is a mild trap when
  grepping. `[verified-by-code]`
- `GET_PG_MAJORVERSION_NUM` (`:19`) divides by 10000, matching the post-v10 two-part version
  scheme (major × 10000 + minor). `[verified-by-code]`

## Invariants & gotchas

- `get_pg_version` returns both a numeric version and a strdup'd `*version_str` (`:21`); the
  `.c` implementation copies the on-disk file length into a 64-byte buffer, which can copy
  uninitialized trailing bytes and may not NUL-terminate — bounded (no overflow), harmless on a
  well-formed `PG_VERSION`. Tracked in `knowledge/issues/fe_utils.md` row `version.c:64`. `[verified-by-code]`

## Cross-refs

- Implementation + the copy-length register row: [[knowledge/files/src/fe_utils/version.c]].
- Backend catalog-version analogue: `knowledge/idioms/catalog-conventions.md` (catversion).

## Potential issues

None new at the header level — the `memcpy`-length nuance is tracked against `version.c` in
`knowledge/issues/fe_utils.md`. The `PG_VERSION_H` guard-name reuse is noted above as a grep
trap (not an issue).
