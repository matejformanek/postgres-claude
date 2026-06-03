# ifaddr.h

- **Source path:** `source/src/include/libpq/ifaddr.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"IP netmask calculations, and enumerating network interfaces" — small
helpers used by `pg_hba.conf` `samehost`/`samenet` matching and by the
ident-style host comparisons [from-comment].

## Public API surface

- `typedef void (*PgIfAddrCallback)(struct sockaddr *addr, struct sockaddr *netmask, void *cb_data)`.
- `int pg_range_sockaddr(addr, netaddr, netmask)` — does `addr` fall in the
  `(netaddr, netmask)` network.
- `int pg_sockaddr_cidr_mask(struct sockaddr_storage *mask, char *numbits, int family)`
  — produce a sockaddr-shaped mask from a CIDR bit count.
- `int pg_foreach_ifaddr(PgIfAddrCallback callback, void *cb_data)` —
  enumerate local network interfaces.

## Cross-refs

- Related backend: `src/backend/libpq/ifaddr.c`.
- Used from `src/backend/libpq/hba.c` for `samehost`/`samenet` token
  evaluation.

## Tally

`[verified-by-code]=4 [from-comment]=1`
