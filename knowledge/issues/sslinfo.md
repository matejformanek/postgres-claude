# Issues — `contrib/sslinfo`

Per-subsystem issue register for **sslinfo**, the TLS-connection
introspection extension (peer cert fields, cipher, version exposed
to SQL). 1 source file / 476 LOC.

**Parent doc:** `knowledge/files/contrib/sslinfo/sslinfo.c.md`.

**Source:** 12 entries surfaced 2026-06-09 by A12-4.

## Headlines

1. **NO superuser/role check on any function.** Default PUBLIC
   EXECUTE per typical contrib `.sql`. Cert metadata callable by
   any role on a TLS connection — useful for app-layer auth but
   "function throws on no-TLS vs returns NULL" is probeable.

2. **`ssl_issuer_field` has weaker gate than sibling
   `ssl_client_dn_field`** — checks `!MyProcPort->peer` instead of
   `!ssl_in_use || !peer_cert_valid`. **Can return issuer-DN data
   from an UNVERIFIED cert** while the sibling requires
   verification. Asymmetric gate is a confirmed correctness issue.

3. **`cstring_to_text` is strlen-based** — embedded NUL in DN
   truncates silently. Potential security-sensitive bypass for CN
   comparisons: an attacker presenting a cert with
   `CN=admin.example.com\0attacker.example.com` could pass
   string-compare against `admin.example.com`.

4. **`ssl_extension_info` value-field bypasses `pg_any_to_server`**
   — non-UTF8 extension bytes land in text columns without
   sanitization. Other DN paths use RFC 2253 minus ESC_MSB +
   UTF8_CONVERT, then `pg_any_to_server`.

## Cross-sweep references

- **A2 libpq SSL/TLS** — sslinfo wraps `be_tls_get_*` helpers; the
  cert-validation discipline lives in libpq-backend.
- **A11 postgres_fdw cross-cluster trust boundary** — sslinfo
  values feed app-layer trust decisions; a CN-truncation bypass
  here propagates into any framework relying on this for auth.

## Entries (12)

- [ISSUE-security: NO superuser/role check on any function; default
  PUBLIC EXECUTE; cert metadata callable by any role on a TLS
  connection (likely)] — `source/contrib/sslinfo/sslinfo.c`.
- [ISSUE-security: `ssl_issuer_field` checks `!MyProcPort->peer`
  instead of `!ssl_in_use || !peer_cert_valid` — can return
  issuer-DN data from an UNVERIFIED cert while sibling
  `ssl_client_dn_field` requires verification (confirmed —
  asymmetric gate)].
- [ISSUE-security: `cstring_to_text` strlen-based — embedded NUL in
  DN truncates silently (potential CN-comparison bypass) (likely)].
- [ISSUE-correctness: `ssl_extension_info` value-field BYPASSES
  `pg_any_to_server` — non-UTF8 extension bytes land in text
  columns without sanitization (likely)].
- [ISSUE-error-handling: function-throws-on-no-TLS vs returns-NULL
  inconsistency = probeable side channel for "is TLS active"
  detection (nit)].
- [ISSUE-correctness: RFC 2253 minus ESC_MSB encoding deviates from
  strict spec for backwards compat; DN string format may differ
  from other LDAP/X.509 tooling (nit)].
- [ISSUE-defense-in-depth: no length cap on returned DN/cert-field
  strings; pathologically large certs = palloc pressure (nit)].
- [ISSUE-correctness: `X509_NAME_print_ex` wrapping — known OpenSSL
  function with historical encoding gotchas (nit)].
- [ISSUE-documentation: per-function role assumptions not
  documented in `sslinfo--*.sql` (nit)].
- [ISSUE-defense-in-depth: uses stable OpenSSL X509/ASN1 API from
  1.1.0+; no OpenSSL 3.0 `EVP_*_fetch`-style migration (nit)].
- [ISSUE-error-handling: `ssl_extension_info` SRF; cert-parsing
  errors from a malicious peer could trip OpenSSL parsers
  mid-iteration (nit)].
- [ISSUE-audit-gap: no audit log when sslinfo functions are called
  — no record of who queried peer-cert details (nit)].
