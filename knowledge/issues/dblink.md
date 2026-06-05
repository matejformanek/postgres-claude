# Issues — `contrib/dblink`

Per-subsystem issue register for **dblink**, the cross-cluster query
bridge. 1-file extension (`dblink.c`, 3 272 LOC). Opens libpq
connections to other PG clusters using user-supplied conninfo; the
**older** of the two cross-cluster trust-boundary modules in
contrib/ (the **newer** is `postgres_fdw`).

**Parent doc:** `knowledge/files/contrib/dblink/dblink.c.md`.

**Source:** 12 entries surfaced 2026-06-04 by the A11 foreground sweep
(agent A11-1). Mirrored in the per-file doc's `## Issues spotted`
block.

## Headlines

1. **Conninfo-trust model has zero host-restriction enforcement.**
   Any role permitted to `dblink_connect` (non-superuser if they
   provide a password explicitly) can target `localhost:5432` and
   ride local-trust pg_hba rules to escalate. **Canonical
   loopback-to-bypass-RLS / privilege-escalation surface.**
   `dblink_security_check` correctly gates credentials channel but
   NOT host.

2. **`dblink_security_check` correctly requires both
   `PQconnectionUsedPassword` AND `dblink_connstr_has_pw`** —
   prevents `.pgpass` / `PGPASSWORD`-env exploitation. But this
   ordering invariant depends entirely on `dblink_connstr_check`
   running first; if a future patch reorders calls in
   `dblink_connect`, the env-var leak returns. **Phase D
   recommendation: add a fixed-name guard test asserting the two
   checks fire in this exact order.**

3. **`dblink_get_connections` has no ACL gate** — cross-SET ROLE
   leakage within a shared backend session.

4. **Connection-cache key is NAMEDATALEN-truncated identifier** —
   two long connection names sharing a prefix collide. Joins
   corpus-wide NAME-vs-OID Phase D pattern.

5. **Superuser bypasses `dblink_security_check` entirely** — no
   audit log of cross-cluster connect attempts; superuser→other-
   cluster pivot is invisible.

## Cross-sweep references

- **postgres_fdw is the modern equivalent** (A11-2) — same
  trust-boundary class. postgres_fdw has stronger
  `password_required` enforcement and connection cache keyed by
  `(umid)` with explicit superuser-shareable rules; dblink has
  weaker discipline and no `application_name` injection prevention.
- **A2 libpq sweep**: dblink's `dblink_security_check` mirrors the
  libpq-side `password_required` invariant added in CVE-2023-5869.
- **NAME-vs-OID Phase D pattern**: dblink's connection-cache key +
  NAME-truncated identifier joins A3+A6+A7+A8+A9+A10+A11.

## Entries

- [ISSUE-security: loopback dblink bypasses pg_hba host-based
  restrictions when local auth is trust/peer (likely)] —
  `source/contrib/dblink/dblink.c:2864` — conninfo-trust model
  accepts any host; pg_hba is sole remote defense; loopback as
  RLS-bypass / privilege-escalation surface.
- [ISSUE-defense-in-depth: unbounded named-connection cache per
  backend (maybe)] — `source/contrib/dblink/dblink.c:2552` — no
  max-conns, no LRU, no time-based eviction.
- [ISSUE-audit-gap: dblink_get_connections has no ACL gate (nit)] —
  `source/contrib/dblink/dblink.c:1279` — cross-SET ROLE leakage
  within shared backend session.
- [ISSUE-defense-in-depth: no size cap on remote PQgetvalue results
  before passing through local input fn (maybe)] —
  `source/contrib/dblink/dblink.c:1255` — malicious remote drives
  local OOM via large input-fn expansions.
- [ISSUE-correctness: applyRemoteGucs covers only DateStyle +
  IntervalStyle (maybe)] —
  `source/contrib/dblink/dblink.c:3148` — other I/O-affecting GUCs
  (extra_float_digits, bytea_output) silently mis-decode.
- [ISSUE-api-shape: 30s cancel deadline hardcoded in
  dblink_cancel_query (nit)] —
  `source/contrib/dblink/dblink.c:1351` — no GUC override.
- [ISSUE-error-handling: PQerrorMessage forwarded verbatim via
  errdetail_internal could leak environment hints (nit)] —
  `source/contrib/dblink/dblink.c:332` — libpq-enriched connstr
  details echo back.
- [ISSUE-concurrency: unnamed pconn->conn silently replaced when a
  second unnamed connect happens (nit)] —
  `source/contrib/dblink/dblink.c:357` — no warning emitted.
- [ISSUE-api-shape: connection-cache key is NAMEDATALEN-truncated
  identifier (nit)] —
  `source/contrib/dblink/dblink.c:2542` — two long names sharing
  prefix collide; NAME-vs-OID pattern.
- [ISSUE-audit-gap: superuser bypasses dblink_security_check
  entirely; no audit log of cross-cluster connect attempts
  (maybe)] — `source/contrib/dblink/dblink.c:2684` — combined with
  conninfo-trust gap, superuser→other-cluster pivot invisible.
- [ISSUE-correctness: dblink_open auto-BEGINs xact on
  PQTRANS_IDLE and resets openCursorCount=0 (nit)] —
  `source/contrib/dblink/dblink.c:459` — recovers from stale state
  but masks accounting bugs.
- [ISSUE-memory: storeInfo.tmpcontext deleted only on PG_TRY
  success path; PG_CATCH leaks until parent reset (nit)] —
  `source/contrib/dblink/dblink.c:1077` — `MemoryContextDelete`
  inside PG_TRY block, not PG_FINALLY.
