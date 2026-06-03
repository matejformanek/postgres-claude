# sasl.h

- **Source path:** `source/src/include/libpq/sasl.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Defines the SASL mechanism interface for the backend." Mechanism authors
(SCRAM, OAUTHBEARER, ...) implement a `pg_be_sasl_mech` callback table;
`auth.c`'s `CheckSASLAuth` drives the exchange via the registered
callbacks [from-comment].

## Public API surface

- Exchange status codes (returned by the mechanism's `exchange` callback):
  `PG_SASL_EXCHANGE_CONTINUE 0`, `_SUCCESS 1`, `_FAILURE 2`, `_ABANDONED 3`.
- `PG_MAX_SASL_MESSAGE_LENGTH 1024` — global cap on a SASL response
  message size from the client [from-comment]. Mechanisms can override
  via `pg_be_sasl_mech.max_message_length`. Not a wire-protocol constant
  but an input-size limit.
- `pg_be_sasl_mech` struct callbacks:
  - `get_mechanisms(Port *, StringInfo)` — advertise mechanism names
    (null-terminated, appended).
  - `init(Port *, mech, shadow_pass) → void *state` — `shadow_pass` may be
    NULL when the role does not exist; **the contract requires continuing
    the exchange as-if to avoid disclosing valid usernames** [from-comment].
  - `exchange(state, input, inputlen, **output, *outputlen, **logdetail)
    → int` — produce server challenges. `input` is null-terminated for
    safety but mechanisms must use `inputlen` because SASL allows embedded
    NULs [from-comment]. `logdetail` is server-log only.
  - `max_message_length` — per-mech override of the 1024-byte default.
- `int CheckSASLAuth(const pg_be_sasl_mech *mech, Port *port, char *shadow_pass,
  const char **logdetail, bool *abandoned)` — common driver in `auth.c`.

## Cross-refs

- Related backend: `src/backend/libpq/auth-sasl.c` (`CheckSASLAuth`).
- Related: `knowledge/files/src/include/libpq/scram.h.md` (mech instance),
  `knowledge/files/src/include/libpq/oauth.h.md` (mech instance),
  `knowledge/files/src/include/libpq/protocol.h.md` (wire-side
  `AUTH_REQ_SASL*` and `'p'` response byte).
- Frontend counterpart: `src/interfaces/libpq/fe-auth-sasl.h`
  [from-comment].

## Potential issues

- **[ISSUE-undocumented-invariant: NULL shadow_pass contract is mechanism-level only]**
  `sasl.h:80-87` — the requirement that mechanisms continue the mock
  exchange when `shadow_pass` is NULL is documented per-callback but not
  asserted by the framework. A new mechanism that early-returns
  `PG_SASL_EXCHANGE_FAILURE` on missing shadow_pass would create a
  user-enumeration oracle via timing/length. Phase D candidate.
  Severity: likely.
- **[ISSUE-leak: input is guaranteed null-terminated only "for safety"]**
  `sasl.h:106-109` — comment says the input is guaranteed null-terminated
  but "SASL allows embedded nulls in responses, so mechanisms must be
  careful to check inputlen." Any mechanism that does `strlen(input)` to
  bound a memcmp creates a truncation-style bypass. Severity: maybe.
- **[ISSUE-undocumented-invariant: logdetail vs client-visible error]**
  `sasl.h:129-133` — `logdetail` is server-side only; "The client will
  only ever see the same generic authentication failure message." But
  enforcement depends on `auth.c` keeping the two strings separate. A
  future refactor that piped `logdetail` into the client's
  `ErrorResponse` would silently regress. Severity: maybe.
- **[ISSUE-undocumented-invariant: max_message_length default for new mechs]**
  `sasl.h:141-142` — if a mechanism implementer forgets to set
  `max_message_length`, the field defaults to 0 (zero-initialized struct),
  which would refuse all client messages. Should at minimum document
  "must be non-zero" or default to `PG_MAX_SASL_MESSAGE_LENGTH`.
  Severity: maybe.

## Tally

`[verified-by-code]=4 [from-comment]=4 [inferred]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
