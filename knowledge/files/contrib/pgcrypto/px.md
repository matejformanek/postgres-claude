# px.c / px.h

## One-line summary

The PX ("PostgreSQL eXtension") abstract API for pgcrypto: opaque
function tables for digests, HMACs, ciphers, and "combo" (cipher +
padding); the `PXE_*` error code enum and `px_strerror`/`px_THROW_ERROR`
mapping; the `combo_*` glue that bolts a `PX_Cipher` to a padding
choice; and miscellaneous primitives (`px_memset`, `px_resolve_alias`,
`px_debug`). Covers `source/contrib/pgcrypto/px.c` (341 lines) and
`source/contrib/pgcrypto/px.h` (239 lines).

## Public API / entry points

### Provider lookups (`px.h:179-182`)

- `int px_find_digest(const char *name, PX_MD **res)` — implemented
  in `openssl.c:160-211`.
- `int px_find_hmac(const char *name, PX_HMAC **res)` — implemented
  in `px-hmac.c:142-176`.
- `int px_find_cipher(const char *name, PX_Cipher **res)` —
  `openssl.c:775-828`.
- `int px_find_combo(const char *name, PX_Combo **res)` —
  `px.c:285-341` (the only `px_find_*` defined here).

### Error/debug (`px.c`)

- `pg_noreturn void px_THROW_ERROR(int err)` — `px.c:93-109`.
  `ereport(ERROR, ...)`, with a special-case `ERRCODE_INTERNAL_ERROR`
  for `PXE_NO_RANDOM` (RNG failure should not look like a user input
  bug); all other errors use `ERRCODE_EXTERNAL_ROUTINE_INVOCATION_EXCEPTION`.
  [verified-by-code]
- `const char *px_strerror(int err)` — `px.c:111-120`. Linear search
  over a 38-entry table; returns `"Bad error code"` for unknown.
  [verified-by-code]
- `void px_memset(void *ptr, int c, size_t len)` — `px.c:123-127`.
  Plain `memset` wrapped in a separately-defined function to prevent
  the compiler from optimizing it away when scrubbing secrets.
  Comment at `px.c:122` is explicit. [verified-by-code, from-comment]
  This is NOT `explicit_bzero` (which exists in `src/port`); the
  optimizer-defeat trick here relies on the call-site being opaque to
  the compiler across the TU boundary. Modern LTO may still elide it.
- `const char *px_resolve_alias(const PX_Alias *list, const char *name)`
  — `px.c:129-139`. Case-insensitive lookup using `pg_strcasecmp`.
- `void px_set_debug_handler(void (*handler)(const char *))` —
  `px.c:143-147`. Used by tests; never set in production
  pgcrypto code.
- `void px_debug(const char *fmt, ...)` — `px.c:149-163`. No-op
  unless a handler is registered.

### Combo provider (`px.c:285-341`)

`px_find_combo` parses a name like `"aes-cbc/pad:pkcs"` and builds a
`PX_Combo` that wraps a `PX_Cipher` plus a padding flag (0=none,
1=pkcs).

### FIPS / builtin crypto gating (`px.h:193-194`, implementation in `openssl.c`)

- `bool CheckFIPSMode(void)` — `openssl.c:843-863`.
- `void CheckBuiltinCryptoMode(void)` — `openssl.c:873-888`.

### PX type structs (`px.h:99-177`)

`PX_MD`, `PX_HMAC`, `PX_Cipher`, `PX_Combo` — vtable-style structs
with function-pointer fields and a `p`/`ptr` union for backend
private data. Convenience macros at `px.h:202-237` (`px_md_*`,
`px_hmac_*`, `px_cipher_*`, `px_combo_*`) dispatch through the vtable.

## Key invariants

- **Error codes are negative**, `PXE_OK == 0`. Numeric values must
  stay stable to not break the `px_err_list` table in `px.c:42-84`.
  Some slots are commented "unused" (-1, -4, -10, -11, -16, -108) —
  intentionally not reused so any external lookup of the codes stays
  stable. [verified-by-code `px.h:46-90`]
