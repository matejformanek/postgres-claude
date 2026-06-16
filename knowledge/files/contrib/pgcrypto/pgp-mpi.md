# pgp-mpi.c

## One-line summary

Multi-precision-integer (MPI) helper functions shared by the OpenSSL
backend: alloc/free, big-endian byte-buffer ↔ bit-counted MPI conversion,
read/write through Push/PullFilter, hash-update with bit-prefix, and the
2-byte rolling checksum.

## Public API / entry points

- `pgp_mpi_alloc(bits, &mpi)` —
  `source/contrib/pgcrypto/pgp-mpi.c:37` [verified-by-code]. Validates
  `0 <= bits <= 0xFFFF`. Single palloc holds struct + data inline.
- `pgp_mpi_create(uint8 *data, bits, &mpi)` —
  `source/contrib/pgcrypto/pgp-mpi.c:56`. Like alloc then memcpy.
- `pgp_mpi_free(mpi)` — `px_memset(0)` then `pfree`,
  `source/contrib/pgcrypto/pgp-mpi.c:70` [verified-by-code]. Scrubs the
  MPI bytes — important since these may be RSA private key components.
- `pgp_mpi_read(PullFilter *, &mpi)` — read 2-byte big-endian bit count,
  then `(bits+7)/8` bytes; `source/contrib/pgcrypto/pgp-mpi.c:80`.
- `pgp_mpi_write(PushFilter *, n)` — opposite,
  `source/contrib/pgcrypto/pgp-mpi.c:105`.
- `pgp_mpi_hash(md, n)` — feed bit prefix + bytes into a digest for
  fingerprint computation,
  `source/contrib/pgcrypto/pgp-mpi.c:119`.
- `pgp_mpi_cksum(cksum, n)` — RFC-4880 secret-key 16-bit additive
  checksum, `source/contrib/pgcrypto/pgp-mpi.c:132`.

## Key invariants

- `bits` is the leading bit count (so `bits=2049` → `bytes=257`). MPI is
  stored big-endian.
- Bounds check `bits < 0 || bits > 0xFFFF` rejects > 8 192 bytes
  (`source/contrib/pgcrypto/pgp-mpi.c:42-46`) [verified-by-code]. 65 535
  bits = 8 191 bytes ≈ 8 KiB → caps RSA modulus at 65 535 bits.
- Struct layout: `palloc(sizeof(*n) + len)` then point `data` past struct
  header (`source/contrib/pgcrypto/pgp-mpi.c:47-50`). One allocation.
- Read flow: 2 bytes bits, then `n->bytes = (bits+7)/8` bytes via
  `pullf_read_fixed`. On read failure, the partially-populated MPI is
  freed (`source/contrib/pgcrypto/pgp-mpi.c:97-100`).

## Notable internals

- `pgp_mpi_cksum` is the additive 16-bit rolling checksum used by
  V3-style secret-key packets and by `pgp-pubdec.c` to validate
  PKCS#1-v1.5-padded session-key payloads (cf. `control_cksum` in
  `pgp-pubdec.c:74`).
- The `data` field is a flexible-array-tail via pointer arithmetic
  (palloc with extra room, point `data` at the tail) rather than
  C99 `data[]`. Style choice predates wider C99 adoption.

## Crypto trust boundary / Phase D surface

- **`bits <= 0xFFFF` cap** = up to **65 535 bits ≈ 8 KiB** for any MPI.
  That's well above RSA-4096 (current practical max) and elgamal-4096.
  `source/contrib/pgcrypto/pgp-mpi.c:42-46`. But still — an attacker
  presenting a public key with 65 535-bit modulus would make every RSA
  operation O(n²) ≈ 4 GB-ops, which is *deliberately* slow per key but
  potentially DoS over many decryption requests.
  [ISSUE-defense-in-depth: 65 535-bit MPI ceiling allows ~8 KiB RSA
  moduli; pathologically slow but functional; could be capped at 8 192
  bits for RSA/Elgamal (likely)] —
  `source/contrib/pgcrypto/pgp-mpi.c:42`.
- **`pgp_mpi_free` does `px_memset` then `pfree`** —
  `source/contrib/pgcrypto/pgp-mpi.c:74`. Important because secret-key
  MPIs (RSA `d`, `p`, `q`, `u`; Elgamal `x`; DSA `x`) live in
  `PGP_PubKey.sec`. Good practice.
- **No constant-time discipline.** `pgp_mpi_cksum` does plain additive
  loop over secret bytes. The cksum compare in `check_key_cksum` in
  `pgp-pubkey.c:328-332` is a plain `!=` — non-constant-time. For
  attacker-controlled ciphertexts feeding `decrypt_rsa` →
  `control_cksum` (`pgp-pubdec.c:74-94`), the same applies. Cksum is a
  16-bit value, so brute force online would need ~32k decryption
  attempts — not realistic but the principle stands.
  [ISSUE-defense-in-depth: cksum comparisons are non-constant-time;
  16-bit search-space is small enough that timing leak doesn't matter
  in practice (nit)] — `source/contrib/pgcrypto/pgp-pubdec.c:88-92`
  and `pgp-pubkey.c:328-332`.

## Cross-references

- `pgp-mpi-openssl.md` — the actual arithmetic (BIGNUM round-trip).
- `pgp-pubkey.md` — `pgp_mpi_read` consumes RSA/Elgamal/DSA components.
- `pgp-pubdec.md` / `pgp-pubenc.md` — MPI is the wire format for
  session-key encryption payloads.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-defense-in-depth: 65 535-bit MPI ceiling; cap at 8 192 (or
  configurable) to limit DoS surface from giant keys (likely)] —
  `source/contrib/pgcrypto/pgp-mpi.c:42`.
- [ISSUE-correctness: `pgp_mpi_free(NULL)` returns 0 — OK,
  defensive. `pgp_mpi_read` partial-failure path frees the MPI (good),
  but doesn't set `*mpi = NULL` so caller might double-free; verify
  callers always check `res < 0` before reuse (nit)] —
  `source/contrib/pgcrypto/pgp-mpi.c:96-100`. Inspecting callers
  (`pgp-pubkey.c:_pgp_read_public_key`), they do check.
- [ISSUE-defense-in-depth: `pgp_mpi_cksum` non-constant-time loop over
  16-bit accumulator; minor since checksum entropy is only 16 bits
  (nit)] — `source/contrib/pgcrypto/pgp-mpi.c:132-142`.
