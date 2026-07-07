# contrib-passwordcheck (password-strength enforcement)

- **Source path:** `source/contrib/passwordcheck/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Loading model:** `shared_preload_libraries` (no `.control` file)
- **Surface:** zero SQL functions; one GUC; one hook installed

## 1. Purpose

Reject weak passwords at `CREATE ROLE` / `ALTER ROLE` time. Installs
the `check_password_hook` so that any password change runs through a
configurable strength check before the catalog is updated. Optional
integration with libcrack (dictionary check) if built with
`USE_CRACKLIB`.

A 167-LOC single-file extension [verified-by-code `wc -l
source/contrib/passwordcheck/passwordcheck.c`]. Despite its size,
it's the canonical example of how to wire a `check_password_hook`
in a contrib module — the template for any custom password-policy
extension.

## 2. The hook

```c
static check_password_hook_type prev_check_password_hook = NULL;
```

[verified-by-code `passwordcheck.c:34`]

In `_PG_init`, the module saves the previous hook (chain) and
installs its own:

```c
prev_check_password_hook = check_password_hook;
check_password_hook = check_password;
```

The hook is fired by `CREATE ROLE PASSWORD '...'` and
`ALTER ROLE PASSWORD '...'`. The callback can raise an ERROR to
reject the password.

## 3. The hook signature

```c
static void
check_password(const char *username,
               const char *shadow_pass,
               PasswordType password_type,
               Datum validuntil_time,
               bool validuntil_null);
```

`password_type` discriminates:
- `PASSWORD_TYPE_PLAINTEXT` — the password is the user's actual
  text. Strength checks are meaningful.
- `PASSWORD_TYPE_MD5` / `PASSWORD_TYPE_SCRAM_SHA_256` — already
  hashed by the client; the module can only check for trivially-
  detectable patterns (e.g. exact-match-to-username for MD5).

The extension's logic branches on `password_type` — plaintext
gets the full check; hashed gets a minimal "doesn't equal a
trivial transform of username" check.

## 4. The default checks

For plaintext passwords:

- **Length ≥ `passwordcheck.min_password_length`** (GUC, default 8).
- **At least one letter AND at least one non-letter** (digit /
  symbol). Prevents all-digit / all-letter passwords.
- **Not a substring of the username** (case-insensitive).
- **Not in libcrack's dictionary** if built with `USE_CRACKLIB`.

## 5. The single GUC

```c
static int min_password_length = 8;
```

[verified-by-code `passwordcheck.c:37`]

`passwordcheck.min_password_length` — integer, bounded
[1, INT_MAX]. Registered in `_PG_init` via `DefineCustomIntVariable`.

Other policy aspects (require-digit, require-symbol, max-length,
etc.) are NOT configurable — the module is intentionally a
**template**, not a feature-complete enforcer. Production
deployments are expected to fork it or write a custom equivalent.

## 6. The hook chain

```c
if (prev_check_password_hook)
    prev_check_password_hook(username, shadow_pass, ...);
```

[verified-by-code `passwordcheck.c:63-64`]

Like every well-behaved hook installer, `passwordcheck` calls
the previous hook before running its own checks. So multiple
password-policy modules can stack.

## 7. Production-use guidance

- **Load via `shared_preload_libraries`** in `postgresql.conf`. The
  hook must be installed before any `CREATE ROLE` runs.
- **The defaults are sane but minimal.** Real password policies
  need additional checks (uppercase, symbols, common-password
  list, password history, etc.). passwordcheck is the
  jumping-off point.
- **`USE_CRACKLIB` requires linking against libcrack** at build
  time. Most distros don't ship that variant; check
  `pg_config --configure` for the flag.
- **No `.control` file, no `CREATE EXTENSION` step.** Loading via
  `shared_preload_libraries` is the entirety of activation.

## 8. The crucial limitation: hashed passwords are blind

If clients hash passwords before sending them (MD5 / SCRAM), the
server NEVER sees the plaintext. passwordcheck on hashed passwords
can only detect:

- Exact-match to username after hash.
- Trivially-predictable hashes.

It CANNOT detect dictionary words, weak passwords, etc. — those
require seeing the plaintext.

The only way to force plaintext-visibility is to set
`password_encryption = scram-sha-256` and require client-side
plaintext submission. Most modern clients hash, so this is
rarely workable.

## 9. Invariants

- **[INV-1]** No SQL surface; activated via `shared_preload_libraries`.
- **[INV-2]** Hook chain via `prev_check_password_hook` —
  composable with other password modules.
- **[INV-3]** Strength checks meaningful only for
  `PASSWORD_TYPE_PLAINTEXT`; hashed types get minimal checks.
- **[INV-4]** Single GUC; intentionally minimal — meant as a
  template.
- **[INV-5]** Raising ERROR in the hook rejects the password
  change.

## 10. Useful greps

- The hook entry point:
  `grep -n 'check_password\|prev_check_password_hook' source/contrib/passwordcheck/passwordcheck.c`
- The default checks:
  `grep -n 'min_password_length\|cracklib' source/contrib/passwordcheck/passwordcheck.c`
- libcrack conditional:
  `grep -n 'USE_CRACKLIB' source/contrib/passwordcheck/passwordcheck.c`

## 11. Cross-references

- `.claude/skills/bgworker-and-extensions/SKILL.md` —
  shared_preload_libraries loading + hook installation pattern.
- `.claude/skills/gucs-config/SKILL.md` — `DefineCustomIntVariable`
  for the policy GUC.
- `.claude/skills/extension-development/SKILL.md` — extension
  loading model.
- `knowledge/subsystems/contrib-auth_delay.md` — companion
  auth-related contrib; both are hook installers in the auth path.
- `source/src/backend/libpq/crypt.c` — the
  `check_password_hook` declaration + fire site.
- `source/src/include/commands/user.h` — `PasswordType` enum.
- `source/contrib/passwordcheck/passwordcheck.c` — implementation
  (167 LOC).

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/passwordcheck/passwordcheck.c`](../files/contrib/passwordcheck/passwordcheck.c.md) |

<!-- /files-owned:auto -->
