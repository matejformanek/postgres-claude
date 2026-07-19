# openssl.c

## One-line summary

The OpenSSL backend that backs every PX primitive — digests via
`EVP_MD_*`, ciphers via `EVP_CIPHER_CTX_*`, RNG via implicit
`pg_strong_random` (NOT `RAND_bytes`), FIPS-mode detection via
`EVP_default_properties_is_fips_enabled` (≥OpenSSL 3.0) or
`FIPS_mode()` (legacy 1.1.1 FIPS forks). With the PG ≥ 18 removal of
the internal/Mhash backends, openssl.c is the **only** implementation
of the PX cipher and digest contracts.

Covers `source/contrib/pgcrypto/openssl.c` (888 lines).

## Public API / entry points

### Required by `px.h`

- `int px_find_digest(const char *name, PX_MD **res)` —
  `openssl.c:160-211`. Wraps `EVP_get_digestbyname` + `EVP_MD_CTX_create`,
  registers the handle with the current `ResourceOwner` for
  abort-safety.
- `int px_find_cipher(const char *name, PX_Cipher **res)` —
  `openssl.c:775-828`. Alias-resolves name (e.g. `'aes'` → `'aes-cbc'`),
  scans `ossl_cipher_types[]`, allocates `OSSLCipher` and `EVP_CIPHER_CTX`,
  wires init/encrypt/decrypt.
- `bool CheckFIPSMode(void)` — `openssl.c:843-863`. Returns true if
  OpenSSL reports FIPS mode enabled.
- `void CheckBuiltinCryptoMode(void)` — `openssl.c:873-888`.
  ereport(ERROR) if `builtin_crypto_enabled == BC_OFF`, or
  `BC_FIPS && CheckFIPSMode()`.

### File-static glue

- `ResOwnerReleaseOSSLDigest` / `ResOwnerReleaseOSSLCipher` —
  ResourceOwner release callbacks (`openssl.c:215-222, 832-836`).
- `gen_ossl_encrypt` / `gen_ossl_decrypt` — generic EVP cipher
  drivers (`openssl.c:336-395`).
- `bf_check_supported_key_len` — `openssl.c:402-445`. Run-time test
  that this OpenSSL build's Blowfish supports >128-bit keys.
- Per-cipher `*_init` functions: `bf_init` (`:447-475`),
  `ossl_des_init` (`:479-494`), `ossl_des3_init` (`:498-513`),
  `ossl_cast_init` (`:517-531`), `ossl_aes_init` + `_ecb_init` +
  `_cbc_init` + `_cfb_init` (`:535-648`).

## Key invariants

- **All OpenSSL handles are owned by `ResourceOwner`**.
  `OSSLDigest` and `OSSLCipher` carry a `ResourceOwner owner` field;
  on transaction abort, the release callback runs `EVP_MD_CTX_destroy`
  / `EVP_CIPHER_CTX_free` and `pfree`s the wrapper. The comment at
  `openssl.c:54-56, 251-253` is explicit: this is the
  abort-safety contract. [verified-by-code]
- **Wrapper structs live in `TopMemoryContext`**, not the current
  context (`openssl.c:179, 797`). This means they survive subtransaction
  rollback; the ResourceOwner cleanup handles their destruction
  instead. [verified-by-code]
- **`PX_MD` / `PX_Cipher` (the vtables themselves) live in the
  current memory context** (`openssl.c:200, 816`), so they get
  freed on subxact rollback. The `OSSLDigest`/`OSSLCipher`
  ResourceOwner cleanup handles the OpenSSL handles independently.
  This split is the abort-safety dance.
- **`od->init` is a one-shot flag**: cipher state in OSSLCipher is
  set up at `bf_init` etc, but the actual EVP `EncryptInit_ex` /
  `DecryptInit_ex` call happens lazily on the first
  `gen_ossl_encrypt` or `_decrypt` call (`openssl.c:345-355,
  375-385`). Marked `od->init = true` after.
- **Cipher init order**: `EVP_EncryptInit_ex(ctx, evp_ciph, NULL,
  NULL, NULL)` then `set_padding` then `set_key_length` then a
  second `EVP_EncryptInit_ex(ctx, NULL, NULL, key, iv)`. The
  two-step is needed for variable key length to take effect.
  [from-comment-pattern; verified-by-code `:347-355`]

## Notable internals

### Wrapped OpenSSL primitives

**Digests**: anything `EVP_get_digestbyname` returns — typically
`md5`, `sha1`, `sha224`, `sha256`, `sha384`, `sha512`, `ripemd160`,
`sm3`, `blake2*`. Whatever OpenSSL has compiled in. pgcrypto
filters nothing.

