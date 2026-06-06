---
path: src/include/fe_utils/archive.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 21
depth: read
---

# `src/include/fe_utils/archive.h`

- **File:** `source/src/include/fe_utils/archive.h` (21 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Declares the single frontend helper for fetching a WAL segment from a WAL archive by running
the configured `restore_command` — used by pg_rewind (and pg_combinebackup-adjacent code) when
it needs a WAL file not present locally. Header guard is `FE_ARCHIVE_H` (the `archive.h`
filename is shared conceptually with the backend's archiving, but this is the frontend variant).
Implementation in [[knowledge/files/src/fe_utils/archive.c]]. `[from-comment]` (:1-12)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `RestoreArchivedFile` | :16 | Run `restoreCommand` to fetch `xlogfname` into `path`; verify size; return result. |

## Internal landmarks

- `RestoreArchivedFile` (`:16-19`) takes `expectedSize` (`:18`) so the caller can assert the
  retrieved segment is the right length — a guard against a partially-restored or wrong file. `[verified-by-code]`
- The function takes the raw `restoreCommand` string (`:19`); the `.c` implementation expands
  the `%f`/`%p` placeholders and runs it via the shell. `[inferred]`

## Invariants & gotchas

- `restoreCommand` is run through a shell with placeholder substitution — the command itself is
  operator-configured (from `postgresql.conf`/CLI), so it is trusted input, but the placeholder
  expansion is the same percent-substitution family the A5 `percentrepl.c` finding flagged as
  doing no shell escaping. Here the inputs (`%f` = a validated WAL segment name) are
  constrained, so the surface is narrow. `[inferred]`
- `expectedSize` of `0` / `-1` conventions for "don't check" live in the `.c`; callers should
  pass the real expected segment size when known. `[inferred]`

## Cross-refs

- Implementation: [[knowledge/files/src/fe_utils/archive.c]].
- Percent-substitution shell-escaping theme: `knowledge/issues/common.md` (A5 `percentrepl.c`).
- Backend WAL/restore context: `knowledge/architecture/wal.md`.

## Potential issues

None new at the header level — the `restore_command` percent-substitution shell surface is an
operator-trusted, narrow-input path; cross-linked to the A5 `percentrepl.c` register entry for
the general pattern.
