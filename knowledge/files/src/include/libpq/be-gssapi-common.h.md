# be-gssapi-common.h

- **Source path:** `source/src/include/libpq/be-gssapi-common.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definitions for GSSAPI authentication and encryption handling" — shared
helpers used by both `be-secure-gssapi.c` (transport) and `auth.c` (auth)
when `ENABLE_GSS` is defined [from-comment].

## Public API surface (only under `#ifdef ENABLE_GSS`)

- `void pg_GSS_error(const char *errmsg, OM_uint32 maj_stat, OM_uint32 min_stat)`
  — render a GSSAPI major/minor status pair into an `ereport`.
- `void pg_store_delegated_credential(gss_cred_id_t cred)` — stash a
  delegated credential the client forwarded.

## Internal landmarks

- Pulls in `libpq/pg-gssapi.h` for the platform-conditional `<gssapi.h>`
  include path (also has the wincrypt `X509_NAME` collision workaround).
- Entire header collapses to empty when GSS is not built in — callers
  must wrap use sites in `#ifdef ENABLE_GSS` themselves.

## Cross-refs

- Related backend: `src/backend/libpq/be-gssapi-common.c`,
  `src/backend/libpq/be-secure-gssapi.c`, `src/backend/libpq/auth.c` (GSS
  path).
- Related: `knowledge/files/src/include/libpq/pg-gssapi.h.md` (header
  include shim).

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-leak: GSS error text granularity]** `be-gssapi-common.h:21` —
  `pg_GSS_error` is the funnel for all GSS error formatting; this is the
  obvious site to audit for over-disclosing minor-status text in client-
  facing errors during pre-auth failures (info leak surface). The header
  itself only declares; review `be-gssapi-common.c` for the actual
  `ereport` level used. Severity: maybe; flagged as Phase D hardening
  candidate.

## Tally

`[verified-by-code]=2 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
