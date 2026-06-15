---
path: src/test/modules/oauth_validator/oauth_hook_client.c
anchor_sha: e18b0cb7344
loc: 381
depth: read
---

# src/test/modules/oauth_validator/oauth_hook_client.c

## Purpose

Standalone **libpq client** binary that drives the OAuth bearer-token
hook (`PQsetAuthDataHook` /
`PQAUTHDATA_OAUTH_BEARER_TOKEN[_V2]`). Built for the
`t/002_client.pl` TAP test; exercises the v1 vs v2 hook API, deliberate
misbehavior modes (`no-token`, `no-socket`, `fail-async`), the
asynchronous polling path, the `connect_timeout` hang-forever path, and
the v2 `error` reporting field. Unlike the other files in this
directory, this is a `postgres_fe.h` frontend program, not a backend
extension. `[verified-by-code]` `oauth_hook_client.c:4-6,17`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `main` | `:65` | CLI entry; parses flags, sets `PQsetAuthDataHook`, then `PQconnectdb` or async-polled `PQconnectStart`+loop |
| `handle_auth_data` (static) | `:201` | The `PQauthDataHook` callback; returns `1` (handled), `0` (default flow), or `-1` (fail) |
| `async_cb` (static) | `:303` | Async hook; either hangs on an unbound socket (`--hang-forever`) or returns the token synchronously |
| `misbehave_cb` (static) | `:345` | Implements the three misbehavior modes |

## Internal landmarks

- Flag set (`:53-62, 67-79`) — `--token`, `--error`, `--no-hook`,
  `--hang-forever`, `--misbehave={no-hook,fail-async,no-token,no-socket}`,
  `--stress-async`, `--expected-{scope,uri,issuer}`, `-v {1,2}` hook
  API selector.
- Hook handler (`:201`):
  - Returns `0` (skip) when `--no-hook` is set or `type` doesn't match
    the selected API version (`:209`).
  - V1 vs V2: V2 also exposes `req2->issuer` and `req2->error`.
  - `expected-*` flags validate that the server-side advertised values
    match; mismatch returns `-1` and prints to stderr.
  - `--error` sets `req2->error = errmsg` and returns `-1` — exercises
    the v2-only error-reporting path.
- `--stress-async` (`:160-176`) — busy-loops on `PQconnectPoll` without
  waiting on socket events; stresses code paths that rely on async work
  completing between polls `[from-comment]` `:162-167`.
- `--hang-forever` (`:305-338`) — creates an unbound `SOCK_DGRAM`
  socket, assigns it to `*altsock`, returns `PGRES_POLLING_READING`;
  libpq's wait will block forever on this socket, validating that
  `connect_timeout` cancels properly. On Windows uses
  `WSAStartup(MAKEWORD(2,2), ...)`.
- Misbehavior modes (`:347-380`):
  - `fail-async` returns `PGRES_POLLING_FAILED`.
  - `no-token` returns `PGRES_POLLING_OK` without setting `req->token`
    — exercises the libpq postcondition check `[from-comment]` `:368`.
  - `no-socket` returns `PGRES_POLLING_READING` without setting
    `*altsock` — exercises the matching socket postcondition `:373`.

## Invariants & gotchas

- FRONTEND program — links libpq, includes `postgres_fe.h`. Not a
  backend extension.
- `--error` and `--token` are mutually exclusive (`:283-287`); `--error`
  requires v2 (`:288-292`).
- Default hook API version is v2 (`hook_version =
  PQAUTHDATA_OAUTH_BEARER_TOKEN_V2`, `:62`).
- TEST DRIVER — the hang-forever socket is intentionally unreadable so
  libpq's poll loop blocks; this is the precise scenario `t/002_client.pl`
  needs to validate `connect_timeout` honoring.

## Cross-refs

- `source/src/interfaces/libpq/libpq-fe.h` — `PQauthDataHook`,
  `PGoauthBearerRequest`, `PGoauthBearerRequestV2`, `PQAUTHDATA_*` enum.
- `source/src/interfaces/libpq/fe-auth.c` — where the hook is invoked
  during SASL-OAUTHBEARER negotiation.
- `knowledge/files/src/test/modules/oauth_validator/validator.c.md` —
  server-side counterpart that produces the data this hook validates.
