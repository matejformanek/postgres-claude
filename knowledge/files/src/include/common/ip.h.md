# ip.h

Prototypes for the three IPv4/IPv6/Unix-socket helpers implemented
in `src/common/ip.c`. (`source/src/include/common/ip.h`)
[verified-by-code]

## Purpose

Shared FE/BE: lets the backend listener and libpq talk through one
set of address-resolution functions that papers over libc
differences with AF_UNIX.

## Key declarations

- `int pg_getaddrinfo_all(const char *hostname, const char
  *servname, const struct addrinfo *hintp, struct addrinfo
  **result)` — getaddrinfo wrapper. Requires non-NULL `hintp`
  (deviates from libc).
- `void pg_freeaddrinfo_all(int hint_ai_family, struct addrinfo
  *ai)` — must be passed the *original* `hintp->ai_family` so the
  freer can tell apart system vs internal AF_UNIX results.
- `int pg_getnameinfo_all(const struct sockaddr_storage *addr, int
  salen, char *node, int nodelen, char *service, int servicelen,
  int flags)` — getnameinfo wrapper using `sockaddr_storage`;
  guarantees `node`/`service` are filled even on failure.

Pulls in `<netdb.h>`, `<sys/socket.h>`, and `libpq/pqcomm.h`.

## Phase D notes

None specific to the header; all behaviour lives in `ip.c` and is
documented there.
