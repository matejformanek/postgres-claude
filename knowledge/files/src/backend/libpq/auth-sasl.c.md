---
path: src/backend/libpq/auth-sasl.c
anchor_sha: 4b0bf0788b0
loc: 214
depth: deep
---

# auth-sasl.c

- **Source path:** `source/src/backend/libpq/auth-sasl.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 214

## Purpose

The mechanism-agnostic SASL outer loop. Owns the wire protocol — the
`AuthenticationSASL` / `AuthenticationSASLContinue` /
`AuthenticationSASLFinal` 'R'-message dance and the client-side `'p'`
(SASLResponse / SASLInitialResponse) messages — and delegates the
actual cryptographic state machine to a `pg_be_sasl_mech` plug
implementation (SCRAM in `auth-scram.c`, OAUTHBEARER in
`auth-oauth.c`). [from-comment, auth-sasl.c:1-13; verified-by-code,
auth-sasl.c:50-213]

This file is tiny (one function plus headers) but its callers carry
the full security weight: any mechanism that goes through
`CheckSASLAuth` automatically inherits the "doomed authentication"
discipline (run the full exchange even when the user is unknown so
that timing and error shape don't reveal user existence).

## Public API surface

- `CheckSASLAuth(const pg_be_sasl_mech *mech, Port *port, char *shadow_pass, const char **logdetail, bool *abandoned) -> int`
  — `auth-sasl.c:50`. Drives one SASL exchange to completion. Returns
  `STATUS_OK` / `STATUS_ERROR` / `STATUS_EOF`. The `abandoned`
  out-parameter (only used by OAUTHBEARER discovery) signals "the
  client requested information that we had to refuse, but this isn't
  a credential-failure event — don't write a security log entry."
  Callers that don't track it must pass `NULL` and the function
  `elog(ERROR)`s if the mechanism returns `PG_SASL_EXCHANGE_ABANDONED`
  unexpectedly. [verified-by-code, auth-sasl.c:50, 193-205]

## Internal landmarks

- **The exchange loop** (auth-sasl.c:84-191).
  1. Sends `AUTH_REQ_SASL` with the `\0`-separated mechanism list
     produced by `mech->get_mechanisms()` (auth-sasl.c:68-75).
  2. Reads one `'p'` (PqMsg_SASLResponse) — first one is
     `SASLInitialResponse` (mechanism name + ICR length + ICR), every
     subsequent one is bare SASL payload (auth-sasl.c:119-152).
  3. Calls `mech->init(port, selected_mech, shadow_pass)` exactly once
     to build the per-exchange opaque state (auth-sasl.c:137).
  4. Calls `mech->exchange(opaq, input, inputlen, &output, &outputlen,
     logdetail)` per iteration (auth-sasl.c:163-165).
  5. Sends `AUTH_REQ_SASL_CONT` for in-progress turns and
     `AUTH_REQ_SASL_FIN` on success (auth-sasl.c:184-187).
  6. Loops while result is `PG_SASL_EXCHANGE_CONTINUE`
     (auth-sasl.c:191).
- **Max message length** — `mech->max_message_length` is passed to
  `pq_getmessage` (auth-sasl.c:104). SCRAM uses
  `PG_MAX_SASL_MESSAGE_LENGTH`; OAUTHBEARER uses the much larger
  `PG_MAX_AUTH_TOKEN_LENGTH` (bearer tokens can be kilobytes).
  [verified-by-code, auth-scram.c:114-120, auth-oauth.c:54-60]
- **Output-after-failure invariant** — if the mechanism returns
  `PG_SASL_EXCHANGE_FAILURE` or `_ABANDONED` *with* an `output`
  buffer, we `elog(ERROR)` because SASL forbids that ("output message
  found after SASL exchange failure", auth-sasl.c:176-177).
  [verified-by-code]

## Invariants & gotchas

- The `shadow_pass` may be `NULL` — that's how `CheckPWChallengeAuth`
  signals "user doesn't exist / has no password / expired" without
  short-circuiting. Mechanisms must complete the protocol anyway and
  fail at the end. The doctrine is spelled out in the header comment
  (auth-sasl.c:26-43): "Mechanisms must take care not to reveal to the
  client that a user entry does not exist; ideally, the external
  failure mode is identical to that of an incorrect password."
  [from-comment]
- The `init` callback runs *after* the first client message arrives —
  so it knows the `selected_mech` (auth-sasl.c:137). This matters for
  OAUTHBEARER's discovery exchange (it conditionally returns a
  `OAUTH_STATE_ERROR_DISCOVERY` if the client offered an empty token).
- The function `pq_startmsgread` + `pq_getbyte` + `pq_getmessage` /
  `pq_endmessage` dance is repeated in every libpq-receiving function
  in the backend; the `assert input == NULL || input[inputlen] ==
  '\0'` (auth-sasl.c:158) relies on `StringInfo` always appending a
  trailing `\0` for safety on string ops. [verified-by-code]
- Only message type `PqMsg_SASLResponse` ('p') is accepted; any other
  type during the exchange is an `ERRCODE_PROTOCOL_VIOLATION`
  (auth-sasl.c:93-97). EOF returns `STATUS_EOF` rather than erroring
  so `auth_failed` can `proc_exit(0)` quietly.

## Cross-refs

- Header / vtable: `knowledge/files/src/include/libpq/sasl.h.md`
  (defines `pg_be_sasl_mech`).
- SCRAM mech: `knowledge/files/src/backend/libpq/auth-scram.c.md`.
- OAUTHBEARER mech: `knowledge/files/src/backend/libpq/auth-oauth.c.md`.
- Drives the AUTH_REQ_SASL* wire messages defined in
  `src/include/libpq/protocol.h`.

## Potential issues

- **[ISSUE-undocumented-invariant: shadow_pass lifetime / scrub]**
  `auth-sasl.c:50` — the signature passes `char *shadow_pass` by
  value; `auth.c:805-815` is the only path that produces a non-NULL
  value, and *it* pfrees the shadow after `CheckSASLAuth` returns,
  but does not `explicit_bzero`. The mechanism may also stash copies
  (SCRAM's `parse_scram_secret` does, via `pstrdup`). Document the
  expected ownership / scrub contract somewhere. Severity: maybe.
- **[ISSUE-question: max_message_length not validated against the
  protocol's hard limit]** `auth-sasl.c:104` — a mechanism could
  legally set `max_message_length = INT_MAX`; `pq_getmessage` already
  caps at `PQ_LARGE_MESSAGE_LIMIT`, but the auth-pre-startup path
  could conceivably allocate large memory before that fires. Verify
  upper bound. Severity: nit.

## Tally

`[verified-by-code]=10 [from-comment]=3 [inferred]=0`
