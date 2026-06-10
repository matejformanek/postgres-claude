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

## Issues

[ISSUE-undocumented-invariant: `pg_getaddrinfo_all`
(`ip.h:23-25`) "requires non-NULL hintp" — but the header has no
explicit precondition statement. Passing NULL (legal for libc
`getaddrinfo`) results in a `NULL hintp->ai_family` deref inside the
wrapper (low)]

[ISSUE-trust-boundary: `pg_getnameinfo_all` (`ip.h:28-31`) — the
`flags` argument is passed verbatim to libc `getnameinfo`; a misuse
(`NI_NAMEREQD` vs `NI_NUMERICHOST`) changes whether the reverse-DNS
boundary is crossed. Header silent on which flags are appropriate
for which caller (low)]

[ISSUE-trust-boundary: shared FE+BE — pg_hba.conf hostname matching
uses these wrappers; a poisoned DNS response can become an auth
decision in the backend listener path (medium)] A2 cross-link;
implementation in .c, but the .h could state the trust model.

## Cross-refs

- A2 libpq stack — primary consumer (auth, hostname matching).
- Companion: `src/common/ip.c`.
