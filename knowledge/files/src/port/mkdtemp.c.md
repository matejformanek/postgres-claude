---
path: src/port/mkdtemp.c
anchor_sha: e18b0cb7344
loc: 293
depth: read
---

# src/port/mkdtemp.c

## Purpose

Provides `mkdtemp(char *path)` for platforms lacking it. Creates a
mode-0700 temporary directory by replacing the trailing `XXXXXX` of a
template path with characters derived from PID + a per-call counter, and
calling `mkdir(path, 0700)` until one succeeds. Code is a near-verbatim
import of NetBSD's `gettemp.c` + `mkdtemp.c` — the file header explicitly
notes OpenBSD's version "better resists denial-of-service attacks" but
has a cryptographic dependency PG didn't want. `[from-comment]`
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `char *mkdtemp(char *path)` | `mkdtemp.c:286` | Returns the template path on success (also written in-place), NULL on failure |

(Internal `GETTEMP` static — shared with file/dir variants in the NetBSD
original.)

## Internal landmarks

- `GETTEMP` (`:94`) — the workhorse, dispatches on `doopen`/`domkdir` flags.
  PG only uses the `domkdir = 1` path through `mkdtemp` at `:290`.
- Template substitution (`:115-138`) — walks back from the end of `path`
  counting trailing `X`s, replaces up to two with `xtra[2]` characters
  (`a..z` rotated each call), then fills the rest with PID digits least-sig
  first. Updates `xtra` (`:141-150`): `aa → ab → ac → ... → zz → aa`.
  Guarantees uniqueness across at least 676 calls in the same process.
  `[from-comment]`
- Directory-existence preflight (`:156-176`) — walks up the path looking
  for the parent directory and `stat`s it. If parent doesn't exist or isn't
  a directory, bail (otherwise the rest of the loop would spin forever
  trying to mkdir into nonexistent parent). `[from-comment]`
- Main retry loop (`:178-214`) — `mkdir(path, 0700)`. On `EEXIST`,
  bumps trailing characters via the wrap rule at `:199-213` (z→a, digit→a,
  else ++): brute-force search across `aa..zz` × (PID digit suffix) space.

## Invariants & gotchas

- **0700 mode is hardwired.** The whole reason `mkdtemp` exists separately
  from `mkstemp` is the directory perm guarantee — the directory is created
  with no group/world access, atomically (mkdir is atomic). A subsequent
  chmod could open a race window; this avoids it. `[verified-by-code]`
- **`xtra[]` static counter survives across calls.** Two threads calling
  `mkdtemp` concurrently could race on `xtra`. Glibc's mkdtemp uses
  thread-local state; this BSD-origin version doesn't. In practice PG calls
  it once at startup so the race is theoretical, but library users beware.
  `[from-comment]`
- **PID digit fill is deterministic per process.** Two processes with the
  same PID range would collide quickly. The `xtra` rotation is the only
  cross-process distinguisher; OS-level retries handle conflicts.
- Code is dual-licensed (BSD + NetBSD `gettemp.c` rider) — preserve the
  copyright block when modifying. `[from-comment]`

## Cross-refs

- `source/src/include/port.h` — `mkdtemp` declaration when
  `!HAVE_MKDTEMP`.
- `source/src/bin/initdb/initdb.c` — caller (creating temporary working
  directories).
- `knowledge/files/src/port/pgmkdirp.c.md` — sibling `mkdir -p` shim.
