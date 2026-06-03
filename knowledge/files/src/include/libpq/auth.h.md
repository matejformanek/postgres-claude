# auth.h

- **Source path:** `source/src/include/libpq/auth.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definitions for network authentication routines" — entry point declarations
for `ClientAuthentication()` and friends, plus the canonical max-token size
used across the auth code [from-comment].

## Public API surface

- `void ClientAuthentication(Port *port)` — top-level auth dispatcher called
  from `BackendInitialize()`.
- `void sendAuthRequest(Port *port, AuthRequest areq, const void *extradata, int extralen)`
  — emit an `AuthenticationRequest` ('R') message.
- `void set_authn_id(Port *port, const char *id)` — record the
  authenticated identity into `MyClientConnectionInfo` and log it.
- Hooks:
  - `ClientAuthentication_hook_type` — `void (*)(Port *, int)`. Called from
    `ClientAuthentication()` so extensions can audit auth decisions.
  - `auth_password_hook_typ` / `ldap_password_hook` — password mutator (LDAP).
- GUC-backed externs: `pg_krb_server_keyfile`, `pg_krb_caseins_users`,
  `pg_gss_accept_delegation` [verified-by-code].

## Key constants

- `PG_MAX_AUTH_TOKEN_LENGTH 65535` — comment justifies the value via
  Microsoft's MaxAuthToken recommendation; also used as the cap on ordinary
  password packet lengths [from-comment]. **Not a wire-protocol constant**:
  this is a server-side input-size limit, not on-wire format.

## Cross-refs

- Related backend: `src/backend/libpq/auth.c` (definitions).
- Related: `knowledge/files/src/include/libpq/hba.h.md` (HBA decisions feed
  into `ClientAuthentication`).
- Related subsystem: `knowledge/subsystems/libpq-backend.md` (if/when
  written).

## Potential issues

- **[ISSUE-undocumented-invariant: hook signature integer is unnamed]** `auth.h:45` —
  `ClientAuthentication_hook_type` is `void (*)(Port *, int)` where the `int`
  is the auth-status code. The header gives no name or comment for the
  second parameter; auditing extensions must read `auth.c` to learn it is
  the post-auth status. Severity: maybe.

## Tally

`[verified-by-code]=2 [from-comment]=2`
