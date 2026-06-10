---
path: src/include/common/file_perm.h
anchor_sha: 4b0bf0788b0
loc: 56
depth: skim
---

# file_perm.h

- **Source path:** `source/src/include/common/file_perm.h`
- **Lines:** 56
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/file_perm.c`.

## Purpose

Central definitions for the `pg_dir_create_mode` / `pg_file_create_mode` / `pg_mode_mask` globals — the **single security boundary** for the cluster's "owner-only" (0700) vs "group-readable" (0750) data-directory policy. `initdb -g`/`--allow-group-access` toggles between them and the mode is then persisted in `pg_control`-adjacent state by reading PGDATA's own mode at startup. [from-comment, file_perm.h:18-48]

## Public surface

- Mode-mask constants:
  - `PG_MODE_MASK_OWNER = S_IRWXG|S_IRWXO` (umask 0077). [verified-by-code, file_perm.h:24]
  - `PG_MODE_MASK_GROUP = S_IWGRP|S_IRWXO` (umask 0027). [verified-by-code, file_perm.h:29]
- File/dir mode constants:
  - `PG_DIR_MODE_OWNER = S_IRWXU` (0700), `PG_DIR_MODE_GROUP = S_IRWXU|S_IRGRP|S_IXGRP` (0750). [verified-by-code, file_perm.h:32-35]
  - `PG_FILE_MODE_OWNER = 0600`, `PG_FILE_MODE_GROUP = 0640`. [verified-by-code, file_perm.h:38-41]
- Globals: `pg_dir_create_mode`, `pg_file_create_mode`, `pg_mode_mask` (PGDLLIMPORT). [verified-by-code, file_perm.h:44-48]
- `SetDataDirectoryCreatePerm(dataDirMode)` — set the three globals from an octal mode. [verified-by-code, file_perm.h:51]
- `GetDataDirectoryCreatePerm(dataDir)` — stat dataDir and call the setter. [verified-by-code, file_perm.h:54]

## Phase D notes

See `file_perm.c.md` — security-critical defaults.

## Issues

[ISSUE-trust-boundary: `pg_dir_create_mode` / `pg_file_create_mode`
(`file_perm.h:44-45`) are PGDLLIMPORT globals — any extension or
backend code can rewrite them at runtime. The header has no
read-only contract (medium)] If an extension flips
pg_file_create_mode from 0600 to 0640 mid-cluster, every NEW file
inherits the looser mode, including `pg_authid` shadow files
written by autovacuum.

[ISSUE-trust-boundary: `GetDataDirectoryCreatePerm` (`file_perm.h:54`)
infers the cluster's policy by `stat()`ing the data directory at
startup; A6 finding: if an admin chmods the data dir between
startups, the inferred mode changes silently. Header has no warning
that this stat is the authoritative source-of-truth (low)]

[ISSUE-stale-todo: A6 cross-link — pg_authid hash files written
under `pg_file_create_mode` persist with whatever mode was active
when written; rotating from group-readable back to owner-only does
NOT chmod existing files (low)] Implementation in .c, but the
header could state the invariant.

## Cross-refs

- A6 `pg_upgrade` — pg_authid mode-persistence finding.
- Companion: `src/common/file_perm.c.md`.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=9`
