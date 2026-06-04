# pgp-s2k.c

## One-line summary

Implements the three OpenPGP "String-to-Key" password-hardening modes —
simple (one SHA), salted, and iterated+salted (RFC 4880 §3.7.1) — used to
derive a symmetric key from a passphrase for both the encrypted-session-key
packet and (on the encrypt side) the random salt/iter selection.

## Public API / entry points

- `pgp_s2k_fill(s2k, mode, digest_algo, count)` — initialize the S2K struct
  for *encryption* (generates salt + decides iter byte),
  `source/contrib/pgcrypto/pgp-s2k.c:223` [verified-by-code].
- `pgp_s2k_read(PullFilter *, PGP_S2K *)` — parse an S2K specifier from a
  packet (used by `parse_symenc_sesskey` and secret-key decoding),
  `source/contrib/pgcrypto/pgp-s2k.c:253` [verified-by-code].
- `pgp_s2k_process(s2k, cipher, key, key_len)` — run the key-derivation,
  populating `s2k->key` / `s2k->key_len`,
  `source/contrib/pgcrypto/pgp-s2k.c:279` [verified-by-code].

## Key invariants

- Three modes: SIMPLE(0) / SALTED(1) / ISALTED(3), per
  `source/contrib/pgcrypto/pgp.h:39-42` and dispatched in
  `pgp_s2k_process` at `source/contrib/pgcrypto/pgp-s2k.c:292-305`
  [verified-by-code].
- The output key length equals the cipher's key length (looked up via
  `pgp_get_cipher_key_size`); function fails with
  `PXE_PGP_UNSUPPORTED_CIPHER` if unknown. `source/contrib/pgcrypto/pgp-s2k.c:284-286`.
- "Preload zeros" trick to extend digest output: when the cipher needs more
  bits than one digest output, restart with N zero bytes prepended on iter
  N. `source/contrib/pgcrypto/pgp-s2k.c:55-59,98-102,148-152` [verified-by-code].
- Salt is always 8 bytes (`PGP_S2K_SALT`), `source/contrib/pgcrypto/pgp.h:115`.
- Salt and `iter` byte are drawn from `pg_strong_random`; failure yields
  `PXE_NO_RANDOM`. `source/contrib/pgcrypto/pgp-s2k.c:236-243` [verified-by-code].

## Notable internals

- **`decide_s2k_iter(rand_byte, count)`** — `source/contrib/pgcrypto/pgp-s2k.c:208`.
  When user gave `count = -1` (default), returns `96 + (rand_byte & 0x1F)`,
  meaning encoded `iter` ∈ [96, 127] → decoded iter count ∈
  [65 536, 262 144]. Otherwise loop iter byte 0..255 and pick the smallest
  whose decoded count >= requested. Caps at 255 (≈65 M iterations max).
- **`calc_s2k_iter_salted`** runs `salt || passphrase` repeatedly through
  the digest until `curcnt >= count` bytes have been fed in
  (`source/contrib/pgcrypto/pgp-s2k.c:159-176`). This is the classic
  OpenPGP iterated-salted KDF — slower than PBKDF2 per iteration (digest
  update with 8+key_len bytes) but functionally equivalent.
- The "1 byte added per restart" trick gives at most `PGP_MAX_DIGEST=64`
  re-runs because a SHA-256 output is 32 bytes and `PGP_MAX_KEY=32`, so for
  AES-256 only one extra restart needed.

## Crypto trust boundary / Phase D surface

- **No upper cap on the decoded iter count beyond the RFC 4880 ceiling
  (~65 M).** Decryption reads `s2k->iter` raw from ciphertext
  (`source/contrib/pgcrypto/pgp-s2k.c:270`) and runs that many digest
  bytes. A maliciously-crafted PGP message can force the maximum.
  [ISSUE-security: attacker-controlled S2K iteration count drives
  per-call CPU up to ~65 M digest ops; cumulative DoS over many
  `pgp_sym_decrypt` calls (likely)] —
  `source/contrib/pgcrypto/pgp-s2k.c:270` + `pgp.h:177`.
- **No constant-time discipline.** `calc_s2k_*` does plain `memcpy` /
  comparisons; not relevant since the input is always the user's password
  (no length oracle outside of timing-based password length leaks, which
  are unfixable for variable-length passwords).
- **Salt is `pg_strong_random`** — good. The salt is exposed in
  ciphertext (it must be), so leakage doesn't matter, but ENTROPY does.
- **`px_memset(buf, 0, sizeof(buf))`** scrubs the digest-output buffer
  after every loop, `source/contrib/pgcrypto/pgp-s2k.c:77,121,191`
  [verified-by-code]. Good. But `s2k->key` is left populated — it lives
  in the parent context's S2K struct and is consumed for CFB-key purposes
  before being zeroed by `pgp_free`.
- Default of 65 536-262 144 iterations is **weak for 2026**: a modern GPU
  cluster can attempt millions of SHA-1 chains per second. The user can
  bump via `s2k-count=N`, but defaults matter.
  [ISSUE-defense-in-depth: 65 536-262 144 default iteration window is
  ~2009-era GPG default; trivially brute-forceable on commodity GPU for
  short passwords (likely)] — `source/contrib/pgcrypto/pgp-s2k.c:213-214`.
- **No memory wiping on error path of `pgp_s2k_fill`.** If
  `pg_strong_random` fails after partial salt write, the partial salt is
  left in `s2k->salt`. Minor — caller treats whole struct as invalid.

## Cross-references

- `pgp-pgsql.md` — `pgp_sym_encrypt` / `pgp_sym_decrypt` are the SQL entry
  points whose `password` arg is fed through here.
- A11-3 pgcrypto core — `pg_strong_random`, `px_md_*` are PX abstractions
  used here.
- RFC 4880 §3.7.1.3 — the byte-encoded count formula.

## Issues spotted

- [ISSUE-security: uncapped attacker-controlled iter count on decrypt path,
  cumulative DoS via repeated `pgp_sym_decrypt` (likely)] —
  `source/contrib/pgcrypto/pgp-s2k.c:270`.
- [ISSUE-defense-in-depth: default iter window 65 536-262 144 is below
  modern NIST SP 800-132 / OWASP recommendations (likely)] —
  `source/contrib/pgcrypto/pgp-s2k.c:213-214`.
- [ISSUE-defense-in-depth: SHA-1 is the default `s2k_digest_algo`; modern
  pgcrypto could default to SHA-256 (nit)] —
  `source/contrib/pgcrypto/pgp.c:44`. SHA-1 second-preimage is still
  computationally hard, but the symbolism is bad.
- [ISSUE-correctness: `pgp_s2k_read` accepts mode=2 silently? No, it
  returns `PXE_PGP_BAD_S2K_MODE` (nit)] —
  `source/contrib/pgcrypto/pgp-s2k.c:272-273`. OK, no issue. Verified
  the `default:` branch covers all unknown modes.
