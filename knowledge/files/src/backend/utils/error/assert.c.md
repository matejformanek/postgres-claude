# assert.c

- **Source path:** `source/src/backend/utils/error/assert.c`
- **Lines:** 66
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/c.h` (Assert/AssertMacro definitions), `error/elog.c`

## Purpose

The crash handler invoked by a failed `Assert()`. Tiny by design: when an assert blows up, you do **not** want to run through the full elog machinery (which itself uses Asserts and allocates memory). This file's `ExceptionalCondition` writes a one-line `TRAP: failed Assert(...)` to stderr, optionally dumps a backtrace, optionally sleeps forever for debugger attach, and `abort()`s. [from-comment, assert.c:22-28]

## Top-of-file comment (verbatim)

> "assert.c — Assert support code." Plus the function header: "ExceptionalCondition — Handles the failure of an Assert(). We intentionally do not go through elog() here, on the grounds of wanting to minimize the amount of infrastructure that has to be working to report an assertion failure." [from-comment, assert.c:3-28]

## Public surface

- `ExceptionalCondition(conditionName, fileName, lineNumber)` (29) — the only function. Called by the `Assert` macro family in `c.h` when `USE_ASSERT_CHECKING` is on.

## Key invariants

- **Never calls `ereport`/`elog`.** This is the whole point of the file. [from-comment, assert.c:25-27]
- **Uses `write_stderr` (the printf-to-stderr no-allocation helper from elog.c) and direct `fflush(stderr)`.** No palloc, no memory contexts, no error-frame stack.
- **Backtrace dumped only if `HAVE_BACKTRACE_SYMBOLS` (glibc/macOS).** Uses `backtrace()` + `backtrace_symbols_fd()`, capped at 100 frames.
- **`SLEEP_ON_ASSERT` build option → `sleep(1000000)` before abort.** Used for "attach debugger now" workflows. `pg_usleep` is intentionally NOT used because its 2 GB µsec limit (~33 min) is "too short". [from-comment, assert.c:56-60]
- **`abort()` is the final action.** Triggers SIGABRT, which the postmaster observes and uses to kill the rest of the cluster.

## Cross-references

- `c.h` defines `Assert(condition)` as `((void)((condition) ? 0 : (ExceptionalCondition(#condition, __FILE__, __LINE__), 0)))` when asserts are enabled, or a no-op otherwise. AssertMacro / StaticAssertStmt etc. share the same handler.
- `postmaster.c` interprets SIGABRT from a backend as a PANIC-equivalent and terminates the cluster.

## Open questions

- None — file is mechanical.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
