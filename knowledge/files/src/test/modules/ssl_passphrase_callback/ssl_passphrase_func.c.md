---
path: src/test/modules/ssl_passphrase_callback/ssl_passphrase_func.c
anchor_sha: e18b0cb7344
loc: 83
depth: read
---

# src/test/modules/ssl_passphrase_callback/ssl_passphrase_func.c

## Purpose

Test loadable that installs an `openssl_tls_init_hook` to supply the server
certificate's SSL passphrase via a callback instead of invoking the external
`ssl_passphrase_command`. The transformation is ROT13 — i.e. the test
deliberately stores the on-disk passphrase rot13'd so the callback's output
can be compared to the configured GUC value. `[verified-by-code]`
`ssl_passphrase_func.c:6-8`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `:35` | Registers GUC + installs `openssl_tls_init_hook` if GUC is set |
| GUC `ssl_passphrase.passphrase` | `:38` | Plain passphrase (rot13 is applied by the callback) |
| Hook `openssl_tls_init_hook` ← `set_rot13` | `:52` | OpenSSL TLS context initializer override |

## Internal landmarks

- `set_rot13` (`:56`) — warns if `ssl_passphrase_command` is also set
  (`:59-61`), then calls `SSL_CTX_set_default_passwd_cb(context,
  rot13_passphrase)`.
- `rot13_passphrase` (`:67`) — `strlcpy` the GUC into the OpenSSL buffer and
  apply ROT13 to ASCII letters in place; non-letters pass through. Returns
  `strlen(buf)` per OpenSSL's callback contract.

## Invariants & gotchas

- TEST MODULE — never load in production: a callback that returns a known
  transformation of a GUC value is not a security model.
- The hook is only installed when `ssl_passphrase.passphrase` is non-NULL at
  `_PG_init` time (`:51`); a subsequent SIGHUP-driven change of the GUC
  cannot retroactively install the hook.
- Hook install is irreversible global state once the .so is loaded
  `[verified-by-code]` `:52`.
- `ssl_passphrase_command` setting is **ignored** (WARNING emitted) once the
  hook is installed `[verified-by-code]` `:59-61`.

## Cross-refs

- `source/src/include/libpq/libpq.h` — `openssl_tls_init_hook` declaration.
- `source/src/backend/libpq/be-secure-openssl.c` — where the hook is invoked.
