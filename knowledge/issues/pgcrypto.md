# Issues — `contrib/pgcrypto`

Per-subsystem issue register for **pgcrypto** — the cryptographic
toolkit shipped in contrib/. Combines the **core** (crypto
primitives, password hashing, symmetric encryption) and **PGP** (the
OpenPGP-compatible packet layer for `pgp_sym_*` / `pgp_pub_*`)
agendas into one register since they are the same module.

**Parent docs:** `knowledge/files/contrib/pgcrypto/*` (25 docs covering
28 source files: most .c/.h pairs combined into module docs per
A9/A10 precedent).

**Source:** ~126 entries (70 from A11-3 pgcrypto core + 56 from
A11-4 pgcrypto PGP) surfaced 2026-06-04 by the A11 foreground sweep.
Mirrored in each per-file doc's `## Issues spotted` block.

This is **THE highest-Phase-D-value module in contrib/** — cryptographic
correctness is unambiguous, the attack surface is concrete, and
the code is touched by virtually every PG installation that uses
column-level encryption or password hashing.

## Headlines

### Core / cipher-machinery headlines

1. **OpenSSL error stack is silently discarded throughout
   pgcrypto.** `<openssl/err.h>` included only for transitive
   needs; `ERR_get_error()` **never called**. Every EVP failure
   collapses to 3 PXE codes (`px.c:42-84`). Auditor blind to which
   OpenSSL primitive failed.

2. **Memory hygiene is inconsistent and weaker than core PG.** The
   corpus-wide secret-scrub cluster (A2/A4/A5/A6) leans on
   `explicit_bzero` (from `src/port`); pgcrypto instead uses
   `px_memset` — a plain `memset` wrapper whose only defense
   against elision is the TU boundary. **Under `-flto`,
   `px_memset` can be elided.** `OSSLCipher.key[MAX_KEY]` and
   `OSSLCipher.iv[MAX_IV]` (`openssl.c:258-259`) are `pfree`'d
   without scrub. The detoasted key bytea in `pgcrypto.c` is also
   never scrubbed before `PG_FREE_IF_COPY`. Notably, the **wrapped
   legacy algorithms (crypt-blowfish, crypt-sha, crypt-md5) DO
   scrub their stack state** — they are MORE disciplined than the
   SQL-boundary layer that surrounds them.

3. **Weak-by-default password hashing.** `crypt(pw, 'aa')` returns a
   traditional DES hash with no warning (`px-crypt.c:96-97 +
   crypt-des.c:650`); `gen_salt('bf')` defaults to cost=5 (~3 ms),
   well below OWASP 2023 minimum of 12; `gen_salt('md5')` produces
   `$1$` salts that map to crypt-md5's hardcoded 1000-round MD5
   (effectively useless in 2026); shacrypt accepts
   `rounds=999999999` which is a ~hour-long single-call CPU DoS
   even with `CHECK_FOR_INTERRUPTS`. The
   `pgcrypto.builtin_crypto_enabled` GUC only gates `crypt`/`gen_salt`
   (via `CheckBuiltinCryptoMode` called only in
   `px-crypt.c:106,162`), not `digest`/`hmac`/`encrypt`. Docstring
   is misleading.

4. **`encrypt(data, key, 'aes-cbc')` (no-IV form) silently uses an
   all-zero IV.** Confirmed by tracing `pgcrypto.c:275` (`NULL, 0`
   passed to `px_combo_init`) → `px.c:197` (`palloc0(ivs)`) →
   `openssl.c:472-473`. Two encryptions of the same plaintext
   produce identical ciphertext, leaking equality.

5. **No AEAD modes and no constant-time HMAC comparison primitive
   in 2026.** `openssl.c:757-770` lists `bf-*`, `des-*`, `des3-*`,
   `cast5-*`, `aes-{ecb,cbc,cfb}` — no GCM, no CCM, no
   ChaCha20-Poly1305. pgcrypto returns raw HMAC tag bytes and SQL
   `=` is byte-wise memcmp, not constant-time. **Auth-tag
   verification is timing-attackable.**

### PGP / public-key headlines

6. **🚨 CRITICAL: Decompression bomb in `pgp-compress.c`.**
   `pgp_sym_decrypt(small_compressed_blob, pw)` has NO output-size
   ceiling (`pgp-compress.c:278-310`). A 10 KB attacker ciphertext
   can decompress to multi-GB plaintext, OOMing the backend. Same
   class as A5's `pg_lzcompress` finding, but reachable via a
   **public SQL API with attacker-controlled bytea**. **Highest-
   severity issue in the entire A11 sweep.**

7. **EFAIL surface still reachable + S2K iter DoS.** pgcrypto
   continues to accept legacy `SYMENCRYPTED_DATA` (tag 9)
   ciphertexts without MDC at `pgp-decrypt.c:1141-1152`, relying
   solely on the delayed-error-reporting mitigation against the
   Mister-Zuccherato CFB attack. Combined with uncapped
   attacker-controlled **S2K iteration count** (`pgp-s2k.c:270` —
   RFC 4880 ceiling of ~65M, no SQL-level cap), a hostile message
   can force the maximum work per call. **Cumulative CPU DoS is
   straightforward.** `pgp_pub_decrypt` is worse: `keypkt` is also
   attacker-controlled (`pgp-pgsql.c:693-717`).

8. **Non-constant-time RSA / Elgamal secret-exponent ops** —
   `pgp-mpi-openssl.c:266,183` uses generic `BN_mod_exp` for
   `pgp_rsa_decrypt` and `pgp_elgamal_decrypt`, without setting
   `BN_FLG_CONSTTIME`. **Classic Brumley-Boneh 2003 timing-attack
   surface.** Fix is a one-line `BN_set_flags` call. Paired with
   the **PKCS#1 v1.5 padding short-circuit** (`pgp-pubdec.c:42-67`)
   which gives a Bleichenbacher-style oracle.

9. **`disable-mdc=1` produces no-MDC (EFAIL-vulnerable) ciphertext
   with no WARNING emitted** (`pgp-encrypt.c:462-465`). Combined
   with the legacy resync-CFB path remaining reachable on decrypt
   (`pgp-decrypt.c:1141-1152`), pgcrypto still offers an
   EFAIL-prone API. Modern AEAD (RFC 9580 SEIPDv2) unsupported.

10. **MDC uses SHA-1** (`pgp-decrypt.c:329`) — no modern HMAC-SHA-256
    alternative; `memcmp` on 20-byte SHA-1 is non-constant-time
    (`pgp-decrypt.c:383`).

11. **Compress-then-encrypt chain order enables CRIME-style
    attacks** when user opts in to compression with attacker-
    influenced plaintext (`pgp-encrypt.c:668-675`).

12. **Plaintext / passphrase / session-key memory not scrubbed.**
    `pgp_sym_decrypt` returns plaintext via palloc'd text/bytea;
    lives in PG memory contexts until reset, never `explicit_bzero`'d
    (`pgp-pgsql.c:443-448, 532`). Password/key bytea args pfree'd
    without `px_memset` wipe (`pgp-pgsql.c:568-571`). Stack tmpbufs
    holding ciphertext/hash scrubbed only on success path
    (`pgp-decrypt.c:250,628,689,348`).

### Other crypto-API surface findings

13. **No SQL-level constant-time HMAC compare helper exposed**
    (`px-hmac.c`) — pgcrypto returns raw tag bytes.

14. **DES/3DES/Blowfish/CAST5 still wired up** in modern
    pgcrypto's OpenSSL backend (`openssl.c:757-770`).

15. **MPI ceiling = 65 535 bits** allows ~8 KiB RSA moduli —
    pathologically slow `BN_mod_exp` per call (`pgp-mpi.c:42`).

16. **V5 OpenPGP keys (RFC 9580) categorically unsupported**
    (`pgp-pubkey.c:169-173`).

17. **Undocumented `debug=1` SQL option in PGP entry points leaks
    parser internals as NOTICEs** (`pgp-pgsql.c:200,365-366`) —
    potential error-oracle leak.

## Cross-sweep references

- **A5 `pg_lzcompress` decompression-bomb gap** is the same class
  as A11's PGP decompression bomb. Closed by a single Phase D pitch
  proposing `pg_lzcompress_with_cap` + adopting in pgcrypto + base
  backup decompression.
- **A2/A4/A5 secret-scrub cluster + A5 SecretBuf hosting site**:
  pgcrypto is the canonical USER of secret-scrub discipline and
  should be the model citizen. **Reality: pgcrypto's secret-scrub
  discipline is WEAKER than core PG.** Adopting `explicit_bzero`
  closes ~12 sites; SecretBuf would close another ~6 caller-owned
  surfaces.
- **A7 OpenSSL discipline (`hbafuncs.c::pg_hba_file_rules.options[]`
  RADIUS/LDAP secrets in plaintext)** is the parallel ACL leak
  surface; pgcrypto's `pgcrypto.builtin_crypto_enabled` is the
  parallel kill-switch GUC.
- **A11-3's `gen_random_uuid()` cross-check with A7 uuid.c**:
  pgcrypto core's `gen_random_bytes` / `gen_random_uuid` should be
  verified to use `pg_strong_random` (A7 finding).

## Entries — pgcrypto CORE (70 entries)

### pgcrypto.c / pgcrypto.h

- [ISSUE-security: DES path still callable without deprecation
  warning (likely)] — `source/contrib/pgcrypto/pgcrypto.c:226`
  (px_crypt entry) → `source/contrib/pgcrypto/px-crypt.c:96-97` —
  empty-prefix salt falls through to traditional DES; no
  NOTICE/WARNING.
- [ISSUE-security: pg_encrypt with no IV silently uses all-zero IV
  for CBC/CFB (confirmed)] —
  `source/contrib/pgcrypto/pgcrypto.c:275` passes `NULL, 0` to
  `px_combo_init`; `px.c:197` `palloc0`'s the IV. IV reuse breaks
  CBC.
- [ISSUE-security: HMAC returned raw; no constant-time-compare
  helper for SQL (likely)] —
  `source/contrib/pgcrypto/pgcrypto.c:122-161`. SQL `=` on bytea is
  byte-wise memcmp, timing leak.
- [ISSUE-defense-in-depth: no AEAD modes (likely)] — `pgcrypto.c`
  encrypt/decrypt SQL surface bound to non-AEAD ciphers only.
- [ISSUE-security: detoasted key/data bytea never scrubbed before
  PG_FREE_IF_COPY (likely)] — `pgcrypto.c:115-117, 156-158,
  281-283`. Compare A5/A2/A4 secret-scrub cluster.
- [ISSUE-documentation: GUC `pgcrypto.builtin_crypto_enabled` only
  gates `crypt`/`gen_salt`, not digest/hmac/encrypt (maybe)] —
  `pgcrypto.c:70-82`. Name suggests broader scope; reality is
  password-hash-only via `CheckBuiltinCryptoMode` calls only in
  `px-crypt.c:106,162`.
- [ISSUE-api-shape: `find_provider`'s `silent` parameter always 0
  (nit)] — `pgcrypto.c:101,139,265,...`. Dead-code parameter.
- [ISSUE-api-shape: IV silently truncated/zero-padded by combo_init
  (maybe)] — `px.c:198-202`.

### px.c / px.h

- [ISSUE-security: `px_memset` is plain memset wrapper; can be
  elided by LTO (likely)] —
  `source/contrib/pgcrypto/px.c:123-127`. Comment claims "must not
  be optimized away" but LTO sees the body. Should use
  `explicit_bzero` from `src/port`.
- [ISSUE-audit-gap: OpenSSL error stack discarded (confirmed)] —
  `source/contrib/pgcrypto/px.c:42-84`. `ERR_get_error()` never
  called. EVP failures collapse to 3 PXE codes.
- [ISSUE-security: silent IV truncation/zero-padding in combo_init
  (maybe)] — `source/contrib/pgcrypto/px.c:198-202`.
- [ISSUE-security: silent key truncation for fixed-key ciphers
  (maybe)] — `source/contrib/pgcrypto/px.c:204-205`. Bypassed for
  AES by `ossl_aes_init` selecting key class, but real for
  DES/3DES/CAST5.
- [ISSUE-api-shape: `px_debug` always compiled in, never enabled in
  prod (nit)] — `source/contrib/pgcrypto/px.h:38`, `px.c:149-163`.

### px-crypt.c / px-crypt.h

- [ISSUE-security: DES dispatch path accessible without warning
  (confirmed)] — `source/contrib/pgcrypto/px-crypt.c:96-97`.
- [ISSUE-security: bcrypt default cost = 6 (confirmed)] —
  `source/contrib/pgcrypto/px-crypt.h:46`. OWASP recommends 12+.
- [ISSUE-security: bcrypt min_rounds=4 (likely)] —
  `source/contrib/pgcrypto/px-crypt.c:141`. Cost 4 ≈ 1 ms, useless
  for password hashing.
- [ISSUE-security: gen_salt('md5'|'des'|'xdes') silently accepted
  (likely)] — `source/contrib/pgcrypto/px-crypt.c:138-140`.
- [ISSUE-security: shacrypt max_rounds = 999_999_999 → ~hour-long
  CPU DoS (maybe)] — `source/contrib/pgcrypto/px-crypt.h:70`.
- [ISSUE-audit-gap: rounds arg silently ignored for DES/MD5 (nit)]
  — `source/contrib/pgcrypto/px-crypt.c:171-178`.

### px-hmac.c

- [ISSUE-security: no constant-time HMAC compare helper exposed
  (likely)] — pgcrypto returns raw tag bytes.
- [ISSUE-defense-in-depth: duplicate of
  `src/common/hmac_openssl.c` (nit)] — corpus has two HMAC
  implementations.
- [ISSUE-security: px_memset LTO-elision risk applies (likely)] —
  `source/contrib/pgcrypto/px-hmac.c:77,119,131-132`.

### openssl.c

- [ISSUE-audit-gap: ERR_get_error never called (confirmed)] —
  `source/contrib/pgcrypto/openssl.c:36` (`<openssl/err.h>`
  included for transitive needs only). Auditor blind to which
  OpenSSL primitive failed.
- [ISSUE-security: OSSLCipher `key[MAX_KEY]` and `iv[MAX_IV]`
  pfree'd without scrub (likely)] —
  `source/contrib/pgcrypto/openssl.c:291-298`. Allocated in
  `TopMemoryContext`, so pfreed bytes may sit in the freelist with
  key material intact.
- [ISSUE-security: NULL IV → all-zero IV for CBC/CFB (confirmed)]
  — `source/contrib/pgcrypto/openssl.c:472-473, 491-492, 510-511,
  527-528, 553-555`.
- [ISSUE-defense-in-depth: no AEAD modes (GCM/CCM/Poly1305)
  (likely)] — `source/contrib/pgcrypto/openssl.c:757-770`.
- [ISSUE-defense-in-depth: DES/3DES/Blowfish/CAST5 still wired up
  (likely)] — `source/contrib/pgcrypto/openssl.c:757-770`.
- [ISSUE-documentation: uses legacy `EVP_aes_128_cbc()` etc;
  modern OpenSSL 3.0 prefers `EVP_CIPHER_fetch` (nit)] —
  migration target.

### mbuf.c / mbuf.h

- [ISSUE-security: plaintext-bearing MBuf scrubbed via px_memset
  only, LTO-elision risk (likely)] —
  `source/contrib/pgcrypto/mbuf.c:66,236,240,285,402,406`.
- [ISSUE-defense-in-depth: no max-size cap on MBuf growth (maybe)]
  — `source/contrib/pgcrypto/mbuf.c:73-91`. Malicious PGP input →
  unbounded `repalloc`.
- [ISSUE-api-shape: `mbuf_steal_data` does not document
  scrub-responsibility transfer (nit)] —
  `source/contrib/pgcrypto/mbuf.c:161`.

### crypt-blowfish.c

- [ISSUE-security: bcrypt cost=31 = ~3-minute per-call CPU
  (likely)] — `source/contrib/pgcrypto/crypt-blowfish.c:625`.
  `CHECK_FOR_INTERRUPTS()` at `:676` mitigates but does not
  prevent DoS surface.
- [ISSUE-security: `$2x$` (sign-extension-buggy) variant silently
  callable (maybe)] —
  `source/contrib/pgcrypto/crypt-blowfish.c:621,643`. Necessary
  for legacy verification but no warning.
- [ISSUE-defense-in-depth: stack scrub may be elided by LTO
  (likely)] — `source/contrib/pgcrypto/crypt-blowfish.c:757`.
  Solar Designer's own comment at `:752-755` is honest about this
  limit.
- Verified-present: 2011 sign-extension bug fix (`BF_set_key`
  accepts `sign_extension_bug` flag at `:550-552, 643`).
  [verified-by-code]

### crypt-des.c

- [ISSUE-security: DES is silent default for `crypt(pw, 'aa')`
  (confirmed)] — entry from `px-crypt.c:96-97`.
- [ISSUE-security: extended DES still dispatchable via `_` salt
  (likely)] — `source/contrib/pgcrypto/crypt-des.c:683`.
- [ISSUE-security: 8-char password truncation in traditional DES
  (likely)] — `source/contrib/pgcrypto/crypt-des.c:737-739`.
- [ISSUE-security: static `output[21]` buffer not scrubbed between
  calls (likely)] — `source/contrib/pgcrypto/crypt-des.c:662`.
- [ISSUE-security: stack-local `keybuf` not scrubbed (likely)] —
  `source/contrib/pgcrypto/crypt-des.c:659`. Compare crypt-blowfish.c's
  explicit scrub.

### crypt-md5.c

- [ISSUE-security: 1000-round hardcoded count makes MD5-crypt
  trivially crackable in 2026 (confirmed)] —
  `source/contrib/pgcrypto/crypt-md5.c:119`.
- [ISSUE-security: MD5 collision-broken since 2004 (confirmed)] —
  bad hygiene though not strictly load-bearing for password-hash
  usage.
- [ISSUE-security: pw cstring (palloc'd copy) not scrubbed before
  pfree in caller (likely)] —
  `source/contrib/pgcrypto/pgcrypto.c:230`.
- [ISSUE-defense-in-depth: no warning when `$1$` is used in 2026
  (likely)].

### crypt-sha.c

- [ISSUE-security: shacrypt max_rounds = ~1 B → hour-long CPU DoS
  (confirmed)] — `source/contrib/pgcrypto/px-crypt.h:70`, gated by
  `crypt-sha.c:209-217`. `CHECK_FOR_INTERRUPTS` at `:498`
  mitigates.
- [ISSUE-security: default rounds = 5000 too low for 2026 (likely)]
  — `source/contrib/pgcrypto/crypt-sha.c:96`.
- [ISSUE-security: min rounds = 1000 too low for 2026 (maybe)] —
  `source/contrib/pgcrypto/px-crypt.h:67`.
- [ISSUE-security: `p_bytes`/`s_bytes` (password-derived material)
  pfree'd without scrub (likely)] —
  `source/contrib/pgcrypto/crypt-sha.c:537-541`.
- [ISSUE-defense-in-depth: out_buf destroyed without scrub (maybe)]
  — `source/contrib/pgcrypto/crypt-sha.c:622`.
- [ISSUE-correctness: typo `PGCRYPTO_SHA_UNKOWN` (nit)] —
  `source/contrib/pgcrypto/crypt-sha.c:59,273,604`.

### crypt-gensalt.c

- [ISSUE-security: bcrypt default cost = 5 (confirmed)] —
  `source/contrib/pgcrypto/crypt-gensalt.c:175`. Way below OWASP
  2023 guidance (12+).
- [ISSUE-correctness: PX_BF_ROUNDS (6) vs hardcoded default 5
  inconsistency (nit)] —
  `source/contrib/pgcrypto/crypt-gensalt.c:175` vs
  `px-crypt.h:46`.
- [ISSUE-security: no deprecation warning for 'des'/'xdes'/'md5'
  gen_salt names (likely)].
- [ISSUE-security: caller can request bcrypt cost up to 31 via
  px_gen_salt (likely)] —
  `source/contrib/pgcrypto/px-crypt.c:141` `max_rounds=31`.
- [ISSUE-defense-in-depth: two distinct base64 alphabets
  (_crypt_itoa64 vs BF_itoa64) (nit)] —
  `source/contrib/pgcrypto/crypt-gensalt.c:21,122`.

## Entries — pgcrypto PGP (56 entries)

### pgp.c / pgp.h

- [ISSUE-defense-in-depth: legacy ciphers (3DES, CAST5, Blowfish)
  selectable by user-supplied algo string (maybe)] —
  `source/contrib/pgcrypto/pgp.c:80-83`.
- [ISSUE-defense-in-depth: SHA-1 and MD5 still permitted as
  `s2k-digest-algo` (maybe)] —
  `source/contrib/pgcrypto/pgp.c:68-72`.
- [ISSUE-audit-gap: `def_s2k_count = -1` falls through to
  65 536-262 144 range, 2009-era GPG default (maybe)] —
  `source/contrib/pgcrypto/pgp.c:43`.
- [ISSUE-api-shape: `pgp_set_symkey` stores non-owning pointer;
  lifetime bound to caller's palloc context (nit)] —
  `source/contrib/pgcrypto/pgp.c:357`.
- [ISSUE-documentation: `unsupported_compr` flag's purpose only
  obvious from cross-file reading (nit)] —
  `source/contrib/pgcrypto/pgp.h:158`.

### pgp-pgsql.c

- [ISSUE-security: `pgp_sym_decrypt`'s `data` bytea is fully
  attacker-controlled; reaches all bottom-level surfaces — S2K
  iter DoS, MDC bypass via tag 9, decompression bomb (likely)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:599-617`.
- [ISSUE-security: `pgp_pub_decrypt`'s `keypkt` is attacker-
  controlled bytea; secret-key S2K iter reaches ~65M (likely)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:693-717`.
- [ISSUE-defense-in-depth: undocumented `debug=1` option emits
  `ereport(NOTICE)` with internal parsing strings; potential
  error-oracle leak (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:200,365-366`.
- [ISSUE-defense-in-depth: password/key bytea args `pfree`'d
  without `px_memset` wipe; cleartext lingers (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:568-571`.
- [ISSUE-defense-in-depth: decrypted plaintext returned via
  palloc'd text/bytea; lives in PG memory contexts until reset;
  never `explicit_bzero`'d (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:443-448,532`.
- [ISSUE-audit-gap: no `ereport(LOG)` for repeated decryption
  failures; attacks invisible from server logs (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:599-740`.
- [ISSUE-correctness: `pgp_armor_headers` assumes UTF-8 input
  encoding; RFC 4880 does not mandate it (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:964-969`.
- [ISSUE-defense-in-depth: malformed UTF-8 in armor header yields
  per-row ERROR aborting SRF mid-iteration (nit)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:968-969`.

### pgp-armor.c

- [ISSUE-defense-in-depth: custom `pg_base64_*` duplicates
  `src/common/base64.c`; divergence risk (maybe)] —
  `source/contrib/pgcrypto/pgp-armor.c:38-175`.
- [ISSUE-error-handling: `elog(FATAL)` on internal length miscalc
  kills entire backend session (maybe)] —
  `source/contrib/pgcrypto/pgp-armor.c:227,370`.
- [ISSUE-audit-gap: no upper bound on `pgp_armor_decode` output
  length; only SQL bytea 1 GB cap applies (maybe)] —
  `source/contrib/pgcrypto/pgp-armor.c:366-368`.
- [ISSUE-correctness: `pgp_extract_armor_headers` returns pointers
  into internal heap buffer; dangling-pointer footgun (nit)] —
  `source/contrib/pgcrypto/pgp-armor.c:438-441`.
- [ISSUE-correctness: `pg_base64_decode` returns mixed sign
  convention (negative-error vs byte-count); callers must check
  sign (nit)] — `source/contrib/pgcrypto/pgp-armor.c:157-159`.

### pgp-cfb.c

- [ISSUE-security: legacy resync-CFB path remains reachable on
  decrypt via tag-9 packets; user gets EFAIL-vulnerable mode
  without warning (likely)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:1141-1152`.
- [ISSUE-defense-in-depth: `pgp_cfb_decrypt` does not validate
  `len`; harmless in practice (nit)] —
  `source/contrib/pgcrypto/pgp-cfb.c:260`.
- [ISSUE-correctness: `block_no` saturating semantics fuzzy across
  multiple messages, but each PGP packet uses a fresh CFB context
  (nit)] — `source/contrib/pgcrypto/pgp-cfb.c:131,226`.
- [ISSUE-documentation: "block #2 is 2 bytes long" comment lacks
  rationale (nit)] — `source/contrib/pgcrypto/pgp-cfb.c:130`.

### pgp-compress.c

- [ISSUE-security: 🚨 **CRITICAL** zlib decompression bomb; no
  output-size cap; small ciphertext → multi-GB plaintext → backend
  OOM] — `source/contrib/pgcrypto/pgp-compress.c:278-310`.
  **Headline finding.**
- [ISSUE-security: compress-then-encrypt enables CRIME-style
  attacks when user opts in to compression with attacker-
  influenced plaintext (likely)] —
  `source/contrib/pgcrypto/pgp-encrypt.c:669-675`.
- [ISSUE-correctness: bzip2 branch of `decompress_init` is dead
  code; dispatch rejects bzip2 before reaching it (nit)] —
  `source/contrib/pgcrypto/pgp-compress.c:210-212`.
- [ISSUE-memory: `dec->buf[ZIP_OUT_BUF]` holds plaintext briefly;
  only scrubbed at free (nit)] —
  `source/contrib/pgcrypto/pgp-compress.c:200,318`.
- [ISSUE-audit-gap: no telemetry when decompression ratio exceeds
  sane threshold; bombs invisible in logs (likely)] —
  `source/contrib/pgcrypto/pgp-compress.c:278-310`.

### pgp-decrypt.c

- [ISSUE-security: tag-9 legacy (no-MDC) ciphertexts still
  accepted; only mitigation is delayed-error reporting on
  prefix_init failure (likely)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:1141-1152`.
- [ISSUE-security: attacker-controlled S2K iter byte in
  `parse_symenc_sesskey`; ~65M digest ops per call; cumulative
  DoS (likely)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:642-647`.
- [ISSUE-security: 🚨 decompression bomb via inner COMPRESSED_DATA
  packet; no output-size cap (critical)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:834-843`.
- [ISSUE-defense-in-depth: MDC uses SHA-1; modern AEAD /
  HMAC-SHA-256 unavailable (maybe)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:329`.
- [ISSUE-audit-gap: no regression test asserts the delayed-error
  invariant; future patches could accidentally introduce a
  timing/error oracle (maybe)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:1180-1212`.
- [ISSUE-correctness: `mdc_finish` `memcmp` non-constant-time;
  20-byte timing leak (nit)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:383`.
- [ISSUE-correctness: `MAX_CHUNK=16 MiB` per chunk but no global
  ceiling on total decrypted-output size (maybe)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:49`.
- [ISSUE-error-handling: `decrypt_key` ignores `pgp_cfb_decrypt`
  return values (nit)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:602-606`.
- [ISSUE-memory: stack `tmpbuf` holds ciphertext/hash briefly;
  `px_memset` only on success path (nit)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:250,628,689,348`.
- [ISSUE-documentation: `disable_mdc=1` silently set on tag-9
  packet; no LOG/NOTICE that user is on EFAIL-prone path (maybe)]
  — `source/contrib/pgcrypto/pgp-decrypt.c:1149`.

### pgp-encrypt.c

- [ISSUE-defense-in-depth: `disable-mdc=1` SQL option produces
  no-MDC ciphertext (EFAIL-vulnerable); no WARNING emitted
  (likely)] — `source/contrib/pgcrypto/pgp-encrypt.c:462-465`.
- [ISSUE-defense-in-depth: compress-then-encrypt chain order;
  CRIME-style attack surface when user opts in to compression
  (likely)] — `source/contrib/pgcrypto/pgp-encrypt.c:668-675`.
- [ISSUE-memory: `EncStat.buf` not scrubbed between chunks (nit)]
  — `source/contrib/pgcrypto/pgp-encrypt.c:153-154,213-221`.
- [ISSUE-memory: `pkt[256]` stack buffer holds session-key+algo
  briefly; compiler could DCE the `px_memset` (nit)] —
  `source/contrib/pgcrypto/pgp-encrypt.c:523,554`.

### pgp-info.c

- [ISSUE-defense-in-depth: exposes only 64-bit long key ID, not
  full v4 fingerprint; collision-resistance ~2^32 (maybe)] —
  `source/contrib/pgcrypto/pgp-info.c:217-223`.
- [ISSUE-correctness: defensive double-`pkt = NULL` + outer-loop
  re-check pattern suggests history of bugs (nit)] —
  `source/contrib/pgcrypto/pgp-info.c:185-194`.
- [ISSUE-audit-gap: no warning if input is partial (EOF before
  encrypted-data packet); silently returns parsed key_id (nit)] —
  `source/contrib/pgcrypto/pgp-info.c:213-231`.

### pgp-mpi-openssl.c

- [ISSUE-security: secret-exponent `BN_mod_exp` calls do not set
  `BN_FLG_CONSTTIME`; Brumley-Boneh timing attack surface in
  `pgp_rsa_decrypt` and `pgp_elgamal_decrypt` (likely)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:266,183`. **Headline
  finding.**
- [ISSUE-security: no maximum RSA modulus / Elgamal `p` size; CPU
  DoS via giant pubkey on encrypt (likely)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:215,101`.
- [ISSUE-defense-in-depth: RSA decrypt skips CRT (p,q,u unused);
  2-3× slowdown (maybe)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:251-284`.
- [ISSUE-defense-in-depth: `decide_k_bits` is heuristic, not
  matched to subgroup order Q (maybe)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:91-98`.
- [ISSUE-error-handling: OpenSSL `BN_*` failures mapped to generic
  `PXE_PGP_MATH_FAILED`; no OOM-vs-arithmetic distinction (nit)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:104,167,217,253`.

### pgp-mpi.c

- [ISSUE-defense-in-depth: 65 535-bit MPI ceiling allows ~8 KiB
  RSA moduli; pathologically slow; cap could be 8 192 (likely)] —
  `source/contrib/pgcrypto/pgp-mpi.c:42`.
- [ISSUE-correctness: `pgp_mpi_read` partial-failure path doesn't
  NULL `*mpi`; callers must check `res<0` (nit)] —
  `source/contrib/pgcrypto/pgp-mpi.c:96-100`.
- [ISSUE-defense-in-depth: `pgp_mpi_cksum` non-constant-time over
  16-bit accumulator; minor due to small entropy (nit)] —
  `source/contrib/pgcrypto/pgp-mpi.c:132-142`.

### pgp-pubdec.c

- [ISSUE-security: PKCS#1 v1.5 EME padding check short-circuits;
  Bleichenbacher-style timing oracle (likely)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:42-67`.
- [ISSUE-security: cksum check runs only if pad succeeds; timing
  distinguishes "bad pad" from "good pad, wrong key" (likely)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:211-220`.
- [ISSUE-error-handling: decrypted `cipher_algo` byte not
  validated before `memcpy` (nit)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:235`.
- [ISSUE-defense-in-depth: only RSA-PKCS1-v1.5 implemented; no
  OAEP / ECDH (likely)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:200-204`.
- [ISSUE-correctness: `any_key` (all-zero key ID) accepted as
  wildcard; fingerprinting surface, minor (nit)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:182-187`.

### pgp-pubenc.c

- [ISSUE-defense-in-depth: only PKCS#1 v1.5 padding implemented;
  no OAEP fallback (likely)] —
  `source/contrib/pgcrypto/pgp-pubenc.c:39-80`.
- [ISSUE-defense-in-depth: encrypt-side cksum is 16-bit; offers no
  MAC; relies on RSA for integrity (nit)] —
  `source/contrib/pgcrypto/pgp-pubenc.c:93-104`.

### pgp-pubkey.c

- [ISSUE-security: secret-key packet S2K iter is uncapped;
  attacker controls `keypkt` arg; ~65M iter DoS per call (likely)]
  — `source/contrib/pgcrypto/pgp-pubkey.c:365-370`.
- [ISSUE-memory: early-return at line 391 leaks `cfb` if
  `pullf_create` fails after `pgp_cfb_create` succeeded (maybe)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:386-391`.
- [ISSUE-correctness: `memcmp` on 20-byte SHA-1 in
  `check_key_sha1` is non-constant-time; theoretical leak (nit)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:287`.
- [ISSUE-defense-in-depth: V3 keys rejected; V5 (RFC 9580) also
  rejected; pgcrypto stuck on V4 (likely)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:169-173`.
- [ISSUE-correctness: `iv[512]` stack buffer; ≤32 bytes used; 480
  bytes wasted but no overflow (nit)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:344`.
- [ISSUE-error-handling: `process_secret_key` returns on error
  without zeroing partial S2K key material on stack (maybe)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:367,371`.

### pgp-s2k.c

- [ISSUE-security: attacker-controlled S2K iter byte on decrypt
  path; ~65M digest ops; cumulative DoS via repeated
  `pgp_sym_decrypt` (likely)] —
  `source/contrib/pgcrypto/pgp-s2k.c:270`. **Headline finding.**
- [ISSUE-defense-in-depth: default iter window 65 536-262 144
  below NIST SP 800-132 / OWASP 2026 recommendations (likely)] —
  `source/contrib/pgcrypto/pgp-s2k.c:213-214`.
- [ISSUE-defense-in-depth: SHA-1 is the default `s2k_digest_algo`
  (nit)] — `source/contrib/pgcrypto/pgp.c:44`.
