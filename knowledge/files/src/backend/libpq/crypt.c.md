---
path: src/backend/libpq/crypt.c
anchor_sha: 4b0bf0788b0
loc: 403
depth: deep
---

# crypt.c

- **Source path:** `source/src/backend/libpq/crypt.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 403

## Purpose

Helpers for the **encrypted passwords stored in
`pg_authid.rolpassword`**: fetch (`get_role_password`), classify
(`get_password_type`), build (`encrypt_password`), verify
(`md5_crypt_verify`, `plain_crypt_verify`). Sits between the
auth-method dispatch in `auth.c` and the per-type primitives
(`pg_md5_encrypt` in `src/common/md5_common.c`,
`pg_be_scram_build_secret` / `scram_verify_plain_password` in
`auth-scram.c`). [from-comment, crypt.c:1-13]

This is also where MD5's deprecation warning is plumbed
(`md5_password_warnings` GUC, crypt.c:33) and where the password-
expiration warning threshold lives (`password_expiration_warning_threshold`,
crypt.c:30).

## Public API surface

- `char *get_role_password(const char *role, const char **logdetail)` —
  `crypt.c:43`. `SearchSysCache1(AUTHNAME, ...)` for the role, returns
  palloc'd `rolpassword` text or `NULL`. The error string in
  `*logdetail` distinguishes "role doesn't exist" vs "no password
  assigned" vs "password expired" — **but the caller must never
  forward that to the client**, only to the postmaster log.
  Side-effect: queues a `StoreConnectionWarning` if expiry is within
  `password_expiration_warning_threshold` seconds (default 604800 = 7
  days). [verified-by-code, crypt.c:42-147]
- `PasswordType get_password_type(const char *shadow_pass)` —
  `crypt.c:153`. Classifies into `PASSWORD_TYPE_MD5` (prefix `"md5"`
  + exact `MD5_PASSWD_LEN` + hex charset), `PASSWORD_TYPE_SCRAM_SHA_256`
  (parses via `parse_scram_secret`), or `PASSWORD_TYPE_PLAINTEXT` as
  fallback. Plaintext isn't ever stored — it means "unrecognized".
  [verified-by-code]
- `char *encrypt_password(PasswordType target_type, const char *role, const char *password)`
  — `crypt.c:180`. If the input is already an encrypted form, returns
  it as-is (passthrough). Otherwise, builds MD5 (`pg_md5_encrypt`)
  or SCRAM (`pg_be_scram_build_secret`). Enforces
  `MAX_ENCRYPTED_PASSWORD_LEN` (512 bytes) — comment crypt.c:219-225
  explains: TOAST de-toasting can't run during auth because no
  database has been selected. Emits the MD5 deprecation WARNING when
  storing an MD5 hash (crypt.c:242-248). [verified-by-code]
- `int md5_crypt_verify(const char *role, const char *shadow_pass, const char *client_pass, const uint8 *md5_salt, int md5_salt_len, const char **logdetail)`
  — `crypt.c:265`. Recomputes the MD5(MD5(password+role)+salt) and
  `timingsafe_bcmp`s it. Returns `STATUS_OK`/`STATUS_ERROR`.
  Side-effect: queues an "authenticated with MD5" deprecation
  warning. [verified-by-code, crypt.c:264-324]
- `int plain_crypt_verify(const char *role, const char *shadow_pass, const char *client_pass, const char **logdetail)`
  — `crypt.c:337`. Switches on stored type: SCRAM →
  `scram_verify_plain_password`; MD5 → recompute hash of cleartext +
  `timingsafe_bcmp`; plaintext branch is a never-reached safety net.
  [verified-by-code, crypt.c:336-403]

## Internal landmarks / globals

- `int password_expiration_warning_threshold` (crypt.c:30) — GUC, seconds.
- `bool md5_password_warnings` (crypt.c:33) — GUC, gates both
  "setting MD5" and "authenticated with MD5" client-bound warnings.
- All warning emission goes through `StoreConnectionWarning` (deferred
  until InitPostgres finishes); see crypt.c:113-142, 301-313, with
  `MemoryContextSwitchTo(TopMemoryContext)` so the message survives
  the auth-time per-query context.

## Invariants & gotchas

- **`*logdetail` is server-log only.** The header at crypt.c:36-41
  ("The error reason should *not* be sent to the client") is the
  primary mitigation against user-existence enumeration; SCRAM's
  doomed-mock pattern depends on auth.c continuing the handshake
  even after `get_role_password` returned NULL.
- **`MAX_ENCRYPTED_PASSWORD_LEN` (512 bytes)** is enforced on every
  write because TOASTed passwords can't be read during auth
  (`pg_class` isn't loaded yet). Defined in `auth.h`. Reducing it
  silently breaks new SCRAM secrets with huge iteration counts.
  [from-comment, crypt.c:219-225]
- **`timingsafe_bcmp` everywhere** for password / hash compares
  (crypt.c:297, 377). A patch swapping in `memcmp` is a security
  regression.
- **MD5 path checks the stored type first** (crypt.c:276-282): if
  the stored secret is SCRAM-shaped and the HBA selected `md5`,
  return `STATUS_ERROR` rather than attempting cross-format compare —
  this is the "can't do MD5 with a SCRAM password" failure mode.
- **Encrypted-passthrough** in `encrypt_password` (crypt.c:187-194)
  means `ALTER USER ... PASSWORD 'md5...'` with an MD5-looking string
  stores it verbatim regardless of `password_encryption`. This is
  intentional (it's how dumps round-trip) but means
  `password_encryption = scram-sha-256` doesn't actually upgrade
  existing MD5 users.
- **Expiry queues a connection warning, not a logged-out error** —
  past-`vuntil` users *are* rejected (crypt.c:91-96), but
  near-expiry just sets a warning that fires at the end of
  `InitPostgres`. A backend that crashes before then loses the
  warning silently.
- **The `PASSWORD_TYPE_PLAINTEXT` enum value** in `encrypt_password`
  (`crypt.c:211-213`) `elog(ERROR)`s — there is no way to store a
  plaintext password.

## Cross-refs

- Header: `knowledge/files/src/include/libpq/crypt.h.md` (planned).
- SCRAM builders: `auth-scram.c::pg_be_scram_build_secret`,
  `auth-scram.c::scram_verify_plain_password`,
  `auth-scram.c::parse_scram_secret`.
- MD5 primitive: `src/common/md5_common.c::pg_md5_encrypt`.
- Catalog: `pg_authid.rolpassword`, `pg_authid.rolvaliduntil`.
- Caller dispatchers in `auth.c`: `CheckPasswordAuth`,
  `CheckPWChallengeAuth`, `CheckMD5Auth`.

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-leak: shadow_pass not zeroed before pfree]** Returned by
  `get_role_password` and freed by callers (`auth.c:815`, `:871`)
  without `explicit_bzero`. SCRAM stored keys / MD5 hash → offline
  brute force. Severity: maybe.
- **[ISSUE-leak: crypt_pwd / crypt_client_pass stack buffers not
  scrubbed]** `crypt.c:271, 341` — local arrays hold MD5-hashed
  forms; on stack so they vanish on return, but a UB-leaning compiler
  could keep them across longjmp. Severity: nit.
- **[ISSUE-correctness: MD5_PASSWD_LEN compared with `strlen`
  inside `timingsafe_bcmp`]** `crypt.c:296-297, 376-377` — comparing
  `strlen(client_pass) == strlen(crypt_pwd)` first defeats some of
  the timing-safety, but since `crypt_pwd` is fixed-length (35 chars
  for "md5" + 32 hex) the length-comparison branch is
  attacker-known anyway. Severity: nit.
- **[ISSUE-question: MD5 deprecation warning depends on
  `md5_password_warnings = true` default]** `crypt.c:33` — silent
  upgrade path: if a site sets `md5_password_warnings = false` to
  quiet logs, they lose the breadcrumb that a deprecated path is in
  use. Severity: nit.
- **[ISSUE-doc-drift: `password_expiration_warning_threshold`
  default 604800 (7 days) is hardcoded]** `crypt.c:30` — comment
  says "Threshold for password expiration warnings" but doesn't
  document units or default. The GUC docs do. Severity: nit.

## Tally

`[verified-by-code]=14 [from-comment]=5 [inferred]=0`
