# `src/include/postgres_fe.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~34
- **Source:** `source/src/include/postgres_fe.h`

The frontend counterpart of `postgres.h` — included first by every PG
client library or stand-alone program (psql, pg_dump, pg_basebackup,
libpq internals, …). It is **deliberately small**: defines `FRONTEND
1`, then pulls in `c.h` and `common/fe_memutils.h`. That's the entire
file. [verified-by-code]

## API / declarations

- `#define FRONTEND 1` (`postgres_fe.h:23`) — set unconditionally
  before any other include. Every header that needs to behave
  differently in frontend vs backend tests `#ifdef FRONTEND` (e.g.
  `c.h:946` for the frontend Assert path).
- `#include "c.h"` (`postgres_fe.h:28`) — pulls in the master
  compatibility header. With `FRONTEND` set, `c.h` skips the backend
  Assert/ExceptionalCondition declarations.
- `#include "common/fe_memutils.h"` (`postgres_fe.h:30`) — frontend
  palloc/pfree wrappers around malloc (no MemoryContext machinery).
- IWYU `begin_exports`/`end_exports` (`postgres_fe.h:26,32`) — both
  re-included headers are exported.

## Notable invariants / details

- Frontend code must include `postgres_fe.h` BEFORE any other PG
  header, otherwise headers that key off `FRONTEND` will see the
  wrong value (the comment at `postgres_fe.h:6-8` is explicit:
  "This should be the first file included by PostgreSQL client
  libraries and application programs"). [from-comment]
- Defining `FRONTEND` flips `Assert` to use libc `assert(3)` (not
  `ExceptionalCondition`), suppresses `extern ExceptionalCondition`
  in `c.h`, and gates dozens of `#ifndef FRONTEND` blocks across the
  source tree. [verified-by-code]
- Mixing `postgres.h` and `postgres_fe.h` in the same TU is a
  compile-time error (multiple definition of the wrong-side
  guards). [inferred]
- The header is `IWYU pragma: always_keep` (`postgres_fe.h:18`) —
  IWYU never removes it, since its main purpose is the side-effect
  of `#define FRONTEND 1`. [from-comment]

## Potential issues

- `postgres_fe.h:22-24` — `#ifndef FRONTEND #define FRONTEND 1
  #endif` lets a caller pre-define `FRONTEND` to a non-1 value
  (e.g. via `-DFRONTEND=2`); the file then does nothing. Most
  consumers test `#ifdef FRONTEND` not `#if FRONTEND == 1`, so a
  non-1 value still works — but the guard is a footgun for an
  imagined "FRONTEND=0 means backend" mistake. [ISSUE-style:
  defensive `#ifndef FRONTEND` guard accepts non-1 values (nit)]
- A new client program that forgets `postgres_fe.h` and includes
  `c.h` directly will be a backend-leaning compile, then fail to
  link `ExceptionalCondition`. No header-level diagnostic.
  [ISSUE-undocumented-invariant: omitting postgres_fe.h fails at
  link time, not compile time (nit)]
