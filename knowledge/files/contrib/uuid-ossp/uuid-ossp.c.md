# `contrib/uuid-ossp/uuid-ossp.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~555
- **Source:** `source/contrib/uuid-ossp/uuid-ossp.c`

Single-source UUID-generation contrib module that wraps **one of
three** system UUID libraries — OSSP libuuid (`HAVE_UUID_OSSP`),
e2fsprogs libuuid (`HAVE_UUID_E2FS`), or BSD's `uuid_create`
(`HAVE_UUID_BSD`) — chosen at `./configure` time via
`--with-uuid=ossp|e2fs|bsd`. Provides the standard SQL functions
`uuid_generate_v1`, `uuid_generate_v1mc`, `uuid_generate_v3`,
`uuid_generate_v4`, `uuid_generate_v5`, plus the well-known
namespace constants. **Note:** since PG 13, modern PG can produce
v4 UUIDs in core (`gen_random_uuid()` in pgcrypto/built-in) and PG
18 added native v7 — so uuid-ossp is increasingly legacy. [verified-by-code]

## API / entry points

- Constant-value functions: `uuid_nil`, `uuid_ns_dns`, `uuid_ns_url`,
  `uuid_ns_oid`, `uuid_ns_x500` (lines 423-481) — return DCE 1.1
  standard namespace UUIDs. OSSP path calls `uuid_load("nil")` etc.;
  the E2FS/BSD path hard-codes the literal UUID string and parses
  through `uuid_in`. [verified-by-code]
- `uuid_generate_v1` (line 484) — time + node-based UUID. Uses host
  MAC address if available (privacy concern; the v1mc variant is
  preferred). [verified-by-code]
- `uuid_generate_v1mc` (line 491) — v1 with random multicast MAC
  instead of physical MAC. OSSP uses `UUID_MAKE_V1 | UUID_MAKE_MC`;
  E2FS uses `uuid_generate_random` then forces the multicast bit;
  BSD synthesizes the trailing 13 chars via `arc4random()`.
  [verified-by-code]
- `uuid_generate_v3` / `uuid_generate_v5` (lines 521, 543) —
  namespace+name UUIDs via MD5 / SHA1 respectively. Non-OSSP path
  uses `pg_cryptohash_*` from `common/cryptohash.h` (so works
  regardless of OpenSSL availability). [verified-by-code]
- `uuid_generate_v4` (line 537) — random UUID. E2FS uses
  `uuid_generate_random` (which itself reads `/dev/urandom`); BSD
  uses `arc4random()`. **No call to PG's own `pg_strong_random()`**
  — the per-backend caching of OSSP / library state means RNG
  source is library-dependent. [verified-by-code]

## Notable invariants / details

- **RNG-source variance is the headline.** Three backends, three
  different paths:
  - OSSP → uses OSSP's internal `/dev/urandom` reads + cached uuid_t.
  - E2FS → `uuid_generate_random()` from e2fsprogs (also
    `/dev/urandom`-based but library-specific seeding).
  - BSD → `arc4random()` (cryptographically strong on modern BSDs
    and glibc 2.36+, but pre-2.36 glibc's arc4random was
    insecure-by-default seeded from rand()).
  None of these are PG's `pg_strong_random()`. A site that has
  audited PG's CSPRNG (pgcrypto, gen_random_uuid in core) cannot
  assume uuid-ossp uses the same. [verified-by-code]
  [ISSUE-security: RNG source is configure-time-dependent and
  not documented in user-facing docs; v4 UUIDs may come from
  arc4random / e2fs RNG / OSSP RNG with different strength
  profiles (maybe — all three are CSPRNG-grade on supported
  platforms but the variance is surprising)].
- **OSSP UUID cache** (`get_cached_uuid_t`, line 156): two static
  `uuid_t*` slots. The comment block (lines 139-155) explains why:
  OSSP caches MAC address and entropy state, and v3/v5 need two
  uuid_t's (namespace + result). Cache is per-backend, never
  freed; small constant memory. [verified-by-code]
