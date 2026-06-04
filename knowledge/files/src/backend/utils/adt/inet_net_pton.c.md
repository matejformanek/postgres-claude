# inet_net_pton.c — presentation-format string → inet bytes

## Purpose

The text→address half of inet I/O. Originally ISC BIND9 code (Paul Vixie, 1996). Accepts dotted-quad IPv4, hex IPv4, IPv6 textual form, optional `/CIDR` prefix. Returns the prefix length or `-1` (with `errno = ENOENT` or `EMSGSIZE`).

Source: `source/src/backend/utils/adt/inet_net_pton.c` (562 lines). Historically the **classic buffer-overflow attack surface** — much hardened over decades.

## Key functions

- `pg_inet_net_pton(af, src, dst, size)` (line 61) — top-level dispatcher; size==-1 selects "net" semantics (no must-fit-CIDR), otherwise "cidr". [verified-by-code]
- `inet_cidr_pton_ipv4` (line 95) — accepts hex (`0x` prefix), nybble strings, dotted decimal, with `/CIDR`. Octet bounds checked (`if (tmp > 255) goto enoent`). Buffer bounds checked at every write (`if (size-- <= 0U) goto emsgsize`). [verified-by-code]
- `inet_net_pton_ipv4` (line 257) — decimal-dotted only; default `/32` if all four octets present, else error. [verified-by-code]
- `getbits` (line 346) — parses the `/CIDR` suffix; rejects leading zeros, caps at 128. [verified-by-code]
- `inet_net_pton_ipv6` (around line 400) — IPv6 parser; uses scratch buffer of fixed size, plus `:` and `::` handling.
- `inet_cidr_pton_ipv6` (further down) — same but enforces no host bits set when size > 0.

## Phase D notes

- **Tight bound-check discipline**: every byte written to `dst` is preceded by a `size-- <= 0U` check. Returns `EMSGSIZE` on overflow rather than overrunning. [verified-by-code:127, 156, 195, 281, 332]
- **Octet-bounds check**: `tmp > 255` guard (line 152) and `bits > 32` / `bits > 128` (lines 186, 306, 367) prevent integer overflow into bytes.
- **No leading-zero in CIDR width** (line 363 in getbits) — RFC-aligned but a quirk relative to `/032` user input.
- **`u_char` type used throughout** — assumes 8-bit char; portability is fine on all PG-supported platforms.
- The historical bugs in BIND inet_pton (CVE-2004-0789 family, the "0xABCD" buffer underrun in nybble loops) appear to be addressed: the dirty-flag-and-shift pattern at lines 114-138 only writes on a complete pair of nybbles. [verified-by-code]

## Potential issues

- `[ISSUE-correctness: inet_cidr_pton_ipv4 imputes classful mask widths from leading-octet ranges (lines 200-220 — Class A/B/C/D/E logic); modern users almost never see classful networks, and this silent imputation could surprise (low)]`.
- `[ISSUE-stale-todo: file carries the 2004 rcsid; the "classful imputation" code is 1996-era reasoning. Harmless but worth a comment update (low)]`.
- `[ISSUE-undocumented-invariant: getbits rejects "00" but accepts "0"; "/0" means "match everything" — by design, but easy to mis-write (low)]`.
- `[ISSUE-dead-code: assert() calls at lines 120, 149, 180 etc.; these are libc assert (defined ON in PG builds via NDEBUG?). Verify they're active under cassert. (low)]`.

Confidence: `[verified-by-code]` for IPv4 paths; IPv6 paths reviewed at index level only.
