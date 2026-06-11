# `contrib/passwordcheck/passwordcheck.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~167
- **Source:** `source/contrib/passwordcheck/passwordcheck.c`

Single-file backend extension that installs `check_password_hook` to
enforce password-quality policy on `CREATE ROLE … PASSWORD '…'` and
`ALTER ROLE … PASSWORD '…'`. Demonstrates the hook API; the
implementation is **deliberately weak** and the upstream docs (and
this comment block) warn users to harden it before any real
production use. Optionally links cracklib for dictionary checks via
`USE_CRACKLIB`. [verified-by-code] [from-comment]

## API / entry points

- `_PG_init` (passwordcheck.c:148-167) — defines one PGC_SUSET GUC
  `passwordcheck.min_password_length` (default 8), marks the GUC
  prefix reserved, and chains `check_password_hook`. [verified-by-code]
- `check_password(username, shadow_pass, password_type, validuntil_time,
  validuntil_null)` (passwordcheck.c:56-143) — the hook. Splits on
  `password_type != PASSWORD_TYPE_PLAINTEXT`:
  - encrypted path: tries `plain_crypt_verify(username, shadow_pass,
    username, &logdetail) == STATUS_OK` — i.e. tries the username
    itself as the plaintext password and rejects only that one case.
    [verified-by-code]
  - plaintext path: enforces min length, rejects substring match of
    username, requires at least one letter AND one non-letter,
    optionally calls `FascistCheck(password, CRACKLIB_DICTPATH)`.
    [verified-by-code]

## Notable invariants / details

- The hook is invoked for both `CREATE ROLE PASSWORD '…'` and
  `ALTER ROLE PASSWORD '…'`. `password_type` reflects whether the
  client wire-protocol value was already hashed (`md5…` /
  `SCRAM-SHA-256$…`) or sent in cleartext (`password_encryption =
  off` from a libpq pre-hashing client). [verified-by-code]
- The encrypted-path check is intentionally limited because the
  server only ever sees the *hash*; the comment block lines 70-77
  spells out that exhaustive checks against a hash are not possible
  without a reverse-the-hash oracle. [from-comment]
- `validuntil_time` and `validuntil_null` are passed to the hook but
  this implementation ignores them. The comment (passwordcheck.c:52-55)
  notes that a real policy might require non-NULL and not-too-far
  expiration. [from-comment] [ISSUE-undocumented-invariant: validity
  args dropped (nit)]
- `min_password_length` is `PGC_SUSET` so only superusers can lower
  it (passwordcheck.c:158). [verified-by-code]
- `isalpha((unsigned char) password[i])` (passwordcheck.c:122) — the
  cast to `unsigned char` is required to avoid UB on signed-char
  platforms; comment at line 119-121 acknowledges multibyte
  encodings are treated character-by-character so non-ASCII bytes
  count as non-letters. [verified-by-code] [from-comment]

## Potential issues

- passwordcheck.c:99-105. **Default minimum length of 8 bytes is below
  modern NIST guidance** (SP 800-63B recommends ≥ 8 user-chosen with
  no other constraints, or ≥ 6 random; in practice most policies
  want ≥ 12). The constraint is "bytes" not "characters" so a
  multi-byte UTF-8 password may be shorter in user-visible chars
  than the policy implies. [ISSUE-security: weak default + byte-vs-
  char mismatch (maybe)]
- passwordcheck.c:114-126. **Letter+non-letter rule rejects many
  high-entropy passphrases** that would pass real-world strength
  checks (e.g. `correcthorsebatterystaple` — all letters, no digits
  — is rejected). The comment block at top of file does not call
  this out. [ISSUE-correctness: anti-pattern composition rule (nit)]
- passwordcheck.c:80-83. **Encrypted path catches only the exact
  username == password case**, and only by feeding the username
  through `plain_crypt_verify`. A user whose client pre-hashed the
  string `"admin"` will be caught; a user who pre-hashed `"admin1"`
  is not (no other dictionary attempt is made). The README warns
  about this; the source does not. [ISSUE-doc-drift: source doesn't
  cross-ref the README's "use cracklib or write your own" caveat
  (nit)]
- passwordcheck.c:132-139. **cracklib build is optional**; on most
  binary distributions `USE_CRACKLIB` is not set and the entire
  branch is compiled out. Result: deployed `passwordcheck` typically
  enforces only "≥ 8 bytes, contains letter + non-letter, not
  username". [ISSUE-security: cracklib disabled by default → policy
  is minimal in practice (likely)]
- passwordcheck.c:78. `const char *logdetail = NULL` is passed to
  `plain_crypt_verify` to receive a diagnostic message but the
  returned `logdetail` is never inspected or logged. Quiet drop.
  [ISSUE-style: discarded diagnostic (nit)]
- passwordcheck.c:108-111. `strstr(password, username)` is a naive
  byte-substring search; "Joe Smith" containing "Joe" rejects, but
  "joe Smith" with capital J in password against lowercase username
  passes. Username case is not normalized — but PG role names are
  case-sensitive themselves, so this matches the role lookup. Worth
  documenting. [ISSUE-undocumented-invariant: substring check is
  case-sensitive (nit)]

## Cross-references

- `knowledge/issues/passwordcheck.md` — per-extension issue register
  (created if absent).
- `source/src/include/commands/user.h` — `check_password_hook_type`
  signature.
- `source/src/backend/libpq/crypt.c` — `plain_crypt_verify`.
- Companion: `contrib/passwordcheck/t/001_passwordcheck.pl` for TAP
  coverage.
