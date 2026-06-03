---
path: src/common/rmtree.c
anchor_sha: 4b0bf0788b0
loc: 132
depth: read
---

# rmtree.c

- **Source path:** `source/src/common/rmtree.c`
- **Lines:** 132
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/file_utils.c` (provides `get_dirent_type`), `storage/fd.c` (`AllocateDir`/`FreeDir` in the backend path).

## Purpose

Recursive `rm -rf` for use by initdb (rollback on error), `pg_upgrade`, `pg_rewind`, pg_basebackup cleanup, and a handful of backend recovery paths. **Same source compiles for backend and frontend** — `OPENDIR`/`CLOSEDIR` macros expand to `AllocateDir`/`FreeDir` in the backend (which respect the limited per-backend dir-handle pool) and to `opendir`/`closedir` in the frontend. [verified-by-code, rmtree.c:25-36]

## Role in PG

Both. Backend callers include `RemoveBackupHistoryFile`, tablespace cleanup, `pg_dropcluster` flows.

## Key functions

- `rmtree(path, rmtopdir)` (49-132). Two-pass walk: first pass deletes regular files via `unlink` and collects subdirectory names into a palloc'd array (`dirnames`, doubling from 8 entries), all while *still holding the parent directory's handle*. After `CLOSEDIR`, second pass recurses into each subdir. This sequencing is deliberate ("avoid using more than one file descriptor at a time", line 82-85) and matters for backend callers because `AllocateDir` charges against a tight pool. [verified-by-code, rmtree.c:49-132]

## State / globals

None. All scratch state is on the stack or in palloc'd `dirnames`.

## Phase D notes

- **`get_dirent_type(pathbuf, de, false, LOG_LEVEL)` passes `false` for `look_through_symlinks`.** [verified-by-code, rmtree.c:75] This means a **symlink inside the tree is classified as `PGFILETYPE_LNK`** and falls into the `default:` branch, which `unlink`s the symlink itself rather than recursing through it. So rmtree does NOT follow symlinks out of the tree — good. [inferred + verified, rmtree.c:75,94-100]
- **But on the top-level call**, `path` itself is `opendir()`'d without symlink check (line 60). If the caller passes a symlink-to-elsewhere, `opendir` follows it transparently and rmtree will then walk that elsewhere tree. The caller is responsible for canonicalizing the input. [verified-by-code, rmtree.c:60] [maybe — Phase D]
- **ENOENT on unlink is silently swallowed** (`errno != ENOENT` check at line 95). Race with another deleter is treated as success. [verified-by-code, rmtree.c:95]
- **Partial-failure semantics.** rmtree returns `false` if anything failed but **continues**. A hostile actor who creates a non-removable subfile mid-walk only delays cleanup; it doesn't abort. The caller cannot tell which files survived. [verified-by-code, rmtree.c:97-99,107]
- **Recursive stack depth.** No depth bound — a deeply-nested directory tree could blow the C stack. Filesystems have their own depth limits but symlinked loops (avoided per above) would otherwise be problematic. [inferred] [maybe]
- **Race with concurrent `mkdir`.** A new file/dir created in `path` after our `readdir` finishes will be missed; the final `rmdir(path)` at line 122 will then fail with ENOTEMPTY and rmtree returns false. Standard rm semantics. [verified-by-code, rmtree.c:120-127]

## Confidence tag tally
`[verified-by-code]=10 [inferred]=2 [maybe]=2`
