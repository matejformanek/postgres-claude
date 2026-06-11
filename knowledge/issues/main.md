# Issues — `main`

Per-subsystem issue register for `src/backend/main/main.c` — the
`int main()` stub for the `postgres` executable and its tiny
dispatch infrastructure.

**Parent subsystem docs:**
- `knowledge/files/src/backend/main/main.c.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | main/main.c:113-114 | undocumented-invariant | nit | `MyProcPid = getpid()` MUST precede `MemoryContextInit()` (the latter's diagnostic paths want `MyProcPid`). Not documented inline | open | knowledge/files/src/backend/main/main.c.md §Potential issues |
| 2026-06-11 | main/main.c:279-282 | stale-todo | nit | XXX "code here is proof that the platform in question is too brain-dead" — Windows-specific cleanups in `startup_hacks`. Not actionable | open | knowledge/files/src/backend/main/main.c.md §Potential issues |
| 2026-06-11 | main/main.c:383-385 | stale-todo | nit | XXX about non-ASCII help output on Windows console code pages | open | knowledge/files/src/backend/main/main.c.md §Potential issues |
| 2026-06-11 | main/main.c:189-191 | style | nit | The `-C VAR` root-check carve-out is silently positional (must be argv[1]). User running `postgres -D /path -C foo` as root gets a confusing rejection with no hint that placement matters | open | knowledge/files/src/backend/main/main.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- Tiny dispatch table: enum `DispatchOption` + `DispatchOptionNames[]`
  string array, wired together by `parse_dispatch_option`. Names are
  `check`, `boot`, `forkchild`, `describe-config`, `single`; default
  (no name) is `DISPATCH_POSTMASTER`.
- `DISPATCH_FORKCHILD` only reachable in `EXEC_BACKEND` builds
  (Windows). On non-EXEC_BACKEND it Asserts(false).
- `__ubsan_default_options` is a weak symbol the sanitizer library
  picks up; gated on a `reached_main` flag to guard against libsan
  initialising before libc, which would otherwise recurse.
- Locale invariants: postmaster forces `LC_COLLATE/MONETARY/NUMERIC/TIME`
  to `C` and absorbs the environment for `LC_CTYPE`/`LC_MESSAGES`.
  Per-DB collation is applied later in `InitPostgres`.
