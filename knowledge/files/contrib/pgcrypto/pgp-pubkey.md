# pgp-pubkey.c

## One-line summary

Parse OpenPGP V4 public-key and secret-key packets — read MPIs for RSA /
Elgamal / DSA, compute the SHA-1 key fingerprint (last 8 bytes = key
ID), and for secret keys handle the S2K-encrypted secret-component
section with CFB decryption + SHA-1 or 16-bit checksum integrity check.

## Public API / entry points

- `pgp_key_alloc(&pk)` — palloc0,
  `source/contrib/pgcrypto/pgp-pubkey.c:38` [verified-by-code].
- `pgp_key_free(pk)` — frees per-algo MPI components then
  `px_memset+pfree`,
  `source/contrib/pgcrypto/pgp-pubkey.c:48` [verified-by-code].
- `_pgp_read_public_key(PullFilter *, &pk)` — parse just the public
  half of a key packet, compute key ID,
  `source/contrib/pgcrypto/pgp-pubkey.c:158`.
- `pgp_set_pubkey(PGP_Context *, MBuf *, key, key_len, pubtype)` —
  entry from `pgp-pgsql.c`; iterates packets, picks the encryption
  subkey, handles secret-key decryption with passphrase,
  `source/contrib/pgcrypto/pgp-pubkey.c:565` [verified-by-code].
- `pubtype` arg: `0` = public-key (encrypt side), `1` = secret-key
  (decrypt side).

## Key invariants

- Only **V4 keys** accepted; `pk->ver != 4` →
  `PXE_PGP_NOT_V4_KEYPKT`,
  `source/contrib/pgcrypto/pgp-pubkey.c:169-173`. V3 (deprecated) and
  V5 (new) are rejected.
- Key ID = last 8 bytes of SHA-1 over `0x99 || len(2B) || ver ||
  time(4B) || algo || MPI_components`,
  `source/contrib/pgcrypto/pgp-pubkey.c:118-151` [verified-by-code]. RFC
  4880 §12.2.
- For encryption keys (`PGP_PUB_RSA_ENCRYPT`, `_ENCRYPT_SIGN`,
  `PGP_PUB_ELG_ENCRYPT`), `pk->can_encrypt = 1`,
  `source/contrib/pgcrypto/pgp-pubkey.c:215,231`.
- Three secret-key encryption modes — `HIDE_CLEAR=0` (no passphrase),
  `HIDE_CKSUM=255` (legacy 16-bit cksum), `HIDE_SHA1=254` (modern SHA-1
  MIC). `source/contrib/pgcrypto/pgp-pubkey.c:248-250,360`.
- Secret key requires passphrase (`key != NULL`) if encrypted,
  otherwise `PXE_PGP_NEED_SECRET_PSW`,
  `source/contrib/pgcrypto/pgp-pubkey.c:362-363`.
- Only one main key + one encryption subkey allowed
  (`PXE_PGP_MULTIPLE_KEYS`, `PXE_PGP_MULTIPLE_SUBKEYS`),
  `source/contrib/pgcrypto/pgp-pubkey.c:489,535`.

## Notable internals

- **`calc_key_id`** computes the V4 fingerprint. SHA-1 of an
  explicitly framed key packet, last 8 bytes become `pk->key_id`. SHA-1
  is mandatory per RFC 4880 — pgcrypto cannot use SHA-256 for v4 IDs
  without breaking compatibility.
- **`process_secret_key`** is the heavy logic:
  1. Read public half (`_pgp_read_public_key`).
  2. Read 1-byte `hide_type`.
  3. If encrypted: read cipher_algo, S2K spec, IV; derive key via
     `pgp_s2k_process`; build a CFB pull filter `pgp_decrypt_filter`
     chained over the packet reader.
  4. Read encrypted MPIs through the decrypt filter.
  5. Verify SHA-1 (modern) or 16-bit cksum (legacy) of all secret
     components.
- **CFB resync flag = 0** for secret-key decryption
  (`source/contrib/pgcrypto/pgp-pubkey.c:386`) — uses "normal" CFB
  mode.
- `internal_read_key` scans top-level packets. First main key is
  always skipped (signing key, not what we want); we want the
  encryption subkey. Multiple subkeys → error.
- `iv[512]` is oversized for any block cipher (max 32 bytes for AES).
  Stack waste but harmless.

## Crypto trust boundary / Phase D surface

