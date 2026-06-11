# `src/include/postmaster/fork_process.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~18
- **Source:** `source/src/include/postmaster/fork_process.h`

Minimal export of the single `fork_process()` wrapper that the
postmaster (and a few other code paths) use to spawn child backends.
The wrapper centralizes per-fork housekeeping (flushing stdio, signal
handling, optional `system_views`/security setup) that must happen
between `fork()` and the child's first real work. [from-comment]
[inferred]

## API / declarations

- `extern pid_t fork_process(void);` — wrapped `fork(2)`. Returns
  the child PID in the parent, 0 in the child, -1 on failure (same
  contract as raw `fork`). [verified-by-code] [inferred]

## Notable invariants / details

- Header is intentionally tiny — the wrapper has one job and lives
  in `src/backend/postmaster/fork_process.c`. The header exists so
  that any backend code that wants to fork goes through the wrapper
  instead of calling raw `fork(2)`. [inferred]
- On Windows / EXEC_BACKEND builds, this is effectively unused;
  process creation goes through `internal_forkexec` instead. The
  header still compiles though. [inferred]
- No locking or shared-state side-effects are documented at this
  layer; the wrapper's responsibilities (flushing buffers, etc.) are
  internal to the `.c` file. [inferred]

## Potential issues

- Line 15. The declaration has no `PGDLLIMPORT`, so on Windows the
  symbol is not callable from extensions. In practice no extension
  should be forking from a backend, but the choice is implicit
  rather than documented. [verified-by-code]
  [ISSUE-api-shape: lack of `PGDLLIMPORT` is intentional but
  undocumented; an extension trying to call `fork_process` from
  Windows would see a link error with no friendly explanation (nit)]
- File-wide. The single-line header gives no hint of when
  `fork_process` is the right entry point vs `internal_forkexec` vs
  the postmaster's bgworker machinery. New contributors looking up
  "how do I fork a child" would benefit from a one-paragraph
  decision-tree comment. [inferred]
  [ISSUE-doc-drift: header lacks any guidance on when `fork_process`
  is the correct entry point (nit)]
