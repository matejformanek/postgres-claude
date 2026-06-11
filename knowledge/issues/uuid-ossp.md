# Issues — `contrib/uuid-ossp`

Per-subsystem issue register for **uuid-ossp**, the UUID-generation
contrib module wrapping one of three system UUID libraries
(OSSP / e2fsprogs / BSD). Single-file extension, ~555 LOC.

**Parent docs:** `knowledge/files/contrib/uuid-ossp/uuid-ossp.c.md`

**Source:** sweep A21-D, 2026-06-11.

## Headlines

1. **RNG-source varies by configure flag.** v4 UUIDs come from OSSP
   internal RNG, e2fsprogs `uuid_generate_random`, or BSD
   `arc4random` depending on `--with-uuid=ossp|e2fs|bsd`. PG's own
   `pg_strong_random()` is **not** used. All three are CSPRNG-grade
   on supported platforms, but the variance is surprising and
   user-facing docs don't call it out. Sites that have audited
   pgcrypto's `gen_random_uuid` cannot assume the same RNG is used
   here.

2. **OSSP libuuid is unmaintained since 2008.** Yet `--with-uuid=ossp`
   is still supported and packaged by distros. CVE response is on
   the packager. Many sites use `--with-uuid=e2fs` instead;
   `--with-uuid=bsd` only on \*BSD.

3. **uuid_hash symbol clash.** BSD's `<uuid.h>` exports `uuid_hash`
   which collides with PG's `uuid_hash` in `utils/builtins.h`.
   Worked around since 2009 by `#define uuid_hash bsd_uuid_hash`.
   Survives because no one's removed BSD support.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | uuid-ossp.c:401-411 | security | maybe | v4 RNG source is configure-time-dependent (OSSP / e2fs / arc4random); user-facing docs don't disclose the variance | open | files/contrib/uuid-ossp/uuid-ossp.c.md |
| 2026-06-11 | uuid-ossp.c (whole file) | security | maybe | Dependency on unmaintained OSSP libuuid (last release 2008) when `--with-uuid=ossp` | open | files/contrib/uuid-ossp/uuid-ossp.c.md |
| 2026-06-11 | uuid-ossp.c:292-301 | error-handling | nit | NetBSD v4-instead-of-v1 detection error lacks actionable hint (suggest `--with-uuid=e2fs` or `gen_random_uuid()`) | open | files/contrib/uuid-ossp/uuid-ossp.c.md |
| 2026-06-11 | uuid-ossp.c:333-365 | style | nit | Per-call `pg_cryptohash_create` palloc churn for v3/v5; cache analogous to `get_cached_uuid_t` would help | open | files/contrib/uuid-ossp/uuid-ossp.c.md |
| 2026-06-11 | uuid-ossp.c:503 | undocumented-invariant | nit | `uuid_t` → `dce_uuid_t` cast for v1mc relies on e2fsprogs layout compatibility (not API-guaranteed) | open | files/contrib/uuid-ossp/uuid-ossp.c.md |
| 2026-06-11 | uuid-ossp.c:401-411 | style | nit | v4 BSD path uses six `arc4random()` calls; could be a single read | open | files/contrib/uuid-ossp/uuid-ossp.c.md |
| 2026-06-11 | uuid-ossp.c:14 (hstore-bridges) | dead-path | nit | `hstoreUpgrade_p` analogue does not apply here, but: many uuid-ossp use cases are superseded by core `gen_random_uuid()` (PG 13+) and `gen_uuid_v7` (PG 18+) | open | files/contrib/uuid-ossp/uuid-ossp.c.md |

## Cross-references

- **A13-1 hstore + A13-2 ltree + A13-3 btree_gist** sweep on
  attacker-controlled-data → unrelated; uuid-ossp doesn't process
  user-supplied strings beyond v3/v5 namespace+name input.
- **`src/backend/utils/adt/uuid.c`** — core UUID type; `uuid_in` /
  `uuid_out` / `gen_random_uuid` / `gen_uuid_v7` live there.
- **`src/include/common/cryptohash.h`** — MD5/SHA1 backends used in
  v3/v5; no OpenSSL dependency.

## Notes

The OSSP cache (`get_cached_uuid_t`) is per-backend, never freed —
small constant memory. Two slots: one for result, one for v3/v5
namespace holder. Comment block at lines 139-155 is unusually
detailed and explains the design rationale (avoid v1 collisions on
fast machines, save entropy, save MAC lookups).

PG 18 added native UUID v7 generation; PG 13 added native v4
(`gen_random_uuid`). The case for keeping uuid-ossp installed is
shrinking: only v1, v1mc, v3, v5 are not in core, and v1/v1mc leak
MAC addresses (privacy concern). v3/v5 namespace UUIDs are the
remaining unique value-add.
