# inet_cidr_ntop.c — inet → presentation-format string

## Purpose

The address→text half of inet I/O. `pg_inet_cidr_ntop` dispatches on AF and writes a presentation-format string (e.g. `192.168.1.0/24`, `fe80::1/64`) into a caller-provided buffer. Mostly imported from ISC BIND9 with PG-specific tweaks.

Source: `source/src/backend/utils/adt/inet_cidr_ntop.c` (294 lines).

## Key functions

- `pg_inet_cidr_ntop(af, src, bits, dst, size)` (line 56) — top-level dispatcher. [verified-by-code]
- `inet_cidr_ntop_ipv4` (line 85) — emits dotted-quad + `/bits`. Walks octets, writes via `snprintf`. [verified-by-code]
- `inet_cidr_ntop_ipv6` (line 165) — emits compressed IPv6 + `/bits`. Implements `::` compression for the longest run of zero words. [verified-by-code]

## Phase D notes

- **Size-bound discipline**: every write into `dst` checks remaining space via the `size` parameter, returns `NULL` with `errno = ENOSPC` on overflow. The callers in `network.c` (`inet_out`/`cidr_out`) palloc a buffer sized for the worst case, so overflow cannot actually happen at runtime — but the defensive bound is present. [verified-by-code]
- **No buffer-over-read**: input is bounded by `bits / 8`.
- This is the historical pair to `inet_net_pton.c`; both came from BIND9 with minor PG adjustments (palloc replacement of malloc).

## Potential issues

- `[ISSUE-correctness: if a future caller computes `size` from VARSIZE without accounting for the trailing /bits suffix, ntop could return NULL and the caller might ereport on a value that should have stringified. Today callers compute correctly (low)]`.
- `[ISSUE-stale-todo: the file still carries an "Id:" rcsid line from BIND CVS history (line 21); cosmetic but indicates lightly-touched code (low)]`.
- `[ISSUE-dead-code: the LIBC_SCCS guard at line 20 dates to the BIND9 import; harmless but worth a future cleanup (low)]`.

Confidence: `[verified-by-code]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
