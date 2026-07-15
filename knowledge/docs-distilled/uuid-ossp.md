---
source_url: https://www.postgresql.org/docs/current/uuid-ossp.html
fetched_at: 2026-07-15T20:50:00Z
anchor_sha: 8f71f64deee6
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.52 uuid-ossp — a UUID generator"
maps_to_skill: [extension-development, fmgr-and-spi]
---

# Docs distilled — uuid-ossp (v1/v3/v4/v5 UUID generation)

The legacy UUID-generation contrib. Now **mostly redundant**: core PostgreSQL
supplies `gen_random_uuid()` (v4) and `uuidv7()` (v7), so this module is only
needed for the *namespace/timestamp* variants — v1 (MAC+time), v3 (MD5-named),
v5 (SHA-1-named). A clean example of SQL-callable C functions that wrap an
external library chosen at configure time.

## Non-obvious claims

- **Five generators + five constants**, all `PG_FUNCTION_INFO_V1` in
  `source/contrib/uuid-ossp/uuid-ossp.c`: `uuid_generate_v1` (`:116`), `_v1mc`
  (`:117`), `_v3` (`:118`), `_v4` (`:119`), `_v5` (`:120`); constants
  `uuid_nil` (`:110`), `uuid_ns_dns` (`:111`), `uuid_ns_url` (`:112`),
  `uuid_ns_oid` (`:113`), `uuid_ns_x500` (`:114`). [verified-by-code]
- **v1 leaks identity + time.** `uuid_generate_v1()` embeds the host MAC address
  and a timestamp — the docs flag it as unsuitable where those must stay secret.
  `uuid_generate_v1mc()` substitutes a **random multicast MAC** to mitigate the
  MAC leak (the timestamp is still present). [from-docs]
- **v3 and v5 are deterministic** — `uuid_generate_v3(namespace, name)` and
  `_v5(namespace, name)` hash `name` within `namespace` (MD5 for v3, SHA-1 for
  v5) with **no random/environmental input**, so the same (namespace,name) always
  yields the same UUID. The docs **recommend v5 over v3** (SHA-1 > MD5). The
  cleartext name is not recoverable from the UUID. v3/v5 share one internal
  path — `uuid_generate_v35_internal(mode, ns, name)` at `uuid-ossp.c:235`,
  dispatched via `UUID_MAKE_V3`/`UUID_MAKE_V5` (`:528`). [verified-by-code]
- **Namespace constants are the RFC 4122 well-knowns** — DNS, URL, ISO-OID (ASN.1
  OIDs, **not** PostgreSQL OIDs), X.500 DN. Example:
  `uuid_generate_v3(uuid_ns_url(), 'http://www.postgresql.org')`. `uuid_nil()`
  is the all-zero UUID that never occurs naturally. [from-docs]
- **Underlying library is a configure-time choice** — `--with-uuid=` selects
  `bsd` (libc, BSD), `e2fs`/`ossp` (`libuuid` from util-linux/e2fsprogs on
  Linux/macOS), or the old OSSP library. The OSSP library is poorly maintained;
  the module name is historical. [from-docs]
- **Prefer core for new code.** For v4 use core `gen_random_uuid()` (no
  extension); for time-ordered keys use core `uuidv7()`. Reach for uuid-ossp
  only when you specifically need v1/v3/v5. [from-docs]
- **Trusted extension** — installable by a non-superuser with `CREATE` on the
  database. [from-docs]

## Links into corpus

- `[[docs-distilled/pgcrypto.md]]` — the other UUID surface: pgcrypto's
  `gen_random_uuid()` is a v4 shim to core; uuid-ossp adds the named/timestamp
  variants. Neither is needed for plain v4/v7 anymore.
- `fmgr-and-spi` skill — a compact set of scalar C functions wrapping an
  external, configure-selected library; a good template for "optional
  third-party dependency chosen at build time".