- **Passphrase is forwarded to `pgp_s2k_process` verbatim** — so the
  S2K iter-count surface (`pgp-s2k.md`) applies here too. An attacker
  providing a secret-key packet with iter=255 forces ~65 M digest
  ops per `pgp_pub_decrypt`. With `pubtype=1` and attacker control of
  `key` (the keypkt), this is **directly reachable via SQL**.
  [ISSUE-security: secret-key packet S2K iter is uncapped; attacker
  controls the keypkt argument to `pgp_pub_decrypt(data, KEYPKT,
  password)`; force ~65 M S2K iters (likely)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:365-370` and
  `pgp-s2k.c:270`.
- **`check_key_sha1` vs `check_key_cksum` — non-constant-time
  `memcmp`.** `check_key_sha1` uses `memcmp` over 20 bytes; cksum check
  is `!=`. For attacker-controlled secret-key payloads with bad
  passphrase, the SHA-1 check is the security-relevant gate. memcmp
  IS non-constant-time, but the cost of a timing attack to recover
  the passphrase via SHA-1 comparison is roughly equivalent to
  brute-forcing the passphrase directly — not exploitable in practice.
- **Secret-key MPIs (`d`, `p`, `q`, `u`, `x`) zeroed on `pgp_key_free`**
  via `pgp_mpi_free(...)`. Good. But the temporary CFB-decrypted
  buffer in `pgp_decrypt_filter` is not explicitly scrubbed between
  reads — relies on pfree of the filter chain.
- **`PGP_PUB_RSA_SIGN`** keys also enter `process_secret_key` (line
  407). `can_encrypt` stays 0 for sign-only, so they're rejected by
  the dispatcher (`internal_read_key` line 527 checks
  `pk->can_encrypt`). Fine.
- **`HIDE_CLEAR` = unencrypted private key.** If a user uploads an
  unencrypted secret-key blob to `pgp_pub_decrypt`, no passphrase is
  needed, and the secret key lives in PG memory for the duration of
  the call. After `pgp_free`, the `PGP_PubKey` is `px_memset`'d. Good
  hygiene.
- **`process_secret_key` returns before freeing `pf_decrypt` / `cfb`
  on early-return paths.** Check line 367 (returns res after
  `pgp_s2k_read`), line 371 (returns after `pgp_s2k_process`), line
  381 (returns after `pullf_read_fixed`). At these points `cfb=NULL`,
  `pf_decrypt=NULL`, so no leak. Lines 388, 391: returns after
  `pgp_cfb_create` and `pullf_create` — at line 391, `cfb` is created
  but the function returns without freeing. The pull-filter chain
  takes ownership of `cfb` only after `pullf_create` succeeds.
  [ISSUE-memory: `process_secret_key` returns at line 391 without
  freeing `cfb` if `pullf_create` fails (maybe)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:386-391`. `pgp_cfb_create`
  succeeded; `pullf_create` failed; `cfb` leaks until MemoryContext
  reset.

## Cross-references

- `pgp-s2k.md` — secret-key passphrase KDF.
- `pgp-cfb.md` — secret-key MPI decryption uses `pgp_cfb_decrypt` with
  resync=0.
- `pgp-mpi.md` — `pgp_mpi_read` for each component.
- `pgp-pubdec.md` / `pgp-pubenc.md` — uses parsed key for RSA / Elgamal.
- `pgp-info.md` — sibling that parses keys WITHOUT decryption.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: secret-key packet S2K iter is uncapped; attacker
  controls `keypkt` arg to `pgp_pub_decrypt`; ~65M iter DoS per call
  (likely)] — `source/contrib/pgcrypto/pgp-pubkey.c:365-370`.
- [ISSUE-memory: early-return at line 391 leaks `cfb` if
  `pullf_create` fails after `pgp_cfb_create` (maybe)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:386-391`.
- [ISSUE-correctness: `memcmp` on 20-byte SHA-1 in `check_key_sha1` is
  non-constant-time; timing leak to distinguish "right pw, wrong key"
  from "wrong pw" — theoretical (nit)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:287`.
- [ISSUE-defense-in-depth: V3 keys rejected; V5 (RFC 9580) keys also
  rejected; pgcrypto stuck on V4 (likely)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:169-173`. V5 keys with
  SHA-256 fingerprints not supported.
- [ISSUE-correctness: `iv[512]` stack buffer; any block cipher uses
  ≤32 bytes; 480 bytes wasted but no overflow risk (nit)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:344`.
- [ISSUE-error-handling: `process_secret_key` returns `PXE_PGP_*`
  without zeroing partial S2K key material on error (maybe)] —
  `source/contrib/pgcrypto/pgp-pubkey.c:367,371`. `s2k.key`
  populated by `pgp_s2k_process` could survive on stack if not
  scrubbed before return. Stack scrub depends on subsequent
  function-call overwriting. Minor in practice.