**Ciphers (`openssl.c:757-771`)**:
- `bf-cbc`, `bf-ecb`, `bf-cfb` — Blowfish (64-bit block, up to
  448-bit key with strong-key check)
- `des-ecb`, `des-cbc` — single DES (56-bit effective key)
- `des3-ecb`, `des3-cbc` — 3DES (192-bit raw / 168-bit effective)
- `cast5-ecb`, `cast5-cbc` — CAST5 (64-bit block, 40-128 bit key)
- `aes-ecb`, `aes-cbc`, `aes-cfb` — AES-128/192/256, mode selected
  by key length.

**No AEAD modes** (no GCM, no CCM, no Poly1305). No XTS, no CTR,
no OFB. [verified-by-code `openssl.c:757-770`]

### Aliases (`openssl.c:654-671`)

`bf` → `bf-cbc`, `aes` → `aes-cbc`, `rijndael` → `aes-cbc`, `3des` →
`des3-cbc`, etc. Case-insensitive resolution via
`px_resolve_alias`.

### Error mapping

Every EVP-level failure becomes one of three PXE codes:

- `PXE_CIPHER_INIT` — any setup failure (key length, padding,
  init).
- `PXE_ENCRYPT_FAILED` — `EVP_EncryptUpdate` or `EVP_EncryptFinal_ex`
  returned 0.
- `PXE_DECRYPT_FAILED` — `EVP_DecryptUpdate` or `EVP_DecryptFinal_ex`
  returned 0.

**`ERR_get_error()` is never called**. This is documented as a known
audit-gap in px.md but worth restating here: when EVP fails, OpenSSL
pushes a detailed error onto its thread-local stack; pgcrypto
discards it. Even `<openssl/err.h>` is included
(`openssl.c:36`), but only for header transitive needs — no calls
into `ERR_*`. [ISSUE-audit-gap: ERR_get_error never read (confirmed)]

### IV handling per cipher mode

In each `*_init`, when `iv` is non-NULL: `memcpy(od->iv, iv, bs)`
where `bs = gen_ossl_block_size(c)`. When `iv` is NULL:
`memset(od->iv, 0, bs)`. So a NULL IV maps to all-zero IV at the
cipher level. The user-facing zero-IV behavior originates in
`px.c:combo_init` (which passes through), but openssl.c also
zero-fills here as a defense.
[ISSUE-security: zero-IV default for CBC/CFB (confirmed)]
For ECB modes (`bf-ecb`, `des-ecb`, `des3-ecb`, `cast5-ecb`,
`aes-ecb`), the IV is irrelevant — but ECB itself leaks plaintext
structure.

### Blowfish key strength check

`bf_check_supported_key_len` (`openssl.c:404-445`): runs a known-answer
test with a 448-bit key. If the OpenSSL build silently truncated, the
KAT fails, and pgcrypto rejects keys >128 bits with `PXE_KEY_TOO_BIG`.
Cached in static `bf_is_strong`. [verified-by-code]

### `OSSLCipher.key[MAX_KEY]` is a fixed 64-byte array

`MAX_KEY = 512/8` (`openssl.c:46`). Any cipher with a key ≤ 512
bits fits. The `memcpy(od->key, key, klen)` at `openssl.c:468, 487,
506, 524, 550` writes into this fixed buffer. The buffer is part of
the `OSSLCipher` allocated in `TopMemoryContext`, so the key persists
for the lifetime of the cipher handle. **It is freed via `pfree`
without scrubbing** (`free_openssl_cipher` at `openssl.c:291-298`).
[ISSUE-security: cipher key in OSSLCipher not scrubbed on free
(likely)]
The ResourceOwner cleanup also calls `free_openssl_cipher` → same
issue.

### `OSSLCipher.iv[MAX_IV]` — 16 bytes

`MAX_IV = 128/8 = 16` (`openssl.c:47`). Sufficient for all
supported ciphers (largest is AES with 16-byte block). Same
unscrubbed-on-free issue.

### FIPS-mode check

`openssl.c:843-863`. Two-path:
- OpenSSL ≥ 3.0: `EVP_default_properties_is_fips_enabled(NULL)`.
- OpenSSL < 3.0 (1.1.1 FIPS forks): `FIPS_mode()`.

Comment at `:847-854` explains why both paths exist (some 1.1.1
forks like RHEL/CentOS shipped FIPS-validated 1.1.1 even though
upstream dropped FIPS in 1.0.2 era). [from-comment]

### `CheckBuiltinCryptoMode` semantics

`openssl.c:873-888`:
- `BC_ON` (default): always allow.
- `BC_OFF`: ereport(ERROR) "use of built-in crypto functions is
  disabled".
