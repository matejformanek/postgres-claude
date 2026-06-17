---
path: src/tools/ifaddrs/test_ifaddrs.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 71
depth: read
---

# `src/tools/ifaddrs/test_ifaddrs.c` — manual smoke test for `pg_foreach_ifaddr()`

## Purpose

A tiny standalone `main()` that exercises PostgreSQL's
`pg_foreach_ifaddr()` (the portable "enumerate this host's network interface
addresses" helper in `src/backend/libpq/ifaddr.c`) and prints each interface's
address and netmask. It is a developer diagnostic, **not** part of the build or
the test suite — there is no meson/Make wiring that runs it automatically; you
compile and run it by hand when porting `ifaddr.c` to a new platform to confirm
the `getifaddrs`/`SIOCGIFCONF`/Win32 fallback path returns sane data.

## Public symbols

| Symbol | Lines | Role |
|---|---|---|
| `print_addr` (static) | 17-43 | Formats one `struct sockaddr` to numeric host form via `getnameinfo(NI_NUMERICHOST)`. Picks the address length by family (`AF_INET`/`AF_INET6`/else `sockaddr_storage`). |
| `callback` (static) | 45-53 | The `PgIfAddrCallback` passed to `pg_foreach_ifaddr`; prints `addr:`/`mask:` for each interface. |
| `main` | 55-71 | Does `WSAStartup` on WIN32, then `pg_foreach_ifaddr(callback, NULL)`. |

## Internal landmarks

- Includes `libpq/ifaddr.h` (test_ifaddrs.c:14) — the only PG header it needs;
  everything else is libc/sockets.
- WIN32 path (test_ifaddrs.c:58-66) initialises Winsock before the enumeration,
  mirroring what a real backend does at startup.

## Invariants & gotchas

- Uses `%m` in its error message (test_ifaddrs.c:69) — relies on PostgreSQL's
  snprintf supplying `%m` (strerror of `errno`), which is why it includes
  `postgres.h` rather than being pure libc.
- Output is informational only; there is no pass/fail assertion. "Correct"
  means the printed addresses match `ip addr` / `ipconfig` for the host.

## Cross-refs

- `src/backend/libpq/ifaddr.c` — the unit under test (`pg_foreach_ifaddr`,
  `pg_range_sockaddr_*`). Used by `hba.conf` CIDR matching.
- [[idioms/error-handling]] — the `%m` conversion specifier.

## Potential issues

(none — single-purpose manual diagnostic.)
