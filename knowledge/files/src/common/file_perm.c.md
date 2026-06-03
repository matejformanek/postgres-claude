---
path: src/common/file_perm.c
anchor_sha: 4b0bf0788b0
loc: 87
depth: read
---

# file_perm.c

- **Source path:** `source/src/common/file_perm.c`
- **Lines:** 87
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/file_perm.h`.

## Purpose

Implements the trio `pg_dir_create_mode` / `pg_file_create_mode` / `pg_mode_mask` and the two setters that flip them between owner-only (0700/0600/0077) and group-read (0750/0640/0027) policies. These globals are consulted by every PG-wide "create a file/dir under PGDATA" call site (backend `mkdir`/`open`, frontend tools mirroring backend behavior, plus initdb/pg_basebackup that pre-create the tree). [from-comment, file_perm.c:21-32]

## Role in PG

Both frontend and backend (no `#ifdef FRONTEND` around the setter), but `GetDataDirectoryCreatePerm` is frontend-only (line 52-87). Backend sets the globals once during `PostmasterMain`/`SubPostmasterMain` from `data_directory_mode` derived at startup.

## Key functions

- `SetDataDirectoryCreatePerm(dataDirMode)` (33-50) — if `(dataDir mode & PG_DIR_MODE_GROUP) == PG_DIR_MODE_GROUP` (i.e. group r+x bits both set), pick the GROUP triple; **else** pick the OWNER triple. The check is "if exactly the GROUP mode bits are set" — extra bits in the input mode (world-read, set-gid, etc.) are tolerated for the GROUP path; missing group bits demote to OWNER. [verified-by-code, file_perm.c:37-49]
- `GetDataDirectoryCreatePerm(dataDir)` (65-84) — frontend: `stat()` the directory; on Unix call the setter with `statBuf.st_mode`; on Windows/Cygwin skip the setter but still return whether the stat succeeded. [verified-by-code, file_perm.c:65-84]

## State / globals

- `pg_dir_create_mode = PG_DIR_MODE_OWNER` (0700). [verified-by-code, file_perm.c:18]
- `pg_file_create_mode = PG_FILE_MODE_OWNER` (0600). [verified-by-code, file_perm.c:19]
- `pg_mode_mask = PG_MODE_MASK_OWNER` (0077). [verified-by-code, file_perm.c:25]

Initial values are the safer defaults. The setter is the only path to relax them.

## Phase D notes

- **Default is restrictive.** A program that *never* calls `Set*`/`Get*DataDirectoryCreatePerm` will create files at 0600/0700 with umask 0077 — safe-by-default. [verified-by-code, file_perm.c:18-25]
- **`GetDataDirectoryCreatePerm` returns true on Windows even though it does not set the globals** — the comment at line 60-63 explains this is intentional, but the caller has no way to know the globals were not updated. A future port (Cygwin-like Unix-y Windows) could silently behave as the owner-only default. [verified-by-code, file_perm.c:78-83] [maybe — Phase D]
- **TOCTOU.** A hostile coexisting process that can write to PGDATA's parent could chmod the data dir between the stat and the open of a file/dir inside it. PG generally trusts PGDATA ownership; this is the same trust model used elsewhere. [inferred] [maybe]
- **The "exactly group bits set" check** is more permissive than it looks: an admin who chmoded PGDATA to 0775 (world-read!) would still trigger the GROUP path because `(0775 & 0750) == 0750`. World-bits in PGDATA itself are an admin error — there is no in-source check that rejects them. [verified-by-code, file_perm.c:37] [ISSUE-undocumented-invariant: SetDataDirectoryCreatePerm only checks PG_DIR_MODE_GROUP bits, not the absence of world bits; a 0775 PGDATA picks the GROUP triple silently (maybe)]

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=7 [inferred]=1 [maybe]=3`
