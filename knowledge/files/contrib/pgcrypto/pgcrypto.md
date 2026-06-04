# pgcrypto.c / pgcrypto.h

## One-line summary

The SQL-callable surface of the pgcrypto extension: `digest`, `hmac`,
`crypt`, `gen_salt`, `encrypt`/`decrypt` (with and without IV),
`gen_random_bytes`, `gen_random_uuid`, plus the `pgcrypto.builtin_crypto_enabled`
GUC defined in `_PG_init`. Covers `source/contrib/pgcrypto/pgcrypto.c`
(518 lines) and the trivial `source/contrib/pgcrypto/pgcrypto.h` (37 lines,
just an `#include "fmgr.h"` wrapper).

## Public API / entry points

All entry points use `PG_FUNCTION_INFO_V1` and are wired into SQL via
`pgcrypto--1.3.sql` (and the upgrade scripts).

- `_PG_init` — `source/contrib/pgcrypto/pgcrypto.c:67-83` —
  registers GUC `pgcrypto.builtin_crypto_enabled` (`PGC_SUSET`,
  enum {`on`, `off`, `fips`}, default `BC_ON`) and calls
  `MarkGUCPrefixReserved("pgcrypto")`. [verified-by-code]
- `pg_digest(bytea, text) → bytea` — `pgcrypto.c:86-119`. Resolves a
  PX hash by name via `find_provider(... px_find_digest ...)`, allocates
  result of `px_md_result_size()`, runs `update`/`finish`/`free`.
  [verified-by-code]
- `pg_hmac(bytea, bytea, text) → bytea` — `pgcrypto.c:122-161`.
  Resolves `PX_HMAC`, no constant-time output handling (raw bytes
  returned; caller is responsible for any comparison discipline).
  [verified-by-code]
- `pg_gen_salt(text) → text` — `pgcrypto.c:165-184`. Reads salt-type
  name into a 129-byte stack buf (`PX_MAX_SALT_LEN + 1`), calls
  `px_gen_salt(buf, buf, 0)` (in-place: first arg is type name, second
  arg is output buf — same storage). [verified-by-code]
- `pg_gen_salt_rounds(text, int4) → text` — `pgcrypto.c:188-207`.
  Same shape with explicit rounds. [verified-by-code]
- `pg_crypt(text, text) → text` — `pgcrypto.c:210-246`. Allocates
  `PX_MAX_CRYPT` (128) bytes for result, dispatches via `px_crypt`.
  Returns `ERRCODE_EXTERNAL_ROUTINE_INVOCATION_EXCEPTION` if `px_crypt`
  returns NULL. [verified-by-code]
- `pg_encrypt(bytea, bytea, text) → bytea` — `pgcrypto.c:249-295`.
  Calls `px_combo_init(c, key, klen, NULL, 0)` — note the **NULL/0 IV
  pair**, which means the combo layer in `px.c` allocates `ivs` zero
  bytes (see Phase D notes). [verified-by-code]
- `pg_decrypt(bytea, bytea, text) → bytea` — `pgcrypto.c:298-343`.
  Mirror of encrypt; also NULL IV. [verified-by-code]
- `pg_encrypt_iv(bytea, bytea, bytea, text) → bytea` — `pgcrypto.c:346-397`.
  Caller supplies IV. [verified-by-code]
- `pg_decrypt_iv(bytea, bytea, bytea, text) → bytea` — `pgcrypto.c:400-451`.
  [verified-by-code]
- `pg_random_bytes(int4) → bytea` — `pgcrypto.c:454-475`. Length
  bounded to `[1, 1024]`. Backed by **`pg_strong_random`** (from
  `src/common/pg_prng` / OS RNG abstraction layer), NOT
  OpenSSL's `RAND_bytes` directly. [verified-by-code]
- `pg_random_uuid() → uuid` — `pgcrypto.c:478-485`. Tail-calls the
  built-in `gen_random_uuid` from `src/backend/utils/adt/uuid.c:524`.
  pgcrypto's name is now a thin alias. [verified-by-code]
- `pg_check_fipsmode() → bool` — `pgcrypto.c:487-493`. Wraps
  `CheckFIPSMode()` from openssl.c. [verified-by-code]
- `find_provider(text *, PFN, const char *, int silent)` — internal
  helper at `pgcrypto.c:495-518`. Lowercases the algorithm name via
  `downcase_truncate_identifier` and dispatches to `px_find_digest`/
  `px_find_hmac`/`px_find_combo`. [verified-by-code]