- **BSD NetBSD quirk** (lines 292-301): recent NetBSD's
  `uuid_create()` returns v4 instead of v1 (NetBSD considers
  MAC-disclosing v1 a privacy bug). PG checks `strbuf[14]` (the
  version-nibble position) and errors if it's not `'1'`. This is
  a defensive check that surfaces a configure-time mismatch as a
  runtime error. [verified-by-code]
- **uuid_hash conflict** (lines 30-43): BSD's `<uuid.h>` exports
  `uuid_hash` which collides with PG's `uuid_hash` in
  `utils/builtins.h`. Workaround: `#define uuid_hash bsd_uuid_hash`
  before the include, then `#undef` after. This is a system-header-
  versus-PG-internal name clash that has survived since 2009.
  [verified-by-code]
- **uuid.h discovery preference** (lines 33-41): tries `<uuid.h>`
  (BSD), then `<ossp/uuid.h>` (OSSP), then `<uuid/uuid.h>` (e2fs).
  Configure script sets exactly one `HAVE_UUID_*` symbol; the C
  code expects that. [verified-by-code]
- **v3 / v5 byte-order handling** (lines 371, 376): hash result is
  in host order; UUID-on-wire is network order, so
  `UUID_TO_NETWORK` swaps. For E2FS's `uuid_unparse` we then
  `UUID_TO_LOCAL` back because that function expects local order.
  BSD's `uuid_to_string` reads the struct fields directly so no
  un-swap. Subtle and easy to break. [verified-by-code]

## Potential issues

- Lines 401-411: v4 BSD path uses **six** `arc4random()` calls but
  could use a single read; this is a stylistic nit, not a security
  issue (arc4random is reentrant + cheap). [ISSUE-style:
  unnecessary arc4random call count (nit)].
- Line 296: NetBSD-version detection is by examining the
  generated UUID's version nibble. If the OS upgrade lands
  between session start and call, mid-session, the assert holds;
  but the error message ("uuid_create() produced version %c
  instead of expected 1") doesn't tell the admin to switch
  to `--with-uuid=e2fs` or `gen_random_uuid()`. [ISSUE-error-
  handling: actionable hint missing (nit)].
- Lines 333-348 / 352-367: MD5 / SHA1 contexts allocated on each
  call. `pg_cryptohash_create` palloc's a context every call —
  for high-rate v3/v5 generation this is measurable allocation
  churn. Caching parallel to `get_cached_uuid_t` would help.
  [ISSUE-style: per-call cryptohash context allocation (nit)].
- Line 504: `((dce_uuid_t *) &uu)->node[0] |= 0x03` — casts `uuid_t`
  (an opaque library type) to `dce_uuid_t` (PG's own struct).
  Relies on e2fsprogs' `uuid_t` being layout-compatible with
  the DCE 1.1 byte layout. That's been true forever but is not
  guaranteed by the e2fsprogs API. [ISSUE-undocumented-invariant:
  uuid_t / dce_uuid_t layout-compat assumption (nit)].
- The OSSP library is **unmaintained since 2008** but is still
  the default name in `--with-uuid=ossp`. Multiple distros
  package it; security/CVE response is on those packagers.
  [ISSUE-security: dependency on unmaintained OSSP libuuid
  (maybe — many sites use e2fs path instead)].
- `decimal_constructor`-style: not applicable here; no global
  Python state.

## Cross-references

- Core PG: `src/backend/utils/adt/uuid.c` — `uuid_in`/`uuid_out`,
  `gen_random_uuid()` (PG 13+), `gen_uuid_v7()` (PG 18+). Many
  uuid-ossp use cases are superseded by these.
- `src/include/common/cryptohash.h` — provides the MD5/SHA1
  used in v3/v5 generation; no OpenSSL dependency.
- `arc4random` is provided by libc on BSDs and modern glibc; PG
  does NOT carry a portable arc4random fallback for uuid-ossp.

<!-- issues:auto:begin -->
- [Issue register — `uuid-ossp`](../../../issues/uuid-ossp.md)
<!-- issues:auto:end -->
