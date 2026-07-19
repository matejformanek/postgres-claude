---
path: src/port/inet_aton.c
anchor_sha: e18b0cb7344
loc: 151
depth: read
---

# src/port/inet_aton.c

## Purpose

GNU C Library `inet_aton()` port for platforms lacking it. Parses an ASCII
IPv4 address (`192.168.1.1`, also `192.168.257`, `0xc0a80101`, octal `010`)
and produces a network-byte-order `struct in_addr`. Importantly differs
from `inet_addr()`: returns 0 on FAILURE (rather than -1 / broadcast
255.255.255.255 confusion), so callers can distinguish "bad address" from
"the broadcast address". `[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int inet_aton(const char *cp, struct in_addr *addr)` | `inet_aton.c:58` | Returns 1 on valid parse, 0 on failure; addr may be NULL to just validate |

## Internal landmarks

- Number-base sniff (`:75-81`) — leading `0x`/`0X` = hex, leading `0` =
  octal, otherwise decimal. Matches C-style integer literal rules.
- Per-octet parsing loop (`:82-98`) — accepts hex digits only in hex base.
  No range check inside the loop; range validated after `'.'` at `:105`.
- Dot handling (`:99-107`) — at most 4 parts total (3 dots); checks
  `pp >= parts + 3` to reject a 5th. Each non-final part is bounded to
  0xff. `[verified-by-code]`
- Trailing-junk check (`:114-118`) — only ASCII whitespace allowed after
  the last digit; anything else fails.
- Multi-format concoction (`:122-147`) — supports four classical forms:
  - `a` (single 32-bit number, no dots) → val unchanged
  - `a.b` (8.24) — b bounded 0xffffff
  - `a.b.c` (8.8.16) — c bounded 0xffff
  - `a.b.c.d` (8.8.8.8) — d bounded 0xff
- Byte-order conversion (`:149`) — `pg_hton32(val)` to network order before
  store. `[verified-by-code]`

## Invariants & gotchas

- **`inet_addr` returns INADDR_NONE (0xffffffff) on error, which is the
  same as the broadcast address 255.255.255.255.** That's why this exists
  — `inet_aton` uses a separate success/failure channel (the return value),
  freeing `addr->s_addr = 0xffffffff` to legitimately mean "broadcast".
  `[from-comment]`
- **Multi-format support is a libc legacy.** Modern parsers usually reject
  anything but four dotted-decimal octets. PG accepts the legacy forms
  because `inet`/`cidr` SQL types contractually preserve libc input
  parsing. Be aware that `192.5.5.50000` parses as `192.5.5.50000` =
  `192.5.13.16` — surprising but documented C behavior.
- **`addr == NULL` is valid** (`:148`) — caller can validate-only without
  storing the parsed bytes. The function still walks the entire string,
  so this is not a length-bound parse.
- **No IPv6 support.** That's `inet_pton(AF_INET6, ...)` territory.

## Cross-refs

- `source/src/backend/utils/adt/network.c` — `inet_in` SQL function path.
- `knowledge/files/src/port/inet_net_ntop.c.md` — sibling IPv4/IPv6 binary-to-text.
- `source/src/include/port/pg_bswap.h` — `pg_hton32` byte-swap primitive.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