## Key invariants

- **Argument resolution order**: every SQL function looks up the
  algorithm name (last text arg) **before** unpacking input bytea, so a
  bad name throws before any allocation of result buffer.
  [verified-by-code `pgcrypto.c:101,139,265,...`]
- **Result allocation lifetime**: every result `bytea` is `palloc`ed
  directly with `VARHDRSZ + N` and returned. No long-lived state.
  [verified-by-code]
- **No `CheckBuiltinCryptoMode` in this file**. The hook lives only in
  `px_crypt` / `px_gen_salt`. So `digest`, `hmac`, `encrypt*`,
  `decrypt*`, `gen_random_*` all bypass the GUC entirely — they
  always go through OpenSSL. [verified-by-code, see Phase D note]
- **GUC level**: `pgcrypto.builtin_crypto_enabled` is `PGC_SUSET`, so
  only superusers (or members with set role) can change it.
  [verified-by-code `pgcrypto.c:77`]

## Notable internals

- The text/bytea argument unpacking idiom is consistent: `PG_GETARG_*_PP`
  (compressed-aware), `VARSIZE_ANY_EXHDR`/`VARDATA_ANY`, and matching
  `PG_FREE_IF_COPY` at the tail.
- `find_provider`'s `silent` parameter is always called with `0` —
  it's dead-code at this level. Kept for symmetry / future use.
  [verified-by-code `pgcrypto.c:101,139,265,314,364,418`]
- Algorithm name passes through `downcase_truncate_identifier`
  (`parser/scansup.h`) — same path the SQL grammar uses for identifier
  case-folding. So `'AES-CBC'` and `'aes-cbc'` are equivalent inputs,
  consistent with PG identifier semantics.

## Crypto trust boundary / Phase D surface

- **`gen_random_bytes`** delegates to `pg_strong_random`
  (`pgcrypto.c:471`), the corpus-wide PRNG primitive (also used by
  the built-in `gen_random_uuid` and by `src/backend/libpq/auth-scram.c`
  for nonces). Strong by construction; no OpenSSL-specific drift.
  Length cap `1024` prevents huge allocations.
- **`gen_random_uuid`** is now an alias for the built-in
  `gen_random_uuid` from `src/backend/utils/adt/uuid.c:524` — v4
  (122 random bits). UUID v7 is NOT available via pgcrypto. Same
  collision properties as the core function (cross-reference A7
  uuid.c finding).
- **`pg_crypt(text, salt)`** dispatches by salt prefix in
  `px-crypt.c:88-99`. The empty-prefix and `_` cases run **DES**
  (traditional 13-char crypt and `_`-style 20-char extended DES). No
  warning is issued when a user calls `crypt(pw, 'aa')` — they get
  back a DES hash and proceed. [ISSUE-security: DES path still callable
  without deprecation warning (likely)]
- **`gen_salt('des', ...)`** and **`gen_salt('xdes', ...)`** still
  produce DES/XDES salt prefixes (`px-crypt.c:138,140`). No NOTICE/
  WARNING surfaced to the user when picking these.
  [ISSUE-security: DES salt-generators silently accepted (likely)]
- **`pg_encrypt(data, key, type)`** (no-IV) passes `NULL, 0` to
  `px_combo_init` at `pgcrypto.c:275`. In `px.c:combo_init`
  (`source/contrib/pgcrypto/px.c:181-216`), when the cipher's
  `iv_size > 0` and `ivlen == 0`, the code allocates `palloc0(ivs)`,
  i.e. **zero-IV**. For `aes-cbc` (16-byte IV), a zero IV means two
  encryptions of the same plaintext produce identical ciphertext —
  IV reuse leakage. [ISSUE-security: encrypt() without IV silently uses
  all-zero IV for CBC/CFB modes (confirmed)] — documented in pgcrypto
  docs but easy to miss.
- **`pg_encrypt_iv`** truncates a too-long user IV silently
  (`px.c:198-202` copies `min(ivlen, ivs)`). [ISSUE-api-shape: IV
  length mismatch silently truncated (maybe)]
- **No AEAD modes** — `openssl.c` ciphers are bf, des, des3, cast5,
  aes-ecb, aes-cbc, aes-cfb. No GCM, no CCM, no ChaCha20-Poly1305.
  Padding-oracle surface remains for CBC mode.
  [ISSUE-defense-in-depth: no AEAD modes in 2026 (likely)]
