---
path: src/interfaces/libpq-oauth/oauth-curl.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 24
depth: read
---

# `oauth-curl.h` — public surface of the OAuth device-flow module

## Purpose

A one-prototype header: it declares the single exported entry point of
the `libpq-oauth` dynamic library, `pg_start_oauthbearer()`. Everything
else in [[oauth-curl.c]] is `static`; this header is what the libpq SASL
layer ([[fe-auth-oauth.c]]) links against to kick off a device flow.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pg_start_oauthbearer(PGconn *conn, PGoauthBearerRequestV2 *request)` | oauth-curl.h:21 | Marked `PGDLLEXPORT`. Implemented at oauth-curl.c:3062. Returns 0 on success, -1 on failure (with `request->error` set). |

## Invariants & gotchas

- Includes only `libpq-fe.h` — deliberately *not* `libpq-int.h`, so the
  module's ABI stays decoupled from libpq internals across minor-version
  bumps (the rationale spelled out in [[oauth-curl.c]] at lines 35-50 and
  in [[oauth-utils.c]]).
- `PGoauthBearerRequestV2` is the versioned request struct; the `.v1`
  prefix in the .c file (e.g. `request->v1.async`) is how the V2 layout
  embeds the original V1 fields.

## Cross-refs

- [[oauth-curl.c]] — the implementation.
- [[oauth-utils.h]] — the companion "missing libpq internals" header.