- **`px_THROW_ERROR` is `pg_noreturn`**. Callers don't need to
  return after it. [verified-by-code `px.h:184`]
- **All allocations happen in `CurrentMemoryContext` except for
  OpenSSL-tied state** which `openssl.c` puts in `TopMemoryContext`
  with `ResourceOwner` callbacks. [verified-by-code]
- **`combo_init` is the only place IV truncation happens**:
  `px.c:194-202`. If `ivlen > cipher->iv_size`, only the first
  `iv_size` bytes are copied; if `ivlen < iv_size`, the rest are
  zero-padded from `palloc0`. [verified-by-code]
- **`combo` always defaults to PKCS padding** when no
  `pad:` modifier is given (`px.c:319-320`). [verified-by-code]

## Notable internals

### PX_*_RES error-code mapping

`px_err_list[]` at `px.c:42-84` maps each `PXE_*` to a human-readable
string. The semantic categories:

- `PXE_NO_HASH`, `PXE_NO_CIPHER`, `PXE_HASH_UNUSABLE_FOR_HMAC` —
  user picked a bad algorithm name.
- `PXE_BAD_OPTION`, `PXE_BAD_FORMAT`, `PXE_KEY_TOO_BIG`,
  `PXE_BAD_SALT_ROUNDS`, `PXE_UNKNOWN_SALT_ALGO`,
  `PXE_ARGUMENT_ERROR` — bad input.
- `PXE_CIPHER_INIT`, `PXE_ENCRYPT_FAILED`, `PXE_DECRYPT_FAILED` —
  OpenSSL-internal failure. **These collapse the entire OpenSSL
  error stack into one PXE_* code** — `ERR_get_error()` is never
  read. The auditor loses visibility on *which* OpenSSL primitive
  failed and why. [ISSUE-audit-gap: OpenSSL error stack discarded
  (confirmed)]
- `PXE_NO_RANDOM` — RNG failure. Specially escalated to
  `ERRCODE_INTERNAL_ERROR` in `px_THROW_ERROR`.
- `PXE_BUG` — pgcrypto internal invariant violation.
- `PXE_PGP_*` (-100..-123) — PGP-subsystem errors, used by
  pgp-decrypt.c / pgp-pubkey.c / etc.

### Combo dispatch

`px_find_combo` (`px.c:285-341`):
1. `pstrdup` the input name.
2. `parse_cipher_name` (`px.c:243-281`) splits on `/`, accepts only
   `pad:none` / `pad:pkcs` as a modifier.
3. Calls `px_find_cipher` to get the cipher (provided by `openssl.c`).
4. Wraps with `combo_init` / `combo_encrypt` / `combo_decrypt` /
   `combo_free`.

`combo_init` (`px.c:181-216`) copies the user-supplied key and IV
into `palloc0`'d buffers (sized to `key_size` / `iv_size`), then
calls the underlying cipher's `init`. This is where **the silent IV
truncation** and **silent key truncation** happen:

- If `klen > ks`, `klen = ks` — silently truncated
  (`px.c:204-205`).
- If `ivlen > ivs`, only first `ivs` bytes copied
  (`px.c:198-199`).
- If `ivlen == 0` and `ivs > 0`, all-zero IV (palloc0 of `ivs`
  bytes, no overwrite) (`px.c:197`).

This is the IV-reuse footgun referenced from pgcrypto.c notes.

### Padding parser

`parse_cipher_name` accepts `"<cipher>"`, `"<cipher>/pad:<mode>"`, or
extra empty `/` slots between. Rejects unknown options with
`PXE_BAD_OPTION`, missing `:` with `PXE_BAD_FORMAT`.

## Crypto trust boundary / Phase D surface

- **`px_memset` is the only "scrub secrets" primitive in pgcrypto**.
  Unlike `explicit_bzero(3)` in OpenBSD/glibc, `px_memset` is just a
  function-call wrapper around `memset`. The comment at `px.c:122`
  says "must not be optimized away" — but **link-time optimization
  (LTO) can still elide it** because the function body is visible to
  the linker. A modern build with `-flto` may scrub nothing.
  [ISSUE-security: px_memset can be elided under LTO (likely)]
