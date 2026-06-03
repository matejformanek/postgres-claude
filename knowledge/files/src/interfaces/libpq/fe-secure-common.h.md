---
path: src/interfaces/libpq/fe-secure-common.h
anchor_sha: 4b0bf0788b0
loc: 30
depth: shallow
---

# fe-secure-common.h

- **Source path:** `source/src/interfaces/libpq/fe-secure-common.h`
- **Lines:** 30
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-secure-common.c`, `fe-secure-openssl.c` (the OpenSSL-specific code that calls into these helpers via `pgtls_verify_peer_name_matches_certificate_guts`).

## Purpose

Library-independent SSL helpers — string and IP comparison routines that compare a certificate subject name against the hostname libpq was told to connect to. Shared between any future TLS backend (today: only OpenSSL). [verified-by-code, fe-secure-common.h:1-13]

## API surface

- `pq_verify_peer_name_matches_certificate_name(conn, namedata, namelen, store_name)` (21) — DNS-name match: exact, case-insensitive, with single-`*` leading wildcard allowed. `*store_name` returns a strdup of the certificate name (for error messages). Returns 1 on match, 0 on no match, -1 on error. [verified-by-code, fe-secure-common.h:21-23; fe-secure-common.c:86-144]
- `pq_verify_peer_name_matches_certificate_ip(conn, ipdata, iplen, store_name)` (24) — for `iPAddress` SAN entries; iplen must be 4 (IPv4) or 16 (IPv6). [verified-by-code, fe-secure-common.h:24-27; fe-secure-common.c:156-244]
- `pq_verify_peer_name_matches_certificate(conn)` (28) — the top-level "should we accept this peer?" entry point. Only runs if `sslmode == verify-full`. [verified-by-code, fe-secure-common.h:28; fe-secure-common.c:251-307]

## Invariants & gotchas

- All three return values use the three-way 1/0/-1 convention — easy to misread as a bool. The dispatch in `pq_verify_peer_name_matches_certificate` checks `rc == 1`, not truthiness. [verified-by-code, fe-secure-common.c:306]
- `store_name` is only written on the name-comparison helpers (1/0/-1 paths), not on early-error paths. Callers must initialize to NULL before calling. [verified-by-code, fe-secure-common.c:95, 169]

## Cross-refs

- Implementation: `fe-secure-common.c` (307 LOC).
- OpenSSL bridge: `fe-secure-openssl.c::pgtls_verify_peer_name_matches_certificate_guts` and the two `openssl_verify_peer_name_matches_certificate_*` wrappers (fe-secure-openssl.c:469-522).

## Tally
`[verified-by-code]=7 [from-comment]=0 [from-readme]=0 [inferred]=0 [unverified]=0`
