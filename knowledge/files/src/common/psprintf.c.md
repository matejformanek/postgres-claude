# src/common/psprintf.c

## Purpose
sprintf-into-an-allocated-on-demand-buffer. Provides `psprintf()` — the
printf-style helper that returns a freshly-`palloc`'d (or `malloc`'d in
frontend) string — plus `pvsnprintf()`, the size-estimating workhorse.

## Role in PG
Pervasive across both backend (`palloc` path) and frontend tools (`malloc`
path, exit-on-error). Used wherever a small formatted string is wanted
without the caller pre-sizing a buffer: `RelationGetRelationName`-formatting
in errmsg, planner debug strings, libpq error strings, pg_dump label
construction, `quote_identifier`, etc.

## Key functions
- `psprintf(const char *fmt, ...)` (`source/src/common/psprintf.c:43`)
  Allocate initial 128-byte buffer, vsnprintf into it, double-and-retry if
  the estimate exceeds. Returns the populated buffer; caller `pfree`s.
  Preserves `errno` across the loop so `%m` keeps working.
- `pvsnprintf(char *buf, size_t len, const char *fmt, va_list args)`
  (`source/src/common/psprintf.c:103`)
  Wraps `vsnprintf`. On success returns the byte count (excludes terminator).
  On too-small buffer returns `vsnprintf`'s estimate **plus 1** (so the
  caller can use the bare return value as the next buffer size). On error
  (`vsnprintf < 0`) raises `elog(ERROR)` (backend) or prints to stderr and
  `exit(EXIT_FAILURE)` (frontend). [verified-by-code]

## State / globals
None. Pure leaf function over `palloc`/`pfree` (or `malloc`/`free` via the
frontend `palloc` shim in `src/common/fe_memutils.c`).

## Phase D notes
- **Allocation discipline.** Never returns NULL. On allocation failure the
  backend `palloc` raises `ereport(ERROR)`; frontend exits. [verified-by-code]
  Comment at psprintf.c:38-40 explicitly warns "*One should therefore think
  twice about using this in libpq.*" — libpq must not abort the host
  process. libpq has its own private printf wrapper.
- **Format-string trust boundary.** `psprintf`/`pvsnprintf` blindly trust
  `fmt`. Every caller MUST pass a compile-time constant. Passing untrusted
  format strings (e.g. attacker-controlled SQL text) would be a CWE-134.
  Grep'ing the tree, all current callers use string literals. [from-comment]
- **MaxAllocSize cap.** `pvsnprintf` will `ereport(ERROR)` if the required
  buffer exceeds `MaxAllocSize - 1` (1 GB - 1). Frontend uses the same cap.
  See psprintf.c:135. Means a runaway format expansion cannot DoS by
  consuming all heap — it errors out cleanly. [verified-by-code]
- **Loop termination.** The estimate-plus-1 trick ensures forward progress
  on non-C99-strict vsnprintf implementations (older glibc, some Solaris
  vsnprintf variants used to return -1 on overflow; PG handles -1 via the
  `unlikely(nprinted < 0)` ereport branch, so non-conforming libc behaves
  as a hard error rather than an infinite loop). [from-comment]

## Potential issues
- [ISSUE-undocumented-invariant: psprintf MUST NOT be used from libpq —
  enforced only by code comment, not by build-time hook. A future patch
  adding libpq use of psprintf would call abort() on OOM inside the client.
  (maybe)]
- [ISSUE-stale-todo: No format-string lint at build time. Callers passing
  non-literal `fmt` would compile silently. `__attribute__((format))` is
  set on the prototype in c.h, so `-Wformat-nonliteral` warnings would
  catch most cases — but PG does not enable that warning. (maybe)]
