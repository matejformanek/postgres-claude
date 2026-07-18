# pgp-mpi-openssl.c

## One-line summary

OpenSSL BIGNUM-backed implementation of the four big-int operations needed
by OpenPGP public-key crypto: RSA encrypt/decrypt (modular exponentiation)
and Elgamal encrypt/decrypt. Marshals `PGP_MPI` ↔ `BIGNUM` via
`BN_bin2bn`/`BN_bn2bin`, then drives `BN_mod_exp` / `BN_mod_mul`.

## Public API / entry points

- `pgp_rsa_encrypt(pk, m, &c)` — `c = m^e mod n`,
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:215` [verified-by-code].
- `pgp_rsa_decrypt(pk, c, &m)` — `m = c^d mod n`,
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:251` [verified-by-code].
  **NB**: does NOT use CRT (no use of `p`, `q`, `u`), so 2-3× slower than
  optimal.
- `pgp_elgamal_encrypt(pk, m, &c1, &c2)` — `c1 = g^k; c2 = m * y^k`,
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:101`.
- `pgp_elgamal_decrypt(pk, c1, c2, &m)` — `m = c2 / c1^x mod p`,
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:164`.

## Key invariants

- `mpi_to_bn(n)` verifies that `BN_num_bits(bn) == n->bits` after
  conversion — round-trip self-check.
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:45-51` [verified-by-code].
  Catches malformed MPI where high bit isn't actually set.
- All BIGNUM allocations checked; `goto err` cleanup path frees every
  BIGNUM via `BN_clear_free` (zeros memory before free) —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:142-160,194-211,236-247,272-283`.
- Elgamal `k` is fresh-random per encryption:
  `BN_rand(k, k_bits, 0, 0)` where `k_bits = decide_k_bits(BN_num_bits(p))`.
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:122-124` [verified-by-code].

## Notable internals

- **`decide_k_bits(p_bits)`** — `source/contrib/pgcrypto/pgp-mpi-openssl.c:91-98`.
  For `p_bits <= 5120` → `p_bits/10 + 160`; else `(p_bits/8 + 200) * 3/2`.
  Mimics gpg behavior, comment admits "Until I research it further". For
  RFC 7919 / NIST SP 800-56A safe primes the expected `k` size should
  match the subgroup order Q; this approach is heuristic but produces
  reasonable values.
- **No CRT for RSA decrypt.** `pgp_rsa_decrypt` only uses `d` and `n`
  (`source/contrib/pgcrypto/pgp-mpi-openssl.c:255-256`). The secret-key
  packet reads `d, p, q, u` (`pgp-pubkey.c:410-419`) but the CRT
  components are unused at decrypt time. Functional but 2-3× slower
  than CRT-based `BN_mod_exp_mont_consttime`.
  [ISSUE-defense-in-depth: RSA decrypt skips CRT (p,q,u unused); 2-3×
  slowdown for every `pgp_pub_decrypt` (maybe)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:251-284`.
- **`BN_mod_exp` is the non-constant-time variant.** OpenSSL provides
  `BN_mod_exp_mont_consttime` for secret exponents
  (cf. `BN_FLG_CONSTTIME` flag set on `BN_set_flags`). This file uses
  the generic `BN_mod_exp` everywhere, including in `pgp_rsa_decrypt`
  with the secret exponent `d` and in `pgp_elgamal_decrypt` with `x`.
  **Real exploitable timing surface.**
  [ISSUE-security: `BN_mod_exp` used with secret exponents in
  `pgp_rsa_decrypt` and `pgp_elgamal_decrypt`; should set
  `BN_FLG_CONSTTIME` to force constant-time `BN_mod_exp_mont_consttime`
  (likely)] — `source/contrib/pgcrypto/pgp-mpi-openssl.c:266,183`.

## Crypto trust boundary / Phase D surface

- **`BN_mod_exp` timing side-channel on secret exponents.** This is the
  textbook RSA timing attack (Brumley-Boneh 2003). For shared-tenancy
  Postgres + remote attacker with timing access, `pgp_pub_decrypt` could
  leak `d` over many requests. The fix is `BN_set_flags(d, BN_FLG_CONSTTIME)`
  before `BN_mod_exp` — trivial.
