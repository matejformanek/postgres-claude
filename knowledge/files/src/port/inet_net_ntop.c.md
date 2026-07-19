---
path: src/port/inet_net_ntop.c
anchor_sha: e18b0cb7344
loc: 296
depth: read
---

# src/port/inet_net_ntop.c

## Purpose

ISC-origin BSD port of `inet_net_ntop()` — converts a network/host address
in network byte order plus a mask-length to its presentation form (CIDR
text: `192.5.5.0/24` or `2001:db8::1/64`). The "always shipped" version
because the `inet`/`cidr` SQL types need predictable behavior across
platforms. Used as `pg_inet_net_ntop()` (with leading `pg_` for symbol
hygiene). `[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `char *pg_inet_net_ntop(int af, const void *src, int bits, char *dst, size_t size)` | `inet_net_ntop.c:77` | af = `PGSQL_AF_INET` or `PGSQL_AF_INET6` (or system `AF_INET6` if different); returns dst or NULL with errno |

## Internal landmarks

- AF dispatcher (`:77-98`) — switch on `af` to v4 or v6 helper. Accepts
  both `PGSQL_AF_INET6` (PG's internal family constant) and the system
  `AF_INET6` if they differ (they almost always do — Linux is 10, FreeBSD
  is 28, etc.). `PGSQL_AF_INET == AF_INET` is asserted invariant by
  comment. `[from-comment]`
- `inet_net_ntop_ipv4` (`:114`) — always prints all four octets (even if
  bits < 32). Appends `/bits` unless bits == 32 (which would round-trip
  back to a host address). `[from-comment]`
- `inet_net_ntop_ipv6` (`:178`) — the heavy lifting:
  - Preprocess copy bytewise → wordwise array (network → host order, `:207-209`).
  - Find the longest run of zero words for `::` shorthand (`:210-239`).
    Runs of length 1 are explicitly skipped (`:238-239`) — the RFC requires
    `::` to compress at least two zero groups, and `0:0:0:1::` is
    incorrect for `::0:0:0:1`. `[verified-by-code]`
  - Format with the compression at the chosen offset (`:244-275`).
  - IPv4-in-IPv6 detection (`:259-272`) — when zero run starts at base 0 and
    matches one of three shapes (length 6 = `::IPv4`, length 7 with
    non-`::1` final = unusual, length 5 with `ffff` at pos 5 = IPv4-mapped),
    print last 32 bits as dotted-decimal via `decoct`. `[from-comment]`
- `decoct` (`:155`) — helper to format `bytes` octets dotted-decimal into
  `dst`.

## Invariants & gotchas

- **Network byte order assumed.** `:108-109` flags this: `192.5.5.240/28`
  has `0b11110000` in its fourth octet, i.e., the mask isn't extracted
  from `src` — `src` is the full address (with possibly nonzero host bits)
  and `bits` is the mask length. The host bits are NOT zeroed by this
  function. `[from-comment]`
- **Buffer-size errors return NULL with errno=EMSGSIZE.** All length checks
  are pre-write (`size <= sizeof ".255"` etc.). Callers must check the
  return before using `dst`.
- **IPv6 zone-id (`%eth0`) is not handled.** Use `pg_inet_pton`/`ntop_ipv6`
  for that; this is purely a numeric address renderer.
- ISC license (not BSD) at the top — preserve when modifying.

## Cross-refs

- `source/src/backend/utils/adt/network.c` — primary caller (`inet_out`,
  `cidr_out` SQL functions).
- `source/src/port/inet_aton.c` — sibling IPv4 text-to-binary.
- `knowledge/files/src/port/inet_aton.c.md` — sibling doc.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
