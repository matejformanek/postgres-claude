# hba.h

- **Source path:** `source/src/include/libpq/hba.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Interface to hba.c" — types and entry points for parsing and matching
`pg_hba.conf` and `pg_ident.conf`. Defines the `UserAuth` enum that drives
`ClientAuthentication()`.

## Public API surface

- Enums:
  - `UserAuth` — the set of auth methods (`uaReject`, `uaImplicitReject`,
    `uaTrust`, `uaIdent`, `uaPassword`, `uaMD5`, `uaSCRAM`, `uaGSS`,
    `uaSSPI`, `uaPAM`, `uaBSD`, `uaLDAP`, `uaCert`, `uaPeer`, `uaOAuth`).
    Comment requires keeping it in sync with the `UserAuthName` array in
    `hba.c` [from-comment].
  - `USER_AUTH_LAST` — sentinel macro pinned to the last value.
  - `IPCompareMethod`, `ConnType` (`ctLocal`/`ctHost`/`ctHostSSL`/etc.),
    `ClientCertMode`, `ClientCertName`.
- Structs:
  - `AuthToken { string, quoted, regex }` — one lexed token; leading-slash
    strings may carry a compiled `regex_t *` [from-comment].
  - `HbaLine` — fully parsed `pg_hba.conf` row. Carries auth method, LDAP
    bind credentials (`ldapbindpasswd`), cert mode, krb realm, OAuth
    issuer/scope/validator, etc.
  - `IdentLine`, `HostsLine`, `TokenizedAuthLine` — supporting types.
- Functions: `load_hba`, `load_ident`, `hba_authname`, `hba_getauthmethod`,
  `check_usermap`, `parse_hba_line`, `parse_ident_line`, `open_auth_file`,
  `free_auth_file`, `tokenize_auth_file`.
- Forward-declares `Port` to avoid including `libpq-be.h` [from-comment].

## Cross-refs

- Related backend: `src/backend/libpq/hba.c`.
- Related: `knowledge/files/src/include/libpq/auth.h.md`,
  `knowledge/files/src/include/libpq/oauth.h.md`,
  `knowledge/files/src/include/libpq/libpq.h.md` (HostsFileLoadResult and
  `load_hosts` live in libpq.h despite the file naming similarity).

## Potential issues

- **[ISSUE-leak: ldapbindpasswd lives in plaintext on HbaLine]** `hba.h:117` —
  the bind password is held as a plain `char *` for the life of the
  loaded HBA configuration; nothing in the header asks the parser to scrub
  it or hint that it must not be logged. Audit `hba.c` for any errcontext
  / debug dump that might include the whole `HbaLine`. Severity: maybe.
- **[ISSUE-undocumented-invariant: USER_AUTH_LAST must equal final enum value]**
  `hba.h:42` — `#define USER_AUTH_LAST uaOAuth` lives inside the enum
  definition. If a future patch adds `uaFoo` after `uaOAuth` and forgets to
  update the macro, callers using `USER_AUTH_LAST` for array sizing will
  silently undercount. The "Must be last value of this enum" comment is the
  only guard. Severity: maybe.

## Tally

`[verified-by-code]=4 [from-comment]=4`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
