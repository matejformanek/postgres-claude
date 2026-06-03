# username.c

Tiny FE/BE helper: returns the effective OS username (`getpwuid` on
POSIX, `GetUserName` on Windows) as a pointer into a **static**
buffer. Used by `initdb`, libpq's default-username fallback,
`pg_regress`, etc. (`source/src/common/username.c:1-87`)
[verified-by-code]

## Purpose

Centralize the "who is the OS user running this binary" lookup so
every tool agrees, and reports the same translated error message
on failure.

## Key functions

- `get_user_name(char **errstr)` — on POSIX, `getpwuid(geteuid())`;
  returns `pw->pw_name` (pointer into libc's static pwd buffer) or
  NULL with `*errstr` set to a `psprintf`'d "could not look up
  effective user ID …" message. On Windows, fills a 257-byte
  function-local static `username[]` via `GetUserName` and returns
  it, with `*errstr` set on failure.
  (`source/src/common/username.c:30-67`)
- `get_user_name_or_exit(progname)` — wrapper that prints `errstr`
  to stderr and `exit(1)` on failure.
  (`source/src/common/username.c:73-87`)

## State / globals

- POSIX: relies on `getpwuid`'s internal static storage —
  **not thread-safe**, and a subsequent `getpwuid` call clobbers
  the previous result.
- Windows: function-local `static char username[257]` — same
  caveat.

## Phase D notes

[ISSUE-trust-boundary: return value points into libc-owned static
storage; lifetime undocumented in the header (low)]
`username.h:12-13` declares the function but doesn't mention the
static-buffer lifetime. A caller that holds the returned `const
char *` across a later `getpwuid`/`getpwnam` call has a
use-after-overwrite. Frontend tools rarely do this, but worth
spelling out.

## Potential issues

- POSIX `errno=0` discipline at line 39-40 + check at 45 — without
  it, glibc's `getpwuid` returning NULL with `errno` left over from
  a prior call would misreport "user does not exist" vs a real
  errno. Correct as written.
