# crypt.h

- **Source path:** `source/src/include/libpq/crypt.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Interface to libpq/crypt.c" — password hashing, storage-format detection,
and verification helpers used by the auth methods (password, md5, scram).

## Public API surface

- `PasswordType` enum: `PASSWORD_TYPE_PLAINTEXT` (only allowed inbound, from
  user CREATE/ALTER USER), `PASSWORD_TYPE_MD5`, `PASSWORD_TYPE_SCRAM_SHA_256`
  — the latter two are the only valid `pg_authid.rolpassword` storage formats
  [from-comment].
- `PasswordType get_password_type(const char *shadow_pass)` — sniff the
  format of an on-disk hash.
- `char *encrypt_password(PasswordType target_type, const char *role, const char *password)`
  — convert plaintext to the target storage format.
- `char *get_role_password(const char *role, const char **logdetail)` —
  fetch a role's `rolpassword` for use during auth.
- `int md5_crypt_verify(...)` and `int plain_crypt_verify(...)` — actually
  check a client-supplied password against the stored shadow. Both take
  `logdetail` out-param so the server can log a specific reason while
  returning a generic failure to the client.
- GUCs: `password_expiration_warning_threshold`, `md5_password_warnings`.

## Key constants

- `MAX_ENCRYPTED_PASSWORD_LEN 512` — bounded so the value never gets
  TOAST-ed (auth runs before a database is selected, so de-TOAST would
  fail) [from-comment]. Not a wire-protocol constant.

## Cross-refs

- Related backend: `src/backend/libpq/crypt.c`.
- Related: `knowledge/files/src/include/libpq/scram.h.md`,
  `knowledge/files/src/include/libpq/sasl.h.md`.

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-leak: logdetail is the side-channel ledger]** `crypt.h:54,56-61` —
  `get_role_password` and the `*_crypt_verify` family use the `**logdetail`
  pattern to keep the server log informative while the client only sees a
  generic auth failure. The split is correct by design, but the contract is
  not enforced in the type system: a caller that forwards `*logdetail` into
  the client-visible `ereport` would leak "role does not exist" vs "password
  mismatch" distinctions. Worth a Phase D audit of all call sites. Severity:
  maybe.
- **[ISSUE-undocumented-invariant: MD5 verify is constant-time?]**
  `crypt.h:56-58` — the header gives no constant-time-comparison guarantee
  for `md5_crypt_verify`; whether the impl uses a timing-safe memcmp is
  not stated. Worth verifying in `crypt.c`. Severity: maybe.

## Tally

`[verified-by-code]=3 [from-comment]=2 [inferred]=1`
