# utils/inet.h — inet/cidr/macaddr internal formats

Source: `source/src/include/utils/inet.h` (184 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

In-memory layout of INET, CIDR, MACADDR, and MACADDR8. The first three share `inet` storage via a 1-byte-header varlena wrapper.

## Public API / on-disk format

`inet_struct` (`inet.h:23-28`):
```
unsigned char family;     /* PGSQL_AF_INET or PGSQL_AF_INET6 */
unsigned char bits;       /* netmask bits */
unsigned char ipaddr[16]; /* up to 128 bits */
```

`inet` (`inet.h:52-56`) wraps it with `char vl_len_[4]` — the *uncompressed* 4-byte-header view. In practice tuples store the 1-byte-header form (max body size = 18 bytes).

`macaddr` (`inet.h:94-102`) and `macaddr8` (`inet.h:107-117`) are plain fixed-length pass-by-reference structs (6 / 8 bytes).

## Invariants

- **INV-inet-family-AF_INET-or-AF_INET6** [verified-by-code, `inet.h:39-40`]: `family ∈ {PGSQL_AF_INET, PGSQL_AF_INET6}`. Underlying constants are derived from system `AF_INET` but offset to be portable across systems lacking AF_INET6 (`inet.h:32-37`).
- **INV-inet-bits-le-maxbits** [from-implementation]: header docs neither caps `bits` nor enforces `bits ≤ ip_maxbits(inetptr)` (32 for INET4, 128 for INET6); enforcement lives in `inet_in`/`inet_recv`.
- **INV-inet-pre-7.4-AF_INET** [from-comment, `inet.h:32-37`]: pre-7.4 databases used the raw AF_INET on disk; the PGSQL_AF_* constants must remain stable on disk to avoid a dump/reload requirement.
- **INV-inet-VARDATA_ANY-trick** [from-comment, `inet.h:58-69`]: macros `ip_family`/`ip_bits`/`ip_addr` use `VARDATA_ANY`, which works for both 1-byte and 4-byte headers. When constructing a fresh value, callers MUST palloc0 (`inet.h:62-65`) so that the unset header word looks like a 4-byte header, then SET_INET_VARSIZE at the end.
- **INV-inet-SET_VARSIZE-after-family** [from-comment, `inet.h:67-69`]: `SET_INET_VARSIZE` requires `family` to be set correctly first (it computes size from `ip_addrsize`).

## Notable internals

- `ip_addrsize` (`inet.h:80-81`): 4 if AF_INET, 16 if AF_INET6.
- `DatumGetInetPP` (`inet.h:123-126`) returns a packed (short-header-tolerant) pointer; obsolete `DatumGetInetP` (`inet.h:138-142`) detoasts to full 4-byte form.
- `bitncmp`/`bitncommon` (`inet.h:181-182`): bit-level comparisons used in opclass support.

## Trust-boundary / Phase-D surface

- **inet_recv / cidr_recv** [inferred — header silent]: binary input must validate (a) `family ∈ {PGSQL_AF_INET, PGSQL_AF_INET6}`, (b) `bits ≤ ip_maxbits`, (c) for CIDR, the host bits beyond `bits` are zero, (d) varlena size matches the family. Header gives no hints.
- **palloc0 contract is fragile** (`inet.h:58-69`): if a future caller allocates with palloc (not palloc0) and forgets SET_INET_VARSIZE before any `ip_*` access, VARDATA_ANY interprets random bytes as the header.

## Cross-refs

- `source/src/backend/utils/adt/network.c` — `inet_recv`, `cidr_in`, validation.
- `source/src/backend/utils/adt/mac.c`, `mac8.c` — macaddr* implementations.

## Issues

- `[ISSUE-DOC: inet_recv validation contract not surfaced (medium)]` — header should reference network.c:inet_recv for the family/bits/host-bits checks; A7 docs a similar gap on array_recv.
- `[ISSUE-INVARIANT: palloc0+SET_INET_VARSIZE ordering is by-comment-only (low)]` — could be enforced by a build-fresh-inet helper to remove the foot-gun.
