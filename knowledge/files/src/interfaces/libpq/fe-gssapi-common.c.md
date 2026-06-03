---
path: src/interfaces/libpq/fe-gssapi-common.c
anchor_sha: 4b0bf0788b0
loc: 128
depth: shallow
---

# fe-gssapi-common.c

- **Source path:** `source/src/interfaces/libpq/fe-gssapi-common.c`
- **Lines:** 128
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-gssapi-common.h`, `fe-auth.c` (`pg_GSS_continue`, `pg_GSS_startup`), `fe-secure-gssapi.c` (`pqsecure_open_gss`), `libpq-int.h` (conn fields).

## Purpose

GSSAPI helper functions shared by the GSS authentication path and the GSS encryption transport. Three small routines: error formatting, credential probing, and service-principal-name import. [verified-by-code, fe-gssapi-common.c:1-12]

## Public surface

- `pg_GSS_error(mprefix, conn, maj_stat, min_stat)` (46-55) — appends `mprefix: <major-status-msgs>:<minor-status-msgs>\n` to `conn->errorMessage`. Iterates `gss_display_status` for both `GSS_C_GSS_CODE` (major) and `GSS_C_MECH_CODE` (minor) via the internal `pg_GSS_error_int` helper. [verified-by-code, fe-gssapi-common.c:46-55]
- `pg_GSS_have_cred_cache(gss_cred_id_t *cred_out)` (60-76) — `gss_acquire_cred(GSS_C_NO_NAME, GSS_C_INITIATE)`. Returns true and yields the cred on success; sets `*cred_out = NULL` and returns false otherwise. [verified-by-code, fe-gssapi-common.c:60-76]
- `pg_GSS_load_servicename(PGconn *conn)` (81-128) — short-circuits if `conn->gtarg_nam` already set. Otherwise builds `"<krbsrvname>@<host>"` (length-bound to `strlen(krbsrvname)+strlen(host)+2`) and imports it via `gss_import_name(GSS_C_NT_HOSTBASED_SERVICE)`. The imported name lands in `conn->gtarg_nam`. [verified-by-code, fe-gssapi-common.c:81-128]

## Internal

- `pg_GSS_error_int(str, stat, type)` (25-41) — walks the multi-part GSS status via the `msg_ctx` token, releasing each `gss_buffer_desc` after appending. [verified-by-code, fe-gssapi-common.c:25-41]

## Invariants & gotchas

- The temp buffer used in `pg_GSS_load_servicename` is `malloc`'d (line 106) and freed unconditionally after `gss_import_name` (line 118), so a name-import failure does not leak the principal string — only the imported `gss_name_t` on success. [verified-by-code, fe-gssapi-common.c:106-118]
- `pg_GSS_error_int` walks the GSS status by chaining `msg_ctx`, but each iteration's failure of `gss_display_status` silently `break`s without any error to the user. A buggy GSS library returning a non-COMPLETE status mid-loop produces a truncated message. [verified-by-code, fe-gssapi-common.c:32-36]
- `pg_GSS_have_cred_cache` returns the credential under success but the caller (fe-auth.c:106, fe-secure-gssapi.c:638) is responsible for releasing it via `gss_release_cred`. There is no central tracking — leak-prone if the auth path is aborted between acquire and release. [verified-by-code, fe-gssapi-common.c:67-75; fe-auth.c:104-106]

## Potential issues

- ISSUE-libpq-gss-001 (severity: maybe) — `pg_GSS_load_servicename` allows `host` to be any user-supplied string. If a hostalias maps to a host containing `@`, the resulting principal becomes ambiguous to GSS (e.g. `postgres@evil.example@good.example`). No validation. The `gss_import_name` may or may not catch this depending on the GSS implementation. [inferred, fe-gssapi-common.c:112-117]

## Cross-refs

- Header: `fe-gssapi-common.h` (28 LOC).
- Callers: `fe-auth.c:106` (`pg_GSS_have_cred_cache`); `fe-auth.c:186` (`pg_GSS_load_servicename`); `fe-secure-gssapi.c:630, 638`.

## Tally
`[verified-by-code]=8 [from-comment]=0 [from-readme]=0 [inferred]=1 [unverified]=0`