- **HMAC comparison**: pgcrypto returns the raw HMAC bytes and lets
  SQL do `tag = expected_tag`. The bytea `=` operator uses
  `memcmp`-style comparison (not constant-time). For HMAC verification
  in SQL, the user must implement their own constant-time comparison
  or accept the timing leak. [ISSUE-security: no constant-time
  comparison primitive exposed to SQL (likely)]
- **`pgcrypto.builtin_crypto_enabled` GUC** — defined here but only
  consulted by `px_crypt` and `px_gen_salt` (i.e. password-hash path).
  AES/HMAC/digest all run regardless. The GUC's docstring says
  "builtin crypto", which is misleading — what it gates is the
  vendored bcrypt/DES/MD5/SHA-crypt password hashing code, not the
  OpenSSL-wrapped primitives. [ISSUE-documentation: GUC name/scope
  ambiguity (maybe)]
- **Memory hygiene**: pgcrypto.c itself does **not** call
  `px_memset`/`explicit_bzero` on key or IV before returning — keys
  live in palloc'd VARDATA_ANY buffers that get `PG_FREE_IF_COPY`'d.
  Detoasted copies get freed (returned to the palloc context, not
  scrubbed). The wrapped algorithms (crypt-blowfish, crypt-sha,
  crypt-md5) do scrub their internal state; the OpenSSL EVP layer
  in openssl.c does not call `EVP_CIPHER_CTX_cleanup` before
  `EVP_CIPHER_CTX_free` — relies on OpenSSL's own cleanup. Compare
  with A5's secret-scrub cluster: pgcrypto is **less disciplined**
  than core (no `explicit_bzero` at the SQL-boundary).
  [ISSUE-security: bytea key never scrubbed after use (likely)]

## Cross-references

- `src/common/cryptohash_openssl.c` (A5) — the OpenSSL-backed digest
  implementation that pgcrypto bypasses in favor of its own EVP
  wrappers in `openssl.c`. Duplicate code paths.
- `src/common/sha2.c` (A5) — the standalone SHA-256/SHA-512 used by
  `src/backend/libpq/auth-scram.c`; pgcrypto uses OpenSSL EVP instead.
- `pg_strong_random` (cross-references uuid.c, libpq SCRAM nonces) —
  shared RNG, A7 finding.
- `src/backend/utils/adt/uuid.c:524` — `gen_random_uuid` that
  `pg_random_uuid` tail-calls.
- `src/backend/libpq/auth-scram.c` — uses `px_memcmp_*`-style discipline?
  No — also uses raw `memcmp` for SCRAM proof verification, with the
  same caveat. Cross-corpus finding.

## Issues spotted

- [ISSUE-security: DES path still callable without deprecation
  warning (likely)] — `pgcrypto.c:226-228 -> px-crypt.c:96-97`. Empty
  prefix falls through to `run_crypt_des`. DES has been weak since 1998.
- [ISSUE-security: `gen_salt('des'|'xdes')` accepted silently (likely)]
  — `px-crypt.c:138,140`. Same issue.
- [ISSUE-security: `pg_encrypt` with no-IV path uses all-zero IV for
  CBC/CFB (confirmed)] — `pgcrypto.c:275 -> px.c:197`. Documented in
  user docs but easy footgun.
- [ISSUE-security: HMAC output returned raw; SQL equality is not
  constant-time (likely)] — no helper exposed.
- [ISSUE-defense-in-depth: no AEAD ciphers (likely)] — openssl.c list
  has no GCM/CCM/Poly1305.
- [ISSUE-security: detoasted key bytea never scrubbed (likely)] —
  pgcrypto.c lacks `px_memset(VARDATA_ANY(key), 0, klen)` before
  `PG_FREE_IF_COPY`. A2/A4/A5/A6 secret-scrub cluster suggests this
  is a gap.
- [ISSUE-documentation: GUC name `builtin_crypto_enabled` ambiguous
  (maybe)] — only gates crypt(3)/gen_salt, NOT digest/hmac/encrypt.
- [ISSUE-api-shape: `find_provider`'s `silent` parameter is dead-code
  (nit)] — always `0`. Either remove or document why.
- [ISSUE-api-shape: IV length silently truncated (maybe)] —
  `pg_encrypt_iv` with longer IV than `iv_size` is silently clipped
  by `px.c:198-202`. Should probably ereport.
