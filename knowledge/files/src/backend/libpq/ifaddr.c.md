---
path: src/backend/libpq/ifaddr.c
anchor_sha: 4b0bf0788b0
loc: 455
depth: medium
---

# ifaddr.c

- **Source path:** `source/src/backend/libpq/ifaddr.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 455

## Purpose

CIDR mask construction, IPv4/IPv6 subnet-match arithmetic, and a
cross-platform `pg_foreach_ifaddr` for enumerating local interface
addresses. Underpins the `samehost` / `samenet` HBA keywords and any IP
range check. The original IPv6 implementation was contributed by Nigel
Kukard / LBSD. [from-comment, ifaddr.c:1-17]

## Public API surface

| Line | Symbol | Semantics |
|---|---|---|
| 49 | `pg_range_sockaddr(addr, netaddr, netmask)` | Is `addr` in `netaddr/netmask`? Returns 1/0. Caller must pre-verify all three are the same family. |
| 105 | `pg_sockaddr_cidr_mask(*mask, numbits, family)` | Build a `numbits`-prefix netmask of `family` (AF_INET / AF_INET6) into `*mask`. Returns 0 OK, -1 error. |
| 230 / 295 / 349 / 425 | `pg_foreach_ifaddr(callback, cb_data)` | Iterate over local interface addresses; four implementations selected by `#ifdef`. |

## Internal landmarks

### Range checks
- `range_sockaddr_AF_INET` (65) — one-line bitop: `(addr XOR netaddr) AND
  netmask == 0`. [verified-by-code, ifaddr.c:70-74]
- `range_sockaddr_AF_INET6` (77) — same idea but per-byte over 16 bytes.
  [verified-by-code, ifaddr.c:78-92]

### Mask construction
- For AF_INET: avoid `x << 32` via an explicit `if (bits > 0)` guard
  (undefined behaviour in C). [verified-by-code, ifaddr.c:131-136]
- For AF_INET6: per-byte loop. `0xff << (8 - bits)` is masked to 8 bits to
  defend against int promotion. [verified-by-code, ifaddr.c:158-159]

### Interface enumeration: four code paths under `#ifdef`
1. **`WIN32`** — Winsock `WSAIoctl(SIO_GET_INTERFACE_LIST)`, growing
   buffer up to 1024 INTERFACE_INFO entries. [verified-by-code, ifaddr.c:229-280]
2. **`HAVE_GETIFADDRS`** — BSD/macOS/Solaris/illumos/Linux preferred path,
   one call. [verified-by-code, ifaddr.c:294-309]
3. **`SIOCGIFCONF`** — fallback Unix `ioctl()` loop with grown buffer up
   to 100 KB; per-platform `_SIZEOF_ADDR_IFREQ` macro handles padding.
   "Some only return IPv4 information here, so this is the least preferred
   method." [from-comment, ifaddr.c:317-323] [verified-by-code, ifaddr.c:349-414]
4. **Stub** — return just `127.0.0.1/8` and `::1/128`. Used when none of
   the above are available. [verified-by-code, ifaddr.c:424-452]

### `run_ifaddr_callback`
- (180) Normalises mask: drops mask if family-mismatched or all-zeros, then
  substitutes a fully-set mask via `pg_sockaddr_cidr_mask(..., NULL, fam)`.
  Means callback always gets a valid mask. [verified-by-code, ifaddr.c:180-216]

## Invariants & gotchas

- **Caller must ensure address-family consistency.** `pg_range_sockaddr`
  silently returns 0 if `addr->ss_family` is neither AF_INET nor AF_INET6
  (e.g. AF_UNIX) — i.e. an AF_UNIX client never matches any IP-based
  `pg_hba.conf` rule, which is the desired behaviour but is "fail-closed"
  by accident. [verified-by-code, ifaddr.c:48-63]
- `pg_sockaddr_cidr_mask` returns -1 silently for bad `numbits` (negative,
  >32 for v4, >128 for v6) — callers must check the return. [verified-by-code, ifaddr.c:117-148]
- The `SIOCGIFCONF` fallback may miss IPv6 interfaces entirely. On modern
  Linux/BSD that path is dormant (HAVE_GETIFADDRS wins), but on a stripped
  embedded Unix without getifaddrs+ifaddrs.h, IPv6 `samenet` checks may
  silently fail. [from-comment, ifaddr.c:317-323]
- The Windows path uses raw `realloc()` / `free()`, not palloc — this
  module is sometimes used in postmaster context where palloc isn't safe.
  [verified-by-code, ifaddr.c:247-250]
- The stub fallback (no SIOCGIFCONF and no getifaddrs) returns *only*
  loopback. `samenet` on such a system means "only loopback subnet" —
  which is fail-closed in the right direction but worth knowing.
  [verified-by-code, ifaddr.c:431-449]

## Cross-refs

- Header: `source/src/include/libpq/ifaddr.h`
- Used by: `source/src/backend/libpq/hba.c` (`check_same_host_or_net`,
  `parse_hba_line` for CIDR), `auth.c` for radius source-address checks
- Sibling: `source/src/common/ip.c` (`pg_getaddrinfo_all`)

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: IPv4-mapped IPv6 (`::ffff:0:0/96`) handling]**
  `range_sockaddr_AF_INET6` (ifaddr.c:77) does literal byte comparison; a
  client connecting via an IPv4 socket that the kernel exposes as
  `::ffff:1.2.3.4` will NOT match an IPv4 `host` line. The comment at
  `pqcomm.c:603-608` flags this as a known kernel-dependent surface. Worth
  cross-checking on platforms without `IPV6_V6ONLY`. severity: maybe
- **[ISSUE-leak: realloc on failure path on Windows]** `ifaddr.c:247-254`
  — `realloc(ii, …)` returns NULL on failure but the caller code reads
  `if (!ptr) { free(ii); … }` correctly. No actual leak, just brittle
  to refactor. severity: nit
- **[ISSUE-undocumented-invariant: stub fallback is fail-closed but
  silently so]** `ifaddr.c:425` — if compiled without SIOCGIFCONF and
  without getifaddrs, `samenet`/`samehost` only ever matches loopback. No
  warning is emitted at HBA-parse time. A `LOG` note at postmaster startup
  would help admins. severity: maybe

## Tally

`[verified-by-code]=14 [from-comment]=4 [inferred]=0`
