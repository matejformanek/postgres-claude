# `src/include/getopt_long.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~37
- **Source:** `source/src/include/getopt_long.h`

The `getopt_long(3)` portability shim — strictly a thin layer over
`pg_getopt.h`. Provides the GNU-style long-option parsing that
front-end tools (psql, pg_dump, pg_basebackup, …) all use.
[verified-by-code]

## API / declarations

- `#include "pg_getopt.h"` (`getopt_long.h:13`) — pulls in the short-
  option machinery and the optarg/optind globals.
- `struct option { const char *name; int has_arg; int *flag; int val; }`
  (`getopt_long.h:17-23`) — only declared if the platform's
  `<getopt.h>` doesn't already define it (`HAVE_STRUCT_OPTION`).
- Argument-presence macros (`getopt_long.h:25-27`):
  - `no_argument 0`
  - `required_argument 1`
  - `optional_argument 2`
- `getopt_long(argc, argv, optstring, longopts, &longindex)`
  (`getopt_long.h:32-34`) — declared only when `HAVE_GETOPT_LONG`
  is unset; otherwise the system version is used. Our port lives in
  `src/port/getopt_long.c`.

## Notable invariants / details

- `IWYU pragma: always_keep` (`getopt_long.h:9`).
- The `struct option` layout is GNU-standard; if a platform has a
  subtly different one (`has_arg` is a `bool`, or `flag` is an
  `int **`), the `HAVE_STRUCT_OPTION` define MUST be set so we use
  theirs. The configure check is in `configure.ac`.
- All PG front-end tools use this header (not pg_getopt.h directly)
  because long options are the user-facing convention.
- The argument-presence macros are deliberately bare integer
  constants matching libc; they appear in the `option` table
  initializers as `OPT_DBNAME, required_argument, NULL, 'd'`. The
  bare-int representation means the table is C-array-initializable
  without runtime construction.

## Potential issues

- `getopt_long.h:15-28` — fallback `struct option` matches the GNU
  layout exactly. A platform with a same-named-but-incompatibly-laid-out
  struct could silently misparse. [ISSUE-style: no static-assert
  that `sizeof(struct option)` matches expected (nit)]
- `getopt_long.h:30-35` — only the function declaration; an extension
  that wants to use the long-option machinery needs to link
  libpgport which carries `src/port/getopt_long.c`. [ISSUE-doc-drift:
  getopt_long porting requirements not documented at header (nit)]
- `getopt_long.h:25-27` — `no_argument`, `required_argument`,
  `optional_argument` are bare macros not in any namespace; collide
  with user-defined macros of the same name. [ISSUE-style: bare
  global macro names from POSIX (nit)]
