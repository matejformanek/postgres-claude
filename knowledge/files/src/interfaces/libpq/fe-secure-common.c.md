---
path: src/interfaces/libpq/fe-secure-common.c
anchor_sha: 4b0bf0788b0
loc: 307
depth: medium
---

# fe-secure-common.c

- **Source path:** `source/src/interfaces/libpq/fe-secure-common.c`
- **Lines:** 307
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-secure-common.h`, `fe-secure-openssl.c` (the only consumer today, calls in via `pgtls_verify_peer_name_matches_certificate_guts`), `libpq-int.h` (`PGconn.connhost`, `sslmode`).

## Purpose

TLS-library-agnostic hostname-vs-certificate matching. The OpenSSL backend (or any future backend) calls into these helpers with raw bytes from the certificate; this file handles wildcard rules, embedded-NUL detection, IP-address normalization, and the "no match" error message. [verified-by-code, fe-secure-common.c:5-9]

## Public surface

- `pq_verify_peer_name_matches_certificate_name(conn, namedata, namelen, store_name)` (86-144) — DNS-name comparison.
- `pq_verify_peer_name_matches_certificate_ip(conn, ipdata, iplen, store_name)` (156-244) — IP-address comparison.
- `pq_verify_peer_name_matches_certificate(conn)` (251-307) — orchestrator. Only checks when `sslmode == verify-full`; otherwise returns true.

## Internal

- `wildcard_certificate_match(pattern, string)` (44-75) — implements the leading-`*.` rule.

## Wildcard rules (security-critical)

The wildcard match is **stricter** than browsers but loosely follows RFC 2818:

1. Only `*` is a wildcard (not `?`).
2. Wildcard must be at the **start** of the pattern, followed by a literal `.`. `*foo` and `foo*` are rejected as non-wildcards. [verified-by-code, fe-secure-common.c:50-54]
3. `*` does NOT match a `.` — so `*.example.com` matches `a.example.com` but not `b.a.example.com`. [verified-by-code, fe-secure-common.c:35-37, 67-71]
4. At most one `*` per pattern (implicit from the start-only rule). [from-comment, fe-secure-common.c:37]

Implementation: pattern minus the leading `*` must equal the tail of the string (case-insensitively), and there must be no `.` left of where the wildcard "consumed". [verified-by-code, fe-secure-common.c:62-72]

## Invariants & gotchas

- **Embedded-NUL defense (CVE-2009-4034).** A certificate name with an embedded NUL byte (e.g. `evil.com\0good.com`) is rejected if `namelen != strlen(name)` after the copy+nul-terminate. Critical: without this, a CA that issues for `good.com` could be hijacked by an attacker who got a name with a hidden NUL. [verified-by-code, fe-secure-common.c:117-125]
- **`inet_aton` not `inet_pton` for IPv4.** Intentionally lenient: accepts shorthand IP forms like `127.1` that `inet_pton` rejects, because libpq has always accepted those as connection-host strings. [from-comment, fe-secure-common.c:191-194; verified-by-code:196]
- **IPv6 path needs `HAVE_INET_PTON`.** If the platform lacks `inet_pton`, an IPv6 SAN in a cert causes an error (line 222-230 falls through). [verified-by-code, fe-secure-common.c:207-230]
- **`verify-full` gate.** `pq_verify_peer_name_matches_certificate` returns true (success) when `sslmode != verify-full` — meaning under `verify-ca` the certificate must chain to a trusted root, but the *hostname* check is skipped. This is the documented contract; users wanting hostname binding must set `verify-full`. [verified-by-code, fe-secure-common.c:263-264]
- The orchestrator delegates the cert-name extraction to `pgtls_verify_peer_name_matches_certificate_guts` (defined in fe-secure-openssl.c:545) — that function decides SAN-vs-CN priority, see ISSUE-libpq-openssl-002.

## Potential issues

- ISSUE-libpq-common-001 (severity: maybe) — `pq_verify_peer_name_matches_certificate_ip` returns -1 only for "iplen not 4 or 16" or `pg_inet_net_ntop` failure. If the host string fails to parse as either IP family (e.g. ill-formed user input), the function returns 0 (no match) rather than -1 (error). The downstream error message then becomes "server certificate does not match host name" — misleading when the *host* was invalid, not the cert. [verified-by-code, fe-secure-common.c:184-220]
- ISSUE-libpq-common-002 (severity: maybe) — the wildcard match is case-insensitive via `pg_strcasecmp` (line 63), which assumes ASCII. Internationalized cert names (IDN, punycoded) are byte-compared. Since libpq does not perform IDN normalization on its `host=` parameter, a cert issued for the punycode form `xn--bcher-kva.com` will not match a connection to a UTF-8 hostname. [inferred, fe-secure-common.c:63]

## Cross-refs

- Caller: `fe-secure-openssl.c::pgtls_verify_peer_name_matches_certificate_guts` (line 545).
- Header: `fe-secure-common.h`.

## Tally
`[verified-by-code]=12 [from-comment]=2 [from-readme]=0 [inferred]=1 [unverified]=0`
