---
path: src/interfaces/libpq/fe-gssapi-common.h
anchor_sha: 4b0bf0788b0
loc: 28
depth: shallow
---

# fe-gssapi-common.h

- **Source path:** `source/src/interfaces/libpq/fe-gssapi-common.h`
- **Lines:** 28
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-gssapi-common.c`, `fe-auth.c` (GSS auth path), `fe-secure-gssapi.c` (GSS encryption transport), `libpq-int.h` (defines `PGconn.gtarg_nam`, `gcred`, `gctx`, `krbsrvname`).

## Purpose

Tiny private header gating GSSAPI helpers behind `#ifdef ENABLE_GSS`. Declares three helpers used by both the auth path (`fe-auth.c`) and the encryption transport (`fe-secure-gssapi.c`). [verified-by-code, fe-gssapi-common.h:1-28]

## API surface

- `pg_GSS_error(mprefix, conn, maj_stat, min_stat)` (21) — formats GSS major/minor errors into `conn->errorMessage`. Both major and minor status codes are walked via `gss_display_status`. [verified-by-code, fe-gssapi-common.h:21-22]
- `pg_GSS_have_cred_cache(gss_cred_id_t *cred_out)` (23) — probe via `gss_acquire_cred(GSS_C_INITIATE)`; returns true and yields credential on success. [verified-by-code, fe-gssapi-common.h:23]
- `pg_GSS_load_servicename(PGconn *conn)` (24) — builds `"<krbsrvname>@<host>"` and imports it as `GSS_C_NT_HOSTBASED_SERVICE` into `conn->gtarg_nam`. Idempotent (returns OK if already set). [verified-by-code, fe-gssapi-common.h:24; fe-gssapi-common.c:81-128]

## Invariants & gotchas

- The whole file is only visible under `#ifdef ENABLE_GSS`. Callers (`fe-auth.c`, `fe-secure-gssapi.c`) only include it inside their own ENABLE_GSS guards. [verified-by-code, fe-gssapi-common.h:19-26]
- These functions all mutate `conn->errorMessage` or `conn->gtarg_nam`/`conn->gcred` — they are not thread-safe with respect to that connection without external locking (which `pg_fe_sendauth` does via `pglock_thread()`, fe-auth.c:1097). [verified-by-code, fe-auth.c:1097-1123]

## Cross-refs

- Implementation: `fe-gssapi-common.c` (128 LOC).
- Consumers: `fe-auth.c` (`pg_GSS_startup`, `pg_GSS_continue`), `fe-secure-gssapi.c` (`pqsecure_open_gss`).

## Tally
`[verified-by-code]=5 [from-comment]=0 [from-readme]=0 [inferred]=0 [unverified]=0`
