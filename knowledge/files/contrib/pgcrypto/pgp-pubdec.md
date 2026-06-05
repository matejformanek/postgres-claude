# pgp-pubdec.c

## One-line summary

Decrypt a public-key-encrypted session-key packet (PGP packet tag 1):
parse version + key-ID + algorithm, decode the RSA or Elgamal ciphertext
MPIs via `pgp_rsa_decrypt` / `pgp_elgamal_decrypt`, strip PKCS#1 v1.5
EME padding, verify the 16-bit additive checksum, and install the
session key into the `PGP_Context`.

## Public API / entry points

- `pgp_parse_pubenc_sesskey(PGP_Context *, PullFilter *)` —
  `source/contrib/pgcrypto/pgp-pubdec.c:150` [verified-by-code]. Called
  by `pgp_decrypt` for tag 1 packets.

## Key invariants

- Only **version 3** pubenc packets are accepted; otherwise
  `PXE_PGP_CORRUPT_DATA`,
  `source/contrib/pgcrypto/pgp-pubdec.c:170-174` [verified-by-code].
- Key-ID check: 8-byte ID must match `pk->key_id` exactly, OR be all
  zeros (the OpenPGP "any key" wildcard),
  `source/contrib/pgcrypto/pgp-pubdec.c:182-187` [verified-by-code].
  Mismatch → `PXE_PGP_WRONG_KEY`.
- Supported algos: `PGP_PUB_ELG_ENCRYPT` (16), `PGP_PUB_RSA_ENCRYPT`
  (2), `PGP_PUB_RSA_ENCRYPT_SIGN` (1),
  `source/contrib/pgcrypto/pgp-pubdec.c:194-204`.
- After decrypt, message format = `cipher_algo (1B) || sess_key (klen)
  || cksum (2B big-endian)`. Total `msglen` ≥ 3.
- Session-key length capped at `PGP_MAX_KEY = 32`,
  `source/contrib/pgcrypto/pgp-pubdec.c:225-230`.
- `pgp_expect_packet_end(pkt)` confirms no trailing data.

## Notable internals

- `check_eme_pkcs1_v15(data, len)` — `source/contrib/pgcrypto/pgp-pubdec.c:42`.
  Validates:
  1. `len >= 10` (1 byte type + 8 byte min pad + 1 byte zero terminator).
  2. First byte is `0x02`.
  3. ≥ 8 non-zero pad bytes follow.
  4. Zero terminator (`0x00`) found before EOD.

  Returns pointer past the terminator on success, NULL on any fail.
- `control_cksum(msg, msglen)` — sums `msg[1 .. msglen-3]`, compares to
  trailing 2-byte big-endian cksum,
  `source/contrib/pgcrypto/pgp-pubdec.c:74-94` [verified-by-code]. Both
  pad-fail and cksum-fail map to `PXE_PGP_WRONG_KEY` (good — same
  error code), but different code paths (timing leak survives).

## Crypto trust boundary / Phase D surface

- **Bleichenbacher / Manger-class padding-oracle.** PKCS#1 v1.5 EME
  decryption is the textbook source of Bleichenbacher 1998. Pgcrypto:
  - Pad failure → `PXE_PGP_WRONG_KEY` (line 215).
  - Cksum failure → `PXE_PGP_WRONG_KEY` (line 91).
  Same error code, good. **But:** cksum runs only if pad succeeds, so
  the timing differs measurably. Plus `check_eme_pkcs1_v15` early-outs
  on the first failing condition (lines 49, 51, 60, 62, 64), giving
  multiple distinguishable timings.
  [ISSUE-security: PKCS#1 v1.5 padding check is not constant-time and
  short-circuits on first failure; Bleichenbacher oracle in
  `pgp_pub_decrypt` if attacker can time SQL calls (likely)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:42-67`. Modern OpenPGP (RFC
  9580) deprecates RSA-PKCS1-v1.5 in favor of OAEP / ECDH, but
  pgcrypto only implements v1.5.
- **`memcpy(ctx->sess_key, msg + 1, sess_key_len)`** lands the decoded
  session key in the context.
  `source/contrib/pgcrypto/pgp-pubdec.c:237` [verified-by-code]. No
  explicit_bzero on `m->data` after — relies on `pgp_mpi_free(m)`
  zeroing.
- **`PXE_PGP_KEY_TOO_BIG`** if session-key length > 32 (`PGP_MAX_KEY`),
  `source/contrib/pgcrypto/pgp-pubdec.c:225-230`. Good bound check.
- **No validation that `cipher_algo` byte (decrypted first byte) is a
  valid algorithm.** It's stored into `ctx->cipher_algo` unchecked
  (line 235). Later `pgp_load_cipher` will fail on unknown — but the
  error message will be misleading.
  [ISSUE-error-handling: decrypted `cipher_algo` byte not validated
  before `memcpy`; invalid algo surfaces later with confusing message
  (nit)] — `source/contrib/pgcrypto/pgp-pubdec.c:235`.
- **`any_key` (all-zero key ID) accepted** — RFC 4880 §5.1 says all-zero
  key ID means "try all available keys", but pgcrypto has only one key
  per `PGP_Context`, so we just try that one. Functional but a
  malicious sender could use ANYKEY to fingerprint which key the
  recipient has (by trying decryption and timing the result). Very
  minor.
- **Memory hygiene.** `pgp_mpi_free(m)` at the cleanup `out:` label
  scrubs the decrypted padded message. Session key in `ctx->sess_key`
  scrubbed by `pgp_free` at the end of the SQL call.

## Cross-references

- `pgp-mpi-openssl.md` — `pgp_rsa_decrypt`, `pgp_elgamal_decrypt`.
- `pgp-pubkey.md` — supplies `ctx->pub_key` with the secret-key
  material.
- `pgp-decrypt.md` — dispatcher that calls
  `pgp_parse_pubenc_sesskey` for tag-1 packets.
- Bleichenbacher 1998, "Chosen ciphertext attacks against protocols
  based on the RSA encryption standard PKCS #1".

## Issues spotted

- [ISSUE-security: PKCS#1 v1.5 EME padding check short-circuits;
  Bleichenbacher-style timing oracle possible (likely)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:42-67`.
- [ISSUE-security: cksum check runs only if pad succeeds; timing
  distinguishes "bad pad" from "good pad, wrong key" (likely)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:211-220`.
- [ISSUE-error-handling: decrypted cipher_algo byte (line 235) is
  installed into ctx without validation; later loadcipher fail emits
  confusing error (nit)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:235`.
- [ISSUE-defense-in-depth: pgcrypto supports only RSA-PKCS1-v1.5 / no
  RSA-OAEP / no ECDH; modern OpenPGP (RFC 9580) deprecates v1.5
  (likely)] — `source/contrib/pgcrypto/pgp-pubdec.c:200-204`.
- [ISSUE-correctness: `any_key` (all-zero key ID) accepted as wildcard;
  fingerprinting surface but very minor (nit)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:182-187`.
