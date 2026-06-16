# network.c — `inet` and `cidr` type I/O and operators

## Purpose

Implements the `inet` and `cidr` SQL types: textual I/O, operators (`<`, `<=`, `=`, `>>=`, `<<`, `&&` etc.), set/get masklen, host/network/broadcast/netmask functions, `inet_merge`, and the family-aware sort-support (with abbreviated keys).

Source: `source/src/backend/utils/adt/network.c` (2037 lines).

## Key functions

- `inet_in` / `cidr_in` (lines 118, 126) — delegate to `inet_net_pton` (in `inet_net_pton.c`), then validate masklen and call `addressOK` (line 1574) to enforce that cidr has no host bits set. [verified-by-code]
- `inet_out` / `cidr_out` (lines 162, 170) — wrap `inet_cidr_ntop` and `inet_net_ntop` (in `inet_cidr_ntop.c`). [verified-by-code]
- `inet_recv` / `cidr_recv` (lines 247, 255) — binary in: read family byte, masklen byte, "is_cidr" byte, address bytes. Validates against the family-specific byte count. [verified-by-code]
- `inet_send` / `cidr_send` (lines 287, 295) — binary out.
- `inet_set_masklen` / `cidr_set_masklen` (lines 319, 343) — range-check the new masklen against family limits. [verified-by-code]
- `network_cmp` (line 420) and `network_fast_cmp`, `network_sortsupport`, `network_abbrev_convert` (lines 432-754) — abbreviated-key sort support; the abbreviated key is the network prefix as a `Datum`-sized integer. [verified-by-code]
- `network_lt`, `_le`, `_eq`, `_ge`, `_gt`, `_ne` (lines 755-810). All go through `network_cmp_internal`.
- `network_sub` (`<<`, "is strictly contained by") (line 862), `network_subeq` (line 877), `network_sup` (line 892). [verified-by-code]
- `network_host` (line 1106), `network_show` (1132), `inet_abbrev`/`cidr_abbrev` (1155, 1173), `network_masklen` (1191), `network_family` (1199), `network_broadcast` (1218), `network_network` (1263), `network_netmask` (1307), `network_hostmask` (1349), `inet_same_family` (1397), `inet_merge` (1409). [verified-by-code]
- `bitncmp` (1502) — bitwise-prefix compare, n is in bits. [verified-by-code]
- `addressOK` (1574) — enforces that cidr has no host bits set. [verified-by-code]
- `inet_client_addr` / `inet_client_port` (1649, 1686), `inet_server_addr` / `inet_server_port` (1721, 1758) — inspect the postmaster MyProcPort. [verified-by-code]
- `inetnot`, `inetand`, `inetor` (1790, 1815, 1847) — bitwise inet ops; only meaningful within the same family. [verified-by-code]
- `internal_inetpl` (1879), `inetpl` (1931), `inetmi_int8` (1941), `inetmi` (1951) — arithmetic; uses Int128 internally to avoid overflow on /96 ranges. [verified-by-code]
- `clean_ipv6_addr` (2028) — strips an IPv6 zone-id suffix.

## Phase D notes

- **`addressOK` is the cidr invariant gate** — rejects any `cidr` input whose host bits are non-zero. This is the difference between `inet` (host address with prefix) and `cidr` (pure network address). [verified-by-code:1574]
- **Binary recv validates byte count**: `inet_recv` reads exactly the right number of bytes per family or errors. [verified-by-code:247-280]
- **Abbreviated sort keys** are correct only because `bitncmp` (and the abbrev encoder) treats different families as distinct ranges. A buggy abbrev key would be a classic sort-corruption hazard. [from-comment]
- **Family check before bitwise ops** — `inetand`/`inetor`/`inetnot`/`internal_inetpl` all error if families differ. [verified-by-code]

## Potential issues

- `[ISSUE-correctness: network_abbrev_convert uses the high-order bits of the address as the abbreviated key; collisions for very narrow nets in the same /16 reduce sort acceleration to the tie-breaker. Performance-only, not correctness (low)]`.
- `[ISSUE-undocumented-invariant: cidr_in normalizes the input — silently drops host bits if invoked through inet_to_cidr — but cidr_in itself rejects them. A user expecting cidr_in to round to the network would be surprised (low; documented in user docs)]`.
- `[ISSUE-correctness: clean_ipv6_addr at 2028 strips zone-id suffixes (e.g. fe80::1%eth0); the comment suggests this is intentional to make zone-id-bearing addresses parseable, but the discarded zone-id is silently lost (low)]`.
- `[ISSUE-trust-boundary: inet_client_addr returns the peer address as recorded at connection time; if a reverse proxy forwards client connections, this won't be the "real" client address. Documented but a common operational gotcha (low)]`.

Confidence: `[verified-by-code]` for the function/line map.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
