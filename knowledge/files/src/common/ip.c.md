# ip.c

Shared FE/BE socket address helpers: `getaddrinfo`/`getnameinfo`
wrappers that also handle `AF_UNIX`, since the system versions on
some platforms don't. Used by the backend listener
(`postmaster/pqcomm.c`) and by libpq when resolving server hosts.
(`source/src/common/ip.c:1-17`) [verified-by-code]

## Purpose

Provide one `pg_getaddrinfo_all` / `pg_freeaddrinfo_all` /
`pg_getnameinfo_all` triple that backend and libpq both call,
papering over `AF_UNIX` differences and the historical quirks of
abstract namespace sockets (`@`-prefixed paths on Linux).

## Key functions

- `pg_getaddrinfo_all(hostname, servname, hintp, **result)` —
  forces `*result = NULL` first (some platforms don't zero on
  failure). Dispatches `AF_UNIX` to `getaddrinfo_unix`, otherwise
  calls libc `getaddrinfo`. Empty/NULL hostname is normalised to
  NULL for the libc path (where NULL means "any local address").
  (`source/src/common/ip.c:55-72`)
- `pg_freeaddrinfo_all(hint_ai_family, ai)` — chases the `ai_next`
  list and `free()`s the unix-built nodes ourselves, since
  `freeaddrinfo` doesn't know about them; otherwise delegates.
  (`source/src/common/ip.c:84-105`)
- `pg_getnameinfo_all(addr, salen, node, nodelen, service,
  servicelen, flags)` — `AF_UNIX` → `getnameinfo_unix`, else libc.
  **Always fills `node`/`service` with `"???"` on failure** so
  log lines never print uninitialized memory.
  (`source/src/common/ip.c:117-144`) [verified-by-code]
- `getaddrinfo_unix(path, hintsp, **result)` (static) — builds one
  `addrinfo` + `sockaddr_un`. Rejects paths ≥ `sizeof(sun_path)`
  with `EAI_FAIL` (line 165-166). For abstract namespace (`@`
  prefix), rewrites the leading byte to NUL and sets `ai_addrlen`
  to `offsetof + strlen(orig)` so trailing zero bytes aren't shown
  in `ss -x`. (`source/src/common/ip.c:155-225`)
- `getnameinfo_unix` (static) — fills `node="[local]"`, `service`
  is either `"@<rest>"` for abstract or `sun_path` verbatim.
  `EAI_MEMORY` if the snprintf would truncate.
  (`source/src/common/ip.c:230-265`)

## State / globals

None.

## Phase D notes

[ISSUE-info-disclosure: pg_getnameinfo_all logs sun_path verbatim
for AF_UNIX (low)] `getnameinfo_unix` writes the full path of the
unix socket into `service`. In multi-tenant or shared-host setups
that path may include a username (`/tmp/.s.PGSQL.<port>` is the
default, but custom `unix_socket_directories` can encode anything).
Backends log this through `BackendInitialize` →
`ps_status`. Low severity — it's already a server-controlled
config value.

[ISSUE-dos: getaddrinfo() with caller-controlled hostname is
synchronous + uncancellable (maybe)] `pg_getaddrinfo_all` blocks
in libc; libpq invokes it on the connection string's `host=`. A
malicious DNS server could stall connection setup indefinitely.
Mitigated by libpq's connection timeout, but `pg_getaddrinfo_all`
itself has no escape hatch — comment in line 67-69 just normalises
NULL.

[ISSUE-undocumented-invariant: getnameinfo_unix returns EAI_MEMORY
on truncation (lines 246, 260) but pg_getnameinfo_all overwrites
node/service with "???" only when rc != 0 — fine, but the
`EAI_MEMORY` literal collides with the libc meaning of "actual OOM"
which callers may treat differently (low)]

## Potential issues

- `strcpy(unp->sun_path, path)` (line 207) is bounded by the
  earlier check at line 165; safe but `strlcpy` would be more
  defensive.
- `getaddrinfo_unix` ignores `hintsp->ai_flags` entirely — comment
  at lines 150-153 calls out `AI_CANONNAME` is not supported.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