- `BC_FIPS`: ereport(ERROR) only if OpenSSL is in FIPS mode.

So `BC_FIPS` is the "let FIPS gate this" mode — pgcrypto's vendored
crypt-blowfish/crypt-sha/etc are non-FIPS-validated and should not
run when OpenSSL is in FIPS strict mode.

## Crypto trust boundary / Phase D surface

- **No RAND_bytes anywhere**. `<openssl/rand.h>` is included
  (`openssl.c:37`) but no call to `RAND_bytes` or `RAND_priv_bytes`
  exists in openssl.c. RNG comes from `pg_strong_random` in
  pgcrypto.c and px-crypt.c. [verified-by-code]
- **EVP error stack discarded** — confirmed. Auditor visibility loss.
- **All-zero IV for NULL IV** — confirmed, both in px.c:combo_init
  and openssl.c:*_init.
- **No AEAD modes** — no integrity guarantees from cipher itself.
  Combined with no constant-time tag comparison (px-hmac.md), this
  is a CBC-padding-oracle-friendly stack.
- **Key/IV stored in unscrubbed `OSSLCipher`** — likely the biggest
  Phase D finding for openssl.c.
- **`MemoryContextAlloc(TopMemoryContext, ...)`** for OSSLDigest/
  OSSLCipher means keys live until ResourceOwner cleanup or process
  exit. On normal SELECT completion, the ResourceOwner cleanup runs
  (RESOURCE_RELEASE_BEFORE_LOCKS). So keys don't linger across
  queries — but the freed allocations may sit in the
  TopMemoryContext freelist with their bytes intact.
- **Blowfish KAT** is a defense-in-depth check for OpenSSL builds
  that silently truncate to 128 bits. Good practice.
  [verified-by-code `:404-445`]
- **FIPS-mode handoff** is honest: bcrypt/crypt-sha/etc are
  vendored, not FIPS-validated, so `BC_FIPS` mode blocks them.

## Cross-references

- `px.c` — defines `PXE_*` codes that openssl.c returns.
- `pgcrypto.c` — `_PG_init` defines the `builtin_crypto_enabled`
  GUC that `CheckBuiltinCryptoMode` reads.
- `src/backend/utils/resowner/resowner.c` — ResourceOwner API
  (`ResourceOwnerRemember`, `ResourceOwnerForget`,
  `RESOURCE_RELEASE_BEFORE_LOCKS`).
- A5 `src/common/cryptohash_openssl.c` — separate OpenSSL-EVP
  wrapper for core PG. Duplicate EVP plumbing.
- `src/common/hmac_openssl.c` — core HMAC. pgcrypto uses px-hmac.c
  instead.
- `<openssl/evp.h>`, `<openssl/err.h>`, `<openssl/rand.h>` —
  external dependencies.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-audit-gap: OpenSSL ERR_get_error never called (confirmed)]
  — every EVP failure collapsed to one of 3 PXE codes.
- [ISSUE-security: OSSLCipher key/iv unscrubbed on free (likely)] —
  `openssl.c:291-298`. `EVP_CIPHER_CTX_free` does internal cleanup
  but the cached `od->key[MAX_KEY]` and `od->iv[MAX_IV]` in the
  TopMemoryContext-allocated OSSLCipher are pfree'd without scrub.
- [ISSUE-security: all-zero IV when caller passes NULL (confirmed)]
  — `openssl.c:472-473, 491-492, 510-511, 527-528, 553-555`.
- [ISSUE-defense-in-depth: no AEAD modes in 2026 (likely)] —
  `openssl.c:757-770`. ChaCha20-Poly1305 / AES-GCM available in
  OpenSSL since ~2014, never wired up.
- [ISSUE-defense-in-depth: DES, 3DES, Blowfish, CAST5 still
  available (likely)] — weak ciphers in the 2026 lookup table.
- [ISSUE-correctness: `bf_is_strong` cached as a static, set on
  first call (nit)] — fine in practice but means the first call
  pays the KAT cost. Not a bug, just a perf nit.
- [ISSUE-api-shape: `EVP_CIPHER_CTX_set_key_length` always called
  even when redundant (nit)] — `openssl.c:351, 381`. Harmless.
- [ISSUE-documentation: comment at `openssl.c:226-228` says "We use
  OpenSSL's EVP* family of functions" but the file also uses
  legacy `EVP_aes_128_cbc()` etc (nit)] — modern OpenSSL 3.0 prefers
  `EVP_CIPHER_fetch`. Migration target.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgcrypto.md](../../../subsystems/contrib-pgcrypto.md)
