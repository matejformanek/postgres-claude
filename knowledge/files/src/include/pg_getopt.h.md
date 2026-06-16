# `src/include/pg_getopt.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~57
- **Source:** `source/src/include/pg_getopt.h`

Portability shim for `getopt(3)`. PG files that use `getopt()` always
include this file. The header handles three scenarios
(`pg_getopt.h:1-9`): (1) platform has a usable `getopt()` and we use
it; (2) platform lacks `getopt()` and we declare everything from
`src/port/getopt.c`; (3) platform has `getopt()` but we don't trust
its behavior — we declare overrides compatible with both libc's and
our `src/port/getopt.c`. [from-comment]

## API / declarations

- `#include <unistd.h>` (`pg_getopt.h:23`) — POSIX-mandated location.
- `#include <getopt.h>` (`pg_getopt.h:27`) — only when `HAVE_GETOPT_H`.
- `optarg`, `optind`, `opterr`, `optopt` (`pg_getopt.h:35-42`) —
  declared as PGDLLIMPORT only when `HAVE_GETOPT_H` is unset
  (otherwise the system header declares them). The previous
  unconditional declaration was changed because "Cygwin doesn't
  like that" (`pg_getopt.h:32-33`).
- `optreset` (`pg_getopt.h:48-50`) — declared when
  `HAVE_INT_OPTRESET` is set but Cygwin is excluded; the BSD
  optreset extension that some platforms have but fail to declare.
- `getopt(nargc, nargv, ostr)` prototype if `HAVE_GETOPT` is unset
  (`pg_getopt.h:53-55`).

## Notable invariants / details

- The file is `IWYU pragma: always_keep` (`pg_getopt.h:18`).
- This header is the FRONTEND counterpart for `getopt`; backend code
  almost never uses `getopt` directly except for stand-alone
  binaries (`postmaster -D ...`).
- `optreset` is BSD-specific; GNU getopt requires resetting via
  `optind = 0`. PG's compatibility wrapper handles both. The Cygwin
  exclusion (`pg_getopt.h:48`) is because Cygwin's `<getopt.h>`
  declares optreset incompatibly. [from-comment]
- The `extern` declarations are PGDLLIMPORT-marked so that frontend
  binaries linking against libpgport on Windows see them through
  the DLL. [verified-by-code]

## Potential issues

- `pg_getopt.h:31-42` — branching declarations of `optind` etc. on
  `HAVE_GETOPT_H` is fragile; a platform whose `<getopt.h>` declares
  these as non-PGDLLIMPORT-extern silently mismatches on Windows
  builds with /MD. [ISSUE-style: portability of optind declaration
  on Windows is fragile (nit)]
- `pg_getopt.h:46-50` — the optreset compile-time scenarios are
  hand-tuned; a new platform combining BSD-style optreset with
  PG-style override needs another `#if defined(...)` clause.
  [ISSUE-style: optreset branch grows linearly with platforms (nit)]
- `pg_getopt.h:53-55` — bare `extern int getopt(...)` with no
  matching libc-shape signature check; if the platform happens to
  have a same-named symbol with different argument types, link
  silently succeeds. [ISSUE-correctness: no signature compatibility
  check at link (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../issues/include-misc.md)
<!-- issues:auto:end -->
