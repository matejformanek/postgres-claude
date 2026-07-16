---
source_url: https://www.postgresql.org/docs/current/sslinfo.html
fetched_at: 2026-07-15T20:50:00Z
anchor_sha: 8f71f64deee6
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.43 sslinfo — obtain client SSL information"
maps_to_skill: [extension-development, fmgr-and-spi]
---

# Docs distilled — sslinfo (client-TLS introspection from SQL)

SQL-callable access to the *current backend's* TLS state and the client
certificate it presented. Ten scalar/SRF functions over OpenSSL, all
`--with-ssl=openssl`-gated. The natural building block for a certificate-based
authorization policy expressed in SQL (e.g. row-level-security predicates keyed
on the client CN).

## Non-obvious claims

- **Ten `PG_FUNCTION_INFO_V1` functions** in
  `source/contrib/sslinfo/sslinfo.c`: `ssl_is_used` (`:44`), `ssl_version`
  (`:55`), `ssl_cipher` (`:75`), `ssl_client_cert_present` (`:98`),
  `ssl_client_serial` (`:114`), `ssl_client_dn_field` (`:236`),
  `ssl_issuer_field` (`:271`), `ssl_client_dn` (`:299`), `ssl_issuer_dn`
  (`:326`), and the SRF `ssl_extension_info` (`:352`). [verified-by-code]
- **Everything is scoped to the *current* connection** — there is no way to ask
  about another backend's TLS. On a non-SSL connection the functions return
  NULL / false, and the module only builds when PG was compiled with
  `--with-ssl=openssl`. [from-docs]
- **`ssl_client_serial()` returns `numeric`** (cert serials exceed int64), and
  the docs note that **serial is unique only *per issuer*** — pair it with
  `ssl_issuer_dn()` to uniquely identify a certificate. [from-docs]
- **DN encoding gotcha.** `ssl_client_dn()`/`ssl_issuer_dn()` convert non-ASCII
  DN characters to the *current database encoding*; under `SQL_ASCII` they come
  back as raw UTF-8 byte sequences. Field extraction
  (`ssl_client_dn_field('commonName')`, `ssl_issuer_field(...)`) takes
  case-insensitive names/aliases (`CN`, `O`, `OU`, `C`, `emailAddress`, …) and
  returns NULL for an absent field. [from-docs]
- **`ssl_extension_info()` is set-returning** — one row per X.509 extension with
  (name, value, critical-flag), for inspecting SAN, key-usage, etc. [from-docs]
- **Not a trusted extension.** Unlike most contrib in this family, the docs page
  carries no "trusted" note — installation is superuser-only. [inferred]

## Links into corpus

- `[[docs-distilled/ssl-tcp.md]]` — server-side TLS setup; sslinfo reads the
  per-connection result of that configuration.
- `[[docs-distilled/auth-cert.md]]` — `cert` authentication maps the client CN
  to a role; sslinfo exposes the *same* certificate fields to SQL for finer
  authorization after auth succeeds.
- `[[docs-distilled/pgcrypto.md]]` — sibling OpenSSL-linked contrib; both need
  `--with-ssl=openssl`.
- `row-level-security` skill — sslinfo's DN-field extractors are the usual source
  for a certificate-keyed RLS `USING` predicate.
