---
path: src/test/modules/ldap_password_func/ldap_password_func.c
anchor_sha: e18b0cb7344
loc: 56
depth: read
---

# src/test/modules/ldap_password_func/ldap_password_func.c

## Purpose

In-tree test module that exercises the `ldap_password_hook` extension point
used by LDAP authentication. Mounts a trivial rot13 transform on the configured
`ldapbindpasswd` so the LDAP test suite can confirm the hook is invoked on the
password before the LDAP bind happens. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `ldap_password_func.c:31` | Installs `ldap_password_hook = rot13_passphrase` |
| `rot13_passphrase` (static) | `:37` | Allocates a palloc'd copy and rotates ASCII alpha by 13 |

## Internal landmarks

- `_PG_init` is the entire installation surface — no GUCs, no SQL functions.
- `rot13_passphrase` returns a freshly `palloc`'d string the caller owns; it
  does **not** scribble over the input.

## Invariants & gotchas

- **Test module — never load in production.** Anyone with this in
  `shared_preload_libraries` would silently mangle every LDAP bind password.
- The hook is global process state; once installed it stays installed for the
  life of the postmaster. There is no uninstall path.
- Uses `strlcpy` + in-place rotate so it's safe regardless of input encoding —
  only ASCII A-Z / a-z are touched.

## Cross-refs

- `source/src/include/libpq/auth.h` — declares `ldap_password_hook`.
- `source/src/backend/libpq/auth.c` — the LDAP authentication path that calls
  the hook before `ldap_simple_bind_s`.
