---
path: src/common/pgfnames.c
anchor_sha: 4b0bf0788b0
loc: 93
depth: read
---

# pgfnames.c

- **Source path:** `source/src/common/pgfnames.c`
- **Lines:** 93
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** none. No matching `pgfnames.h` exists at the moment; the prototype lives in `port.h`/`src/include/port.h`.

## Purpose

`opendir`/`readdir`/`closedir` wrapper that returns a `NULL`-terminated palloc'd array of `pstrdup`'d filenames (excluding `.` and `..`). Used by initdb, pg_resetwal, and other tools that need to walk a directory once. [from-comment, pgfnames.c:29-34]

## Role in PG

Both frontend and backend (via `#ifdef FRONTEND` macro switch around the logging). Same source, different `pg_log_warning` expansion.

## Key functions

- `pgfnames(path)` (36-76) — `palloc_array(char *, 200)` initial array, double on overflow; per-entry `pstrdup`. On `opendir` failure: log warning and return `NULL`. On `readdir` failure mid-walk: log warning, **but still return the partial array** (with `errno`-set warning logged). On `closedir` failure: log warning, still return array. [verified-by-code, pgfnames.c:36-76]
- `pgfnames_cleanup(filenames)` (84-93) — `pfree` each name then the array. Expects NULL terminator. [verified-by-code, pgfnames.c:84-93]

## State / globals

None.

## Phase D notes

- **Partial-success return.** If `readdir` errors mid-walk (e.g. removed dir, ENOENT during scan), `pgfnames` returns whatever it had with only a warning. Callers that depend on completeness (e.g. backup tools, rmtree) silently lose entries. [verified-by-code, pgfnames.c:67-70] [maybe — Phase D]
- **No symlink discrimination.** Just `d_name`; symlink targets are returned the same as regular files. The caller decides via subsequent `stat`. [verified-by-code, pgfnames.c:54-65]
- **No path-length cap.** A directory entry with `d_name` longer than what the caller's `MAXPGPATH` buffer holds will be returned by `pgfnames` (only the `d_name` itself is copied — the caller composes the full path). [inferred]
- **Initial buffer is 200 entries.** Doubling is unbounded; a hostile directory with N entries causes ~2N palloc on average. Backend `palloc` is `MaxAllocSize` capped; frontend `pg_malloc` calls `exit()` on OOM. So a DoS is bounded by `MaxAllocSize` / 8 bytes per pointer ≈ 128M entries. [verified-by-code, pgfnames.c:43,58-62] [maybe]

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=4 [inferred]=1 [maybe]=2`
