# pgp-pubenc.c

## One-line summary

Encrypt a fresh random session key under a recipient's public key (RSA
or Elgamal) and emit it as an OpenPGP `PUBENCRYPTED_SESSKEY` packet (tag
1). Generates PKCS#1 v1.5 EME pad with `pg_strong_random` non-zero pad
bytes, prepends cipher_algo byte and appends 16-bit checksum.

## Public API / entry points

- `pgp_write_pubenc_sesskey(PGP_Context *, PushFilter *)` —
  `source/contrib/pgcrypto/pgp-pubenc.c:190` [verified-by-code]. Called
  by `pgp_encrypt` when `ctx->pub_key` is set.

## Key invariants

- Packet layout: `ver=3 (1B) || key_id (8B) || algo (1B) || MPI(c)` for
  RSA or `MPI(c1) || MPI(c2)` for Elgamal.
  `source/contrib/pgcrypto/pgp-pubenc.c:212-231` [verified-by-code].
- Padded msg layout (EME-PKCS1-v1.5): `0x02 || PS (non-zero pad) || 0x00
  || cipher_algo (1B) || sess_key || cksum (2B)`.
- Min pad length 8 bytes; enforced at
  `source/contrib/pgcrypto/pgp-pubenc.c:46-47`. If RSA modulus is too
  small to fit `klen+3` plus 11 bytes of overhead, returns `PXE_BUG`.
- Pad bytes are drawn from `pg_strong_random` and re-rolled until
  none are zero,
  `source/contrib/pgcrypto/pgp-pubenc.c:52-72` [verified-by-code].

## Notable internals

- **`pad_eme_pkcs1_v15`** — rejection-sampling loop for the non-zero
  pad. Worst-case bias is negligible since random bytes are uniform
  and zero is one of 256 outcomes — expected ~pad_len/255 re-rolls.
- **`create_secmsg`** — builds the cleartext to be RSA-encrypted:
  `cipher_algo || sess_key || cksum`. `klen = ctx->sess_key_len`.
  Both `secmsg` and `padded` are scrubbed with `px_memset` before
  pfree (`source/contrib/pgcrypto/pgp-pubenc.c:119-124`).
- **`full_bytes = pub.rsa.n->bytes - 1`** —
  `source/contrib/pgcrypto/pgp-pubenc.c:171`. The MPI is created with
  `full_bytes * 8 - 6` bits so the top bit pattern matches `0x02xx` (a
  6-bit leading-zero strip). This ensures `m < n` for RSA without
  losing entropy.
- **Cksum is the same 16-bit additive sum** as `pubdec`, no MAC.

## Crypto trust boundary / Phase D surface

- **PKCS#1 v1.5 vs OAEP.** Same critique as `pgp-pubdec.md`. Encrypt
  side just produces v1.5 padding; modern RFC 9580 uses OAEP. No
  pluggable padding mode.
  [ISSUE-defense-in-depth: encrypt-only-PKCS1-v1.5; no RSA-OAEP option
  (likely)] — `source/contrib/pgcrypto/pgp-pubenc.c:39-80`.
- **Random pad via `pg_strong_random`.** If RNG returns 0 entropy
  (e.g. /dev/urandom broken), function returns `PXE_NO_RANDOM`.
  Caller in `pgp_encrypt` propagates as ERROR.
- **Session-key cksum is also 16 bits** — for an Eve who can intercept
  ciphertexts, the cksum offers no integrity beyond what RSA itself
  provides. The decrypt side uses cksum match as a sanity check (was
  this really the right key?). Fine.
- **`secmsg` scrubbed before pfree.**
  `source/contrib/pgcrypto/pgp-pubenc.c:123-124`. Good. Session-key
  bytes briefly live there.
- **No `BN_set_flags(d, BN_FLG_CONSTTIME)` involved here** — we're
  encrypting with public exponent `e`, so timing leaks on `BN_mod_exp`
  reveal only public info. Encrypt side is fine.
- **Elgamal encrypt generates fresh `k` via OpenSSL `BN_rand`** — see
  `pgp-mpi-openssl.md` for the entropy concern.

## Cross-references

- `pgp-mpi-openssl.md` — `pgp_rsa_encrypt` / `pgp_elgamal_encrypt`.
- `pgp-pubkey.md` — `PGP_PubKey.pub.rsa.n.bytes` consumed here.
- `pgp-encrypt.md` — top-level `pgp_encrypt` calls
  `pgp_write_pubenc_sesskey` after `init_sess_key`.
- `pgp-pubdec.md` — the matching decrypt path.

## Issues spotted

- [ISSUE-defense-in-depth: only PKCS#1 v1.5 padding implemented; no
  OAEP fallback (likely)] —
  `source/contrib/pgcrypto/pgp-pubenc.c:39-80`.
- [ISSUE-defense-in-depth: encrypt-side cksum is 16-bit; offers
  zero-effort to compute, no MAC; relies entirely on RSA for
  integrity (nit)] —
  `source/contrib/pgcrypto/pgp-pubenc.c:93-104`. OpenPGP-spec
  behavior, not a pgcrypto-specific bug.
- [ISSUE-error-handling: if `pad_eme_pkcs1_v15` returns `PXE_NO_RANDOM`
  in the inner zero-rejection loop, `buf` is not pfree'd (`px_memset`
  IS called for the path at line 66, but not for the early
  `pg_strong_random` failure at line 52 — actually that path DOES pfree.
  Re-check.] — Re-read: line 52 returns `PXE_NO_RANDOM` with `pfree(buf)`
  at 54; line 64 returns with `px_memset+pfree`. Both paths OK. (nit, no
  issue)
