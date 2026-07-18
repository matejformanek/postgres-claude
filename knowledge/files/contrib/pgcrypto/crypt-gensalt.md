# crypt-gensalt.c

## One-line summary

Salt-string generators for the password-hashing algorithms. Each
`_crypt_gensalt_*_rn` formats a `pg_strong_random`-seeded byte
sequence into the algorithm-specific salt syntax (`$1$...$`,
`$2a$NN$...`, `$5$rounds=N$...`, `_RRRRSSSS`, or 2-byte traditional).
Called from `px-crypt.c:px_gen_salt`.

Covers `source/contrib/pgcrypto/crypt-gensalt.c` (271 lines).

## Public API / entry points

- `_crypt_gensalt_traditional_rn(count, input, size, output,
  output_size)` — `crypt-gensalt.c:24-40`. 2-byte DES salt. Rejects
  `count != 0 && count != 25`.
- `_crypt_gensalt_extended_rn` — `crypt-gensalt.c:42-78`. Extended
  DES `_RRRRSSSS`. Default count = 725. Rejects even counts
  ("weak DES key" risk).
- `_crypt_gensalt_md5_rn` — `crypt-gensalt.c:80-118`. `$1$<4or8>$`
  prefix. Hardcoded count = 1000 (rejects any other).
- `_crypt_gensalt_blowfish_rn` — `crypt-gensalt.c:162-189`.
  `$2a$NN$<22 chars>` prefix. Cost factor `[4, 31]`. Default 5.
  Notice: the file always emits `$2a$`, not `$2x$` — the buggy
  variant cannot be generated, only verified.
- `_crypt_gensalt_sha256_rn`, `_crypt_gensalt_sha512_rn` —
  `crypt-gensalt.c:243-271`. `$5$rounds=N$<16 chars>` or
  `$6$rounds=N$<16 chars>`. Delegate to internal
  `_crypt_gensalt_sha`.

## Key invariants

- **All RNG entropy comes from caller** — these functions just
  format `input` (caller already `pg_strong_random`'d it in
  `px-crypt.c:180`).
- **Output is plain ASCII salt string**, terminated by NUL.
- **`_crypt_gensalt_extended_rn` rejects even counts** at
  `:53`. Comment at `:49-51` explains: even counts make weak-DES-key
  detection easier. Hardcoded defense.
- **`_crypt_gensalt_blowfish_rn` always emits `$2a$`**, the
  correct (non-sign-extension-bug) variant
  (`crypt-gensalt.c:178-179`). `$2x$` is verify-only.
- **`_crypt_gensalt_sha*_rn` always emits `rounds=<N>`** even when
  the count is the default 5000 (`:219`, also crypt-sha.c:32-33).
  Drepper's reference does this optionally; pgcrypto always.
- **`BF_encode`** at `:125-160` is the bcrypt base64 encoder. The
  alphabet is `"./ABCDEF...0123456789"` (note: digits LAST in
  bcrypt's alphabet, unlike `_crypt_itoa64`'s digits-FIRST).
  [verified-by-code]

## Notable internals

### Two alphabets

- `_crypt_itoa64` (`:21-22`): `"./0123456789ABC...xyz"` — used by
  traditional DES, extended DES, MD5-crypt, SHA-{256,512}-crypt.
- `BF_itoa64` (`:122-123`): `"./ABCDEF...0123456789"` — used by
  bcrypt. Digits at the end.

A user who pastes a bcrypt salt into a DES function or vice versa
will get garbage. The dispatch layer in `px-crypt.c` uses prefix
matching, not character-set validation, so this is a real footgun.

### Bcrypt default cost = 5

`crypt-gensalt.c:175`: `if (!count) count = 5;`. So
`gen_salt('bf')` (no rounds arg) yields cost 5 — 32 rounds — about
3 ms of bcrypt computation. **Way below modern OWASP recommendation
(12+).** [ISSUE-security: gen_salt('bf') default cost too low
(confirmed)]
Note: `px-crypt.c:141` says `def_rounds = PX_BF_ROUNDS = 6` but
this generator hardcodes 5 when count==0. Inconsistency — the
dispatch in `px_gen_salt` passes `def_rounds = 6` when caller
passed 0, so the count!=0 branch hits 6. But if somehow count=0
got through, this would be 5. [ISSUE-correctness: minor const
drift between PX_BF_ROUNDS (6) and crypt-gensalt.c default (5)
(nit)]

### Extended DES default count = 725

`:60-61`. Same as `PX_XDES_ROUNDS = 29 * 25` (from `px-crypt.h:43`).
Comment notes this matches NetBSD `bin/passwd/local_passwd.c`.

### SHA salt formatting

`_crypt_gensalt_sha` (`:194-241`):
1. Emit 3-byte magic at offset 0-2 (set by caller).
2. Format `rounds=%lu$` at offset 3.
3. Append `size` (16) bytes of base64-encoded input.
4. NUL-terminate.

Uses `pg_snprintf` for the rounds field; rejects on encoding error.

## Crypto trust boundary / Phase D surface

- **RNG quality is the caller's problem** (`px-crypt.c:180` calls
  `pg_strong_random`). Verified.
- **Even-count rejection for extended DES** is a defense against
  one specific weak-key class. Good.
- **Bcrypt default cost = 5 (32 rounds, ~3 ms)** is too low for
  2026. Most modern guidance: cost ≥ 12.
- **No deprecation warning** when `gen_salt('des')`, `'xdes'`, or
  `'md5'` is called. Even passing in the legacy salt type strings
  is silently accepted.
- **No max-cost cap below 31 for bcrypt** — caller can request
  cost 31 → 2^31 iterations. DoS surface.
- **The `_crypt_gensalt_traditional_rn` 2-byte output** (`:35-36`)
  takes only 12 bits of randomness from the 16-byte
  `pg_strong_random` input. The remaining 14 bytes are wasted but
  not leaked.

## Cross-references

- `px-crypt.c:px_gen_salt` — the caller; provides RNG input via
  `pg_strong_random`.
- `crypt-blowfish.c:_crypt_blowfish_rn` — verifier counterpart.
- `crypt-des.c:px_crypt_des` — verifier for traditional/extended
  DES salts.
- `crypt-md5.c:px_crypt_md5` — verifier for MD5-crypt.
- `crypt-sha.c:px_crypt_shacrypt` — verifier for SHA-{256,512}-crypt.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: bcrypt default cost = 5 (confirmed)] — `:175`.
  Too low for 2026.
- [ISSUE-correctness: PX_BF_ROUNDS (6) vs hardcoded default 5
  (nit)] — minor inconsistency between px-crypt.h and this file.
  Resolved by px_gen_salt routing — `def_rounds=6` is the
  effective value.
- [ISSUE-security: no deprecation warning for legacy algos
  ('des', 'xdes', 'md5') (likely)] — caller picks the algo by
  name; gensalt silently accepts.
- [ISSUE-security: caller can request bcrypt cost up to 31 via
  px_gen_salt (likely)] — `px-crypt.c:141`. DoS vector.
- [ISSUE-defense-in-depth: two different base64 alphabets
  (`_crypt_itoa64` vs `BF_itoa64`) are easy to confuse (nit)] —
  duplicated alphabet tables, no shared helper.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgcrypto.md](../../../subsystems/contrib-pgcrypto.md)