- **Elgamal `k` randomness.** `BN_rand(k, k_bits, 0, 0)` uses OpenSSL's
  default RAND, which in PG builds is initialized via libcrypto's own
  entropy gathering. If OpenSSL's RNG is unseeded (impossible in normal
  builds but worth noting), `k` would be predictable → key recovery.
  `pgcrypto` does not call `RAND_seed`/`RAND_status` to verify.
  [ISSUE-defense-in-depth: relies on OpenSSL RAND init for Elgamal `k`;
  no explicit `RAND_status` check (maybe)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:123`.
- **PKCS#1 v1.5 padding-oracle.** `pgp_rsa_decrypt` returns raw integer;
  `pgp-pubdec.c:check_eme_pkcs1_v15` then checks the `02 ... 00 ...`
  pad. If padding fails → `PXE_PGP_WRONG_KEY` (`pubdec.c:215`); if
  cksum fails → same `PXE_PGP_WRONG_KEY` (`pubdec.c:91`). Same error
  code, good. But the timing path is different (cksum runs only if
  pad OK), so a fine-grained timing oracle survives.
  [ISSUE-security: PKCS#1 v1.5 padding check is not constant-time;
  Bleichenbacher-class oracle possible if attacker can time
  `pgp_pub_decrypt` calls precisely (maybe)] —
  `source/contrib/pgcrypto/pgp-pubdec.c:42-67,211-220`.
- **`BN_clear_free` is called on every BIGNUM** including public values
  (n, e) where it's overkill but harmless. Secrets (d, x) properly
  zeroed. Good.
- **No length check on `pk->pub.rsa.n`.** Whatever modulus size the key
  has, we run `BN_mod_exp` on it. A maliciously-large public key (e.g.
  20 000-bit RSA, allowed by the 65 535-bit MPI cap) → expensive
  exponentiation per encrypt. The encrypt side is attacker-driven
  (`pgp_pub_encrypt(data, evil_huge_key)`) so this is a CPU-DoS surface.
  [ISSUE-security: no maximum modulus check; 60 000-bit RSA key
  triggers minutes-per-call exponentiation; CPU DoS on
  `pgp_pub_encrypt` (likely)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:215`. The MPI parsing
  cap (`pgp-mpi.c:42`) gives 65 535 bits as max, but no per-algorithm
  sanity cap (e.g. 8 192 for RSA).

## Cross-references

- `pgp-mpi.md` — MPI struct definition.
- `pgp-pubdec.md` / `pgp-pubenc.md` — callers of these routines.
- `pgp-pubkey.md` — parses the BIGNUM components from key packets.
- OpenSSL `BN_FLG_CONSTTIME` / `BN_set_flags` — the fix for timing
  leaks here.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: secret-exponent `BN_mod_exp` calls do not set
  `BN_FLG_CONSTTIME`; classic Brumley-Boneh timing attack surface in
  `pgp_rsa_decrypt` and `pgp_elgamal_decrypt` (likely)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:266,183`.
- [ISSUE-security: no maximum RSA modulus / Elgamal `p` size; CPU DoS
  via giant pubkey on encrypt (likely)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:215,101`.
- [ISSUE-defense-in-depth: RSA decrypt does not use CRT (p,q,u
  ignored); 2-3× slower than necessary (maybe)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:251-284`.
- [ISSUE-defense-in-depth: `decide_k_bits` is heuristic, comment admits
  "Until I research it further"; not matched to subgroup order Q from
  the DH parameters (maybe)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:91-98`.
- [ISSUE-error-handling: OpenSSL `BN_*` failures mapped to generic
  `PXE_PGP_MATH_FAILED`; no distinction between OOM and arithmetic
  error (nit)] —
  `source/contrib/pgcrypto/pgp-mpi-openssl.c:104,167,217,253`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgcrypto.md](../../../subsystems/contrib-pgcrypto.md)
