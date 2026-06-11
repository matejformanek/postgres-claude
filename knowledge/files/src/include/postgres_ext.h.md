# `src/include/postgres_ext.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~74
- **Source:** `source/src/include/postgres_ext.h`

The external API surface for libpq consumers — declarations that must
be visible **outside the PG source tree**. Anything declared here is
part of the libpq ABI; anything not here is internal. `c.h` includes
it (`c.h:96`), so backend code also sees these symbols, but the
authoritative purpose is the client-side contract. [verified-by-code]

## API / declarations

- `typedef unsigned int Oid` (`postgres_ext.h:32`) — the canonical
  client-visible Oid type. Backend `c.h:723-727` re-uses this. C++
  callers get `Oid(0)` for `InvalidOid`; C callers get `((Oid) 0)`
  via the `__cplusplus` gate at `postgres_ext.h:34-38`.
- `#define InvalidOid` — 0.
- `#define OID_MAX UINT_MAX` — comment notes "you will need to include
  `<limits.h>` to use the above #define" (`postgres_ext.h:41`).
- `atooid(x)` macro = `(Oid) strtoul(x, NULL, 10)` (`postgres_ext.h:43`).
- `typedef int64_t pg_int64` (`postgres_ext.h:48`) — explicitly
  deprecated ("formerly used in client API declarations"). Kept for
  source compatibility with apps that still use the alias.
- 17× `PG_DIAG_*` single-char field tags (`postgres_ext.h:55-72`) —
  these are the wire-protocol field identifiers in an ErrorResponse
  message. Frozen ABI; any new ones go at the end. Examples:
  `PG_DIAG_SEVERITY = 'S'`, `PG_DIAG_SQLSTATE = 'C'`,
  `PG_DIAG_MESSAGE_PRIMARY = 'M'`, `PG_DIAG_STATEMENT_POSITION = 'P'`,
  `PG_DIAG_CONTEXT = 'W'`, `PG_DIAG_SCHEMA_NAME = 's'`,
  `PG_DIAG_SOURCE_FILE = 'F'`. [verified-by-code]

## Notable invariants / details

- This is one of three header tiers visible to libpq applications.
  The hierarchy: this file (universal, type-level) → `libpq-fe.h`
  (libpq-specific) → `libpq-events.h` etc. (`postgres_ext.h:9-12`).
  [from-comment]
- "User-written C functions don't count as external to Postgres"
  (`postgres_ext.h:13-16`) — meaning a `PG_FUNCTION_INFO_V1` C
  function is allowed to consume backend-internal headers. The
  `postgres_ext.h` line is for genuine third-party clients
  (Python's psycopg2, JDBC's pgjdbc-ng equivalents).
- `Oid` is `unsigned int`, not `uint32_t` — historical. Equivalent on
  every platform PG supports today, but the typedef is not parameterised
  on `<stdint.h>`. [verified-by-code]
- `Oid8` is **NOT** here — it's a backend-only typedef at `c.h:756`.
  Client code that wants 8-byte OIDs must roll its own. This is
  intentional: 8-byte OIDs are a recent (post-master) addition and
  libpq ABI cannot accept them without a version bump.
  [ISSUE-doc-drift: `Oid8` is backend-only but the comment at
  `c.h:755` doesn't explain why it's not in `postgres_ext.h` (nit)]
- `pg_int64` is deprecated for libpq itself but is still in extension
  code worldwide. Removing it would break a huge amount of
  third-party code. [from-comment]
- The `PG_DIAG_*` values are 1-byte ASCII codes chosen for the
  PostgreSQL wire protocol (5.4 "ErrorResponse and NoticeResponse"
  in the docs). New ones MUST be ASCII printable and MUST NOT collide
  with existing assignments — a hazard for forks adding new diag
  codes. [inferred]
- `#include <stdint.h>` at `postgres_ext.h:27` is required for
  `int64_t` in the `pg_int64` typedef. [verified-by-code]

## Potential issues

- `postgres_ext.h:32` — `Oid` is `unsigned int`. On a hypothetical
  16-bit `int` platform Oid would be 16 bits, breaking everything.
  No `StaticAssert` at this layer enforces `sizeof(Oid) == 4`.
  [ISSUE-undocumented-invariant: no static assert that `sizeof(Oid)
  == 4` at the public-ABI boundary (nit)]
- `postgres_ext.h:43` — `atooid` uses `strtoul`; on a platform with
  `sizeof(unsigned long) == 8` and a huge input, the truncating cast
  to `Oid` silently loses bits with no error. [ISSUE-correctness:
  `atooid` silently truncates inputs > 2^32 on 64-bit `long`
  platforms (maybe)]
- `postgres_ext.h:55-72` — `PG_DIAG_*` constants are not enclosed in
  an enum; a fork or extension that adds custom diag fields can
  collide with future PG additions without compile-time warning.
  [ISSUE-api-shape: PG_DIAG_* namespace is single-char ASCII with
  no allocation discipline document (nit)]