- **Silent key truncation** at `px.c:204-205` — a user passing a
  500-bit key to AES-256 gets the first 32 bytes used, no error.
  Documented but easy to misuse.
  [ISSUE-security: silent key truncation in combo_init (maybe)]
- **Zero-IV default** — confirmed at `px.c:197`. The `palloc0(ivs)`
  is intentional but means `encrypt(data, key, 'aes-cbc')`
  (no IV variant) always uses the all-zero IV.
  [ISSUE-security: zero-IV when no IV supplied (confirmed, but
  documented behavior)]
- **OpenSSL error stack discarded** — `px.c` error mapping
  drops `ERR_get_error()`. For an auditor trying to diagnose a CFB
  failure vs an OAEP failure, all they see is "Decryption failed".
  [ISSUE-audit-gap: OpenSSL error chain not surfaced (confirmed)]
- **`px_strerror` is safe-by-construction**: no user input ever
  reaches the format string. (Unlike e.g. `px_debug`'s vsnprintf,
  but that's gated by the never-installed-in-prod debug handler.)
- **`px_resolve_alias` is case-insensitive**, so `'AES'` and `'aes'`
  resolve identically. Defense-in-depth: pgcrypto.c already
  lowercases via `downcase_truncate_identifier`.

## Cross-references

- `openssl.c` — provides `px_find_digest`, `px_find_cipher`,
  `CheckFIPSMode`, `CheckBuiltinCryptoMode`.
- `px-hmac.c` — provides `px_find_hmac` (built on top of `PX_MD`).
- `px-crypt.c` — calls `CheckBuiltinCryptoMode` for password-hash path.
- A5 `src/common/cryptohash.c` — parallel abstraction layer for the
  CORE backend; pgcrypto deliberately doesn't reuse it.
- A5 `src/common/cryptohash_openssl.c` — separate OpenSSL wrapping
  for core (libpq SCRAM, replication). Duplicate of what's in
  pgcrypto's openssl.c.
- `src/include/port.h` — `explicit_bzero` exists. pgcrypto does NOT
  use it.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `px_memset` may be elided by LTO (likely)] —
  `px.c:123-127`. Modern compilers with link-time optimization can
  see through the function call and remove the dead store. Should
  use `explicit_bzero` from `src/port` (already vendored for the
  rest of the corpus, e.g. `src/backend/libpq/auth-scram.c`).
- [ISSUE-audit-gap: OpenSSL error stack collapsed to PXE_* (confirmed)]
  — `px.c:42-84`. `ERR_get_error()` never called; the auditor loses
  the OpenSSL-internal reason.
- [ISSUE-security: silent IV truncation/zero-padding (maybe)] —
  `px.c:198-202`. User passing wrong-length IV gets a silently mangled
  IV. Should ereport.
- [ISSUE-security: silent key truncation (maybe)] — `px.c:204-205`.
  Same issue. AES-256 with a 24-byte key silently downgrades to
  AES-192? No — `ossl_aes_init` (`openssl.c:535-558`) picks the key
  size class based on klen, so the truncation in `combo_init` doesn't
  alter the key length seen by AES. But for ciphers with a fixed
  key size (DES, DES3, CAST5), truncation is real.
- [ISSUE-api-shape: `px_debug` is always compiled in but never
  enabled (nit)] — `PX_DEBUG` is defined at `px.h:38`, so
  `px_debug` exists; but `debug_handler` is never set in production
  code. Dead path.
- [ISSUE-correctness: `px_find_combo` error path leaks on
  `PXE_BAD_OPTION` from padding check (maybe)] — `px.c:317`
  `goto err1` after a `pad:` parse failure, but the `cipher` was
  already populated. The `err1` block does `px_cipher_free(cx->cipher)`
  so this is actually fine. Verified.
