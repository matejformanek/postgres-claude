---
path: src/backend/libpq/be-gssapi-common.c
anchor_sha: 4b0bf0788b0
loc: 147
depth: shallow
---

# be-gssapi-common.c

- **Source path:** `source/src/backend/libpq/be-gssapi-common.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 147

## Purpose

Shared GSSAPI helpers used by both `be-secure-gssapi.c` (encryption) and
`auth.c` (authentication). Two responsibilities: convert GSSAPI status codes
into human-readable `ereport(COMMERROR, …)` output, and stash a delegated
credential into a process-local MEMORY: ccache so later libpq calls
(postgres_fdw, dblink) can re-use it. [from-comment, be-gssapi-common.c:1-12,96-101]

## Public API surface

| Line | Symbol | Semantics |
|---|---|---|
| 75 | `pg_GSS_error(errmsg, maj_stat, min_stat)` | Format major+minor GSS status into one `COMMERROR`. Always logged, never sent to client (recursion risk). |
| 104 | `pg_store_delegated_credential(cred)` | Save a delegated client credential into a per-process MEMORY ccache and `setenv("KRB5CCNAME", ...)` so subsequent libpq connections inherit it. |

## Internal landmarks

- `pg_GSS_error_int` (24) — fixed-size 128-byte buffer per status string;
  loops over `gss_display_status` with `msg_ctx` until the mechanism stops
  appending; truncates and logs `incomplete GSS error report` if the buffer
  fills. [verified-by-code, be-gssapi-common.c:24-58]
- `GSS_MEMORY_CACHE` macro = `"MEMORY:"` — chosen so the cred lives only
  inside this backend's address space, not on disk. [verified-by-code, be-gssapi-common.c:102]

## Invariants & gotchas

- **Always `COMMERROR`, never `ERROR`/`FATAL` to the client.** The comment
  is explicit: sending GSS errors to the client risks infinite recursion
  inside elog.c when the connection itself is broken. [from-comment, be-gssapi-common.c:66-71]
- The 128-byte cap on each of `msg_major` / `msg_minor` is documented as
  "No known mechanisms will produce error messages beyond this cap." If a
  novel KRB5 mechanism ever does, the output is silently truncated (with
  the `incomplete GSS error report` log line). [from-comment, be-gssapi-common.c:70-72]
- `pg_store_delegated_credential` uses `GSS_C_INITIATE` so the credential
  is only usable for *outbound* libpq connections (postgres_fdw / dblink),
  not for re-authenticating inbound. [verified-by-code, be-gssapi-common.c:121]
- `setenv("KRB5CCNAME", GSS_MEMORY_CACHE, 1)` mutates the backend's
  environment with overwrite=1; any later `gss_acquire_cred` call will use
  the delegated cred. This is process-wide — extensions calling KRB5 in
  the same backend will inherit it. [verified-by-code, be-gssapi-common.c:146]

## Cross-refs

- Header: `source/src/include/libpq/be-gssapi-common.h`
- Callers: `source/src/backend/libpq/auth.c` (`pg_GSS_recvauth`),
  `source/src/backend/libpq/be-secure-gssapi.c`
- Frontend counterpart: `source/src/interfaces/libpq/fe-gssapi-common.c`

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-leak: principal-name truncation logged but no enforcement]**
  `be-gssapi-common.c:53-57` — if a GSS mechanism produces a status string
  longer than 127 bytes, the buffer is truncated AND a `COMMERROR` is
  emitted, but the resulting `errdetail` is the truncated string. Probably
  benign (admin still sees the truncation log) but mildly information-lossy
  for diagnosis. severity: nit
- **[ISSUE-question: delegation default-on or default-off?]** This file
  unconditionally stores the delegated credential when called; the
  caller-side decision (whether to accept delegation at all) lives in
  `auth.c` / `be-secure-gssapi.c`. Worth tracing from a security-review
  angle that "no delegation unless explicitly opted in." severity: maybe

## Tally

`[verified-by-code]=5 [from-comment]=4 [inferred]=0`
