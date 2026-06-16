# `src/include/portability/mem.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~46
- **Source:** `source/src/include/portability/mem.h`

Portability shims around the SysV-IPC and mmap flag constants used
by `shmem_*` setup code. Provides safe defaults for missing
`MAP_ANONYMOUS`, `MAP_HASSEMAPHORE`, `MAP_NOSYNC`, `MAP_FAILED`, and
the SysV `SHM_SHARE_MMU` (Solaris intimate shared memory).
[verified-by-code]

## API / declarations

- `IPCProtection = 0600` — owner-only access mode for `shmget`.
- `PG_SHMAT_FLAGS` — `SHM_SHARE_MMU` on Solaris, else 0.
- `MAP_ANONYMOUS` — alias to `MAP_ANON` where the latter is the
  spelling (e.g. BSDs).
- `MAP_HASSEMAPHORE` — 0 on Linux (not needed); preserved as a
  BSD-derived flag.
- `MAP_NOSYNC` — 0 elsewhere; on FreeBSD-style systems prevents
  "gratuitous" flush of dirty mmap pages.
- `MAP_FAILED` — fallback `((void *) -1)` for "really old systems".

## Notable invariants / details

- `IPCProtection = 0600` is the PG-wide policy for shared memory
  segments — owner only, no group/world access. Matches the
  "no PG runs as root" assumption.
- Order of these defaults vs platform `<sys/mman.h>` — caller must
  include `<sys/mman.h>` BEFORE this header, otherwise the `#ifndef
  MAP_*` guards will fire even on platforms that DO have them.
  [inferred]

## Potential issues

- "Some really old systems don't define `MAP_FAILED`" — the
  fallback is correct but the comment hasn't been re-evaluated in
  years; on a modern POSIX system this is dead code.
  [ISSUE-stale-todo: MAP_FAILED fallback likely unreachable
  (nit)]
- File is silent on whether `MAP_HASSEMAPHORE` actually does
  anything on BSD-derived systems any more. [ISSUE-doc-drift:
  MAP_HASSEMAPHORE current-platform impact (nit)]
- `IPCProtection 0600` octal is correct but unlabeled — easy to
  misread as decimal 600. [ISSUE-style: 0600 vs S_IRUSR|S_IWUSR
  spelling (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../../issues/include-misc.md)
<!-- issues:auto:end -->
