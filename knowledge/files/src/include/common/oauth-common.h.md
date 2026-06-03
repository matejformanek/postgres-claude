---
path: src/include/common/oauth-common.h
anchor_sha: 4b0bf0788b0
loc: 19
---

# oauth-common.h

- **Source path:** `source/src/include/common/oauth-common.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 19

## Purpose

Single shared constant for the OAUTHBEARER SASL mechanism (RFC 7628):
`OAUTHBEARER_NAME "OAUTHBEARER"` — the IANA-registered name used in
both `src/backend/libpq/auth-sasl.c` advertising and the libpq
`fe-auth-oauth*.c` client path. [verified-by-code, oauth-common.h:17]

## Phase D notes

- **Trust-boundary marker only — no token handling here.** The bearer
  token itself lives in libpq's `PGoauthBearerRequest` (frontend) and
  the backend's `ValidatorModuleResult` once validated by the
  external `oauth_validator_libraries` module. This header is just
  the wire string.
- Renaming `OAUTHBEARER` would break every SASL handshake; it's an
  on-wire string (matching IANA registry).
- The frontend OAuth dance lives in `src/interfaces/libpq/fe-auth-oauth*`
  files and uses iddawc + a temp file under `~/.cache/...` (per A2
  notes); the secret lifetime gap is *there*, not here.

## Cross-refs

- Backend OAuth dispatch: `src/backend/libpq/auth-oauth.c`.
- Frontend impl: `src/interfaces/libpq/fe-auth-oauth.c` +
  `fe-auth-oauth-curl.c`.
- The validator-module API: `src/include/libpq/oauth.h`.

## Tally

`[verified-by-code]=1 [inferred]=1`
