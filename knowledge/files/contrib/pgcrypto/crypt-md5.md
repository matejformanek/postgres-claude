# crypt-md5.c

## One-line summary

Poul-Henning Kamp's `$1$`-style MD5-crypt password hashing,
imported from FreeBSD circa 1999. Implements 1000-round MD5
iteration with salt mixing. Called from `px-crypt.c` for `$1$`
salt prefixes.

Covers `source/contrib/pgcrypto/crypt-md5.c` (169 lines).

## Public API / entry points

- `char *px_crypt_md5(const char *pw, const char *salt, char *passwd,
  unsigned dstlen)` — `crypt-md5.c:34-169`. `dstlen` must be ≥120.
  Salt is parsed: strips leading `$1$`, takes up to 8 chars before
  next `$`.

## Key invariants

- **Hardcoded 1000 rounds** (`crypt-md5.c:119`). No rounds
  parameter, no way to increase. PHK's original comment at `:115-118`
  says "On a 60 Mhz Pentium this takes 34 msec" — i.e. ~34 ms in
  1999, well under 1 ms on modern hardware. **For 2026 password
  hashing, 1000 rounds of MD5 is utterly insufficient.**
  [ISSUE-security: 1000 rounds hardcoded; effectively no work
  factor (confirmed)]
- **Salt max 8 chars** (`crypt-md5.c:62`). Stops at first `$` or
  after 8 bytes.
- **`dstlen < 120`** returns NULL (`:51-52`).
- **Two PX_MD objects required** (`:69-78`). If the second
  `px_find_digest` fails (low memory), the first is freed cleanly.
- **Final scrub of `final[16]` stack array** at `:163` and earlier at
  `:98`. Uses `px_memset`. Same LTO-elision caveat as elsewhere.

## Notable internals

### The "really weird" loop

`crypt-md5.c:100-105`:
```
for (i = strlen(pw); i; i >>= 1)
    if (i & 1) px_md_update(ctx, final, 1);
    else       px_md_update(ctx, (const uint8 *) pw, 1);
```
For each bit of the password length, mixes either one byte of the
MD5(pw,salt,pw) digest or one byte of the password into the running
hash. The PHK trick — described in PHK's posted source as "just to
make sure things don't run too fast" but the actual purpose is to
inject password-length information into the digest in a way that
resists straightforward parallelization.

### The 1000-round inner loop

`:119-138`. Each iteration:
1. Reset digest B.
2. Add either password or previous digest, depending on `i & 1`.
3. Add salt if `i % 3 != 0`.
4. Add password if `i % 7 != 0`.
5. Finalize into `final[]`.

The `% 3` and `% 7` choices are designed to make precomputation
hard — each iteration mixes in a different selection of inputs.

### Output encoding

`_crypt_a64` alphabet (same as DES crypt). 22 base64-ish chars of
output after the `$1$<salt>$` prefix. Total output length is
3 (magic) + ≤8 (salt) + 1 ($) + 22 (hash) = 34 chars max. Hence
the 120-byte dstlen minimum is generously oversized.

## Crypto trust boundary / Phase D surface

- **MD5-crypt is fundamentally weak in 2026**. 1000 hardcoded
  rounds is ~6 microseconds on modern CPU. A GPU can do billions
  of these per second. **Any password hashed with `$1$` is
  effectively in cleartext given a stolen hash.**
  [ISSUE-security: MD5-crypt hardcoded 1000 rounds, broken in 2026
  (confirmed)]
- **MD5 collision resistance is broken** (since 2004 Wang attack).
  For password hashing this is less critical than for signatures,
  but still — using MD5 at all for new password storage is poor
  hygiene.
- **`gen_salt('md5')` still works** (see crypt-gensalt.c), so users
  can ask pgcrypto to generate `$1$` salts and the cycle perpetuates.
- **Stack-local `final[MD5_SIZE]` is scrubbed twice**: once at
  `:98` (mid-function reuse), once at `:163` (end). Good
  discipline; subject to LTO elision.
- **Password is passed by `const char *`** and never scrubbed —
  but pw is `pgcrypto.c`'s `buf0`, a `palloc`'d copy of the SQL
  text argument. That copy gets `pfree`'d after `px_crypt`
  returns (`pgcrypto.c:230`), but **the bytes are not scrubbed
  before pfree**.
  [ISSUE-security: pw cstring not scrubbed before pfree (likely)]
- **No `CHECK_FOR_INTERRUPTS`** in the 1000-round loop. Fast
  enough that it doesn't matter (≤ 1ms total).

## Cross-references

- `px-crypt.c:px_crypt_list` — dispatches `$1$` here.
- `crypt-gensalt.c:_crypt_gensalt_md5_rn` — generates `$1$<salt>$`
  prefix.
- `crypt-sha.c:px_crypt_shacrypt` — the SHA-{256,512}-crypt
  replacement, with proper rounds parameter.
- FreeBSD `lib/libcrypt/crypt-md5.c` — upstream.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: 1000-round hardcoded count makes MD5-crypt
  trivially crackable in 2026 (confirmed)] — `:119`.
- [ISSUE-security: MD5 collision-broken since 2004 (confirmed)] —
  not load-bearing for password hashing per se, but bad hygiene.
- [ISSUE-security: no `CHECK_FOR_INTERRUPTS` — but DoS-irrelevant
  given speed (nit)].
- [ISSUE-security: password cstring not scrubbed before pfree in
  caller (likely)] — `pgcrypto.c:230` pfrees `buf0` without
  scrubbing.
- [ISSUE-defense-in-depth: no warning emitted when `$1$` is used
  in 2026 (likely)] — Should at least NOTICE.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgcrypto.md](../../../subsystems/contrib-pgcrypto.md)
