---
path: src/interfaces/libpq/fe-auth.h
anchor_sha: 4b0bf0788b0
loc: 36
depth: shallow
---

# fe-auth.h

- **Source path:** `source/src/interfaces/libpq/fe-auth.h`
- **Lines:** 36
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-auth.c` (implements every prototype), `fe-auth-sasl.h` (mechanism table type), `fe-auth-scram.c` (defines `pg_scram_mech` referenced here), `libpq-int.h` (defines `PGconn`, `AuthRequest`, `PQauthDataHook_type`).

## Purpose

Private header shared between `fe-auth.c`, `fe-auth-scram.c`, and `fe-auth-oauth.c`. Declares the public-into-libpq auth dispatcher (`pg_fe_sendauth`), the user-name helpers, and exports the global `PQauthDataHook` plus the SCRAM mechanism table. Not part of the libpq public ABI — applications must not include it. [verified-by-code, fe-auth.h:1-36]

## API surface

- `PQauthDataHook` (line 21) — the externally-mutable user hook for auth-data callbacks. Settable via `PQsetAuthDataHook`. Default is `PQdefaultAuthDataHook` (set in `fe-auth.c`). [verified-by-code, fe-auth.h:21; fe-auth.c:1586]
- `pg_fe_sendauth(AuthRequest areq, int payloadlen, PGconn *conn, bool *async)` (25) — the client-side dispatcher for an incoming `Authentication*` message. `*async` is set to true if the auth flow needs to suspend (OAuth token retrieval). [verified-by-code, fe-auth.h:25-26]
- `pg_fe_getusername(uid_t, PQExpBuffer)` (27) — POSIX `getpwuid_r` (or `GetUserName` on Windows) wrapper, returns malloc'd string. [verified-by-code, fe-auth.h:27]
- `pg_fe_getauthname(PQExpBuffer)` (28) — convenience wrapper for the calling euid. [verified-by-code, fe-auth.h:28]
- `pg_scram_mech` (31) — exported SCRAM mechanism table consumed by `pg_SASL_init`. [verified-by-code, fe-auth.h:31]
- `pg_fe_scram_build_secret(password, iterations, errstr)` (32) — produces the `SCRAM-SHA-256$...` verifier string for client-side `ALTER USER ... PASSWORD` flows. [verified-by-code, fe-auth.h:32-34]

## Invariants & gotchas

- Including this header pulls in `libpq-int.h`, which exposes the entire `PGconn` struct — so any client of fe-auth.h sees libpq internals. Not safe to expose from a public header. [verified-by-code, fe-auth.h:17-18]
- The `PQauthDataHook_type` typedef itself lives in the public `libpq-fe.h`; this header only declares the *variable*. The default must always be non-NULL (set via `PQsetAuthDataHook(NULL)` which collapses to the default — see `fe-auth.c:1594-1598`). [verified-by-code, fe-auth.h:21; fe-auth.c:1594-1598]

## Cross-refs

- All call sites are in `fe-auth.c`, `fe-auth-scram.c`, `fe-auth-oauth.c`, and the connection-state machine in `fe-connect.c` (which calls `pg_fe_sendauth` from `PQconnectPoll`).
- See also `knowledge/files/src/interfaces/libpq/fe-auth.c.md` for the dispatcher itself.

## Tally
`[verified-by-code]=8 [from-comment]=0 [from-readme]=0 [inferred]=0 [unverified]=0`
