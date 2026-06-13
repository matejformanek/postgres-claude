# contrib-sslinfo (SSL/TLS connection introspection)

- **Source path:** `source/contrib/sslinfo/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.2` (per `sslinfo.control`)
- **Trusted:** no (exposes auth-relevant info)

## 1. Purpose

Expose **SSL/TLS connection metadata** to SQL — whether the
current connection uses SSL, the version, the cipher suite,
the client certificate's subject and issuer DN, etc. Useful
for:

- **Audit logging**: record per-row which TLS version + cipher
  was active.
- **Row-level access control**: gate rows on client certificate
  attributes.
- **Compliance reporting**: confirm all connections use
  acceptable cipher suites.

Only works for connections that actually used SSL. On a
non-SSL connection, every function returns NULL or false.

## 2. SQL surface

[verified-by-code `sslinfo.c:44-271`]

| Function | Returns |
|---|---|
| `ssl_is_used()` | bool — true if SSL/TLS in use |
| `ssl_version()` | text — e.g. 'TLSv1.3' |
| `ssl_cipher()` | text — e.g. 'TLS_AES_256_GCM_SHA384' |
| `ssl_client_cert_present()` | bool — true if client cert supplied |
| `ssl_client_serial()` | numeric — cert serial number |
| `ssl_client_dn()` | text — full subject DN |
| `ssl_client_dn_field(field)` | text — extract one field by OID |
| `ssl_issuer_dn()` | text — issuer DN |
| `ssl_issuer_field(field)` | text — extract issuer field |
| `ssl_extension_info()` | SETOF text — cert X.509 extensions |

The most common: `ssl_is_used`, `ssl_version`,
`ssl_client_dn`.

## 3. The audit pattern

```sql
INSERT INTO audit_log (user, ts, ssl_v, ssl_cipher, client_cn)
VALUES (
    CURRENT_USER, now(),
    ssl_version(),
    ssl_cipher(),
    ssl_client_dn_field('commonName')
);
```

Per-row capture of TLS state. Combined with a BEFORE
trigger, every business operation gets tagged with the
SSL context that authorized it.

## 4. The row-level access pattern

```sql
CREATE POLICY only_engineering ON sensitive
USING (
    ssl_client_dn_field('organizationalUnit') = 'engineering'
);
```

Row-level security based on the client certificate's OU
field. Combined with `pg_hba.conf` requiring cert auth,
this means: connect with the right cert OR see nothing.

## 5. The field-extraction by OID

`ssl_client_dn_field('commonName')` extracts one field of
the subject DN by its OID short name. Common short names:

| Short name | OID | Common content |
|---|---|---|
| `commonName` | 2.5.4.3 | Hostname / username |
| `organizationName` | 2.5.4.10 | Company name |
| `organizationalUnit` | 2.5.4.11 | Department / team |
| `countryName` | 2.5.4.6 | 2-letter country code |
| `localityName` | 2.5.4.7 | City |
| `stateOrProvinceName` | 2.5.4.8 | State |

The function returns NULL if the field is absent from the
cert.

## 6. The cert-extensions function

`ssl_extension_info()` returns a set of `(name, value,
critical)` rows for each X.509 extension on the client cert.
Useful for inspecting unusual fields:

```sql
SELECT * FROM ssl_extension_info();
-- name           | value              | critical
-- subjectAltName | DNS:example.com    | f
-- keyUsage       | digitalSignature   | t
-- ...
```

## 7. Permission model

The extension is **not trusted** — `CREATE EXTENSION sslinfo`
requires superuser by default. The reason: exposing per-
connection auth state is a privilege escalation risk if
misused.

Most production deployments install + grant EXECUTE on
specific functions to specific roles.

## 8. The OpenSSL dependency

[`sslinfo.c` uses OpenSSL APIs directly]

The extension reads from the SSL context's BIO (`MyProcPort->
ssl`). If PG is built without `--with-openssl`, sslinfo is
not buildable.

For builds with newer OpenSSL or alternate TLS stacks
(GnuTLS, OpenSSL 3.x), the function set may differ
slightly. The `ssl_extension_info` requires OpenSSL 1.0.2+.

## 9. The connection-private state

The SSL context is per-connection, stored in `MyProcPort`.
sslinfo's functions read from there directly — no shared
state, no synchronization needed.

Inside a connection pooler that multiplexes backends
(pgbouncer, pgpool), sslinfo reflects the pooler's
connection to the database, NOT the client's connection
to the pooler. Plan auditing accordingly.

## 10. Production-use guidance

- **For compliance audit**, sslinfo + row-trigger is the
  canonical pattern.
- **For row-level security via cert attributes**, combine
  with RLS policies.
- **For connection-pooler users**, sslinfo describes the
  pooler-to-DB session, not the original client.
- **Build flag**: `--with-openssl` required.

## 11. Invariants

- **[INV-1]** Non-SSL connections return NULL / false.
- **[INV-2]** Per-connection state; no shared state.
- **[INV-3]** Field extraction is by OID short name; NULL on
  missing.
- **[INV-4]** Requires `--with-openssl` build.
- **[INV-5]** Not trusted; CREATE EXTENSION requires
  superuser.

## 12. Useful greps

- All entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/sslinfo/sslinfo.c`
- The SSL context access:
  `grep -n 'MyProcPort->ssl\|MyProcPort->peer_cn' source/contrib/sslinfo/sslinfo.c | head -10`
- Cert DN parsing:
  `grep -n 'X509_NAME\|X509_get_ext' source/contrib/sslinfo/sslinfo.c | head -10`

## 13. Cross-references

- `.claude/skills/extension-development/SKILL.md` — extension
  loading; OpenSSL build flag.
- `knowledge/subsystems/contrib-pgcrypto.md` — companion
  OpenSSL-using contrib.
- `knowledge/subsystems/libpq-backend.md` — connection
  management; `MyProcPort` lives here.
- `.claude/skills/catalog-conventions/SKILL.md` — function
  registration in pg_proc.
- `source/contrib/sslinfo/sslinfo.c` — implementation.
