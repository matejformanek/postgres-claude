# crypt-blowfish.c

## One-line summary

Solar Designer's bcrypt implementation, vendored from John the Ripper
with reentrant + crypt(3) interfaces added. Implements the
`$2a$`/`$2x$`-prefix bcrypt password hashing used by
`px_crypt(pw, '$2a$...')`. Includes the 2011-era sign-extension bug
fix (the `$2x$` variant deliberately reproduces the buggy
sign-extension behavior for compat with old broken hashes).

Covers `source/contrib/pgcrypto/crypt-blowfish.c` (760 lines).

## Public API / entry points

- `char *_crypt_blowfish_rn(const char *key, const char *setting,
  char *output, int size)` — `crypt-blowfish.c:581-760`.
  Reentrant bcrypt. `setting` must be a `$2a$NN$` or `$2x$NN$` salt
  prefix followed by 22 base64 chars. `output` must have at least
  `7 + 22 + 31 + 1 = 61` bytes. Returns `output` on success, NULL
  on insufficient buffer; ereport(ERROR) on malformed salt.

## Key invariants

- **Cost factor encoded as two ASCII digits**, bound `04..31` by
  the parser at `crypt-blowfish.c:623-625`. Cost = `1 << NN`.
  Cost=31 = 2^31 Blowfish key schedules. [verified-by-code]
- **Cost minimum NN=04** (verified `:623` `setting[4] < '0'` and
  `:624` digit checks). NN=00 through NN=03 are rejected by the
  digit-range check. [verified-by-code]
- **Cost factor cap NN=31** at `:625` (`setting[4] == '3' &&
  setting[5] > '1'` rejects). Beyond cost 31 the iteration count
  would overflow the `BF_word` (uint32). [verified-by-code]
- **`count < 16` check** at `:634` is redundant given the
  prefix-digit check (minimum cost factor 4 gives count = 16), but
  serves as a safety net. [verified-by-code]
- **The salt itself is 16 bytes** decoded via `BF_decode` from 22
  base64 chars (`:634`).
- **Output is 60 bytes** (`$2a$NN$` + 22 salt chars + 31 hash
  chars + NUL). Buffer size 61 enforced at `:605-606`.
- **`CHECK_FOR_INTERRUPTS()` inside the inner cost-loop**
  (`crypt-blowfish.c:676`). Lets a SIGINT cancel a high-cost
  bcrypt computation. Without this, `crypt(pw, '$2a$31$...')`
  would be uninterruptible (~hours of CPU). [verified-by-code]
- **Stack scrub at end**: `px_memset(&data, 0, sizeof(data))` at
  `:757`. Comment at `:752-755` is honest that "this does not
  guarantee there's no sensitive data left on the stack and/or in
  registers". [from-comment, verified-by-code]

## Notable internals

### Cost-factor encoding

```
count = (BF_word) 1 << ((setting[4] - '0') * 10 + (setting[5] - '0'));
```
`crypt-blowfish.c:633`. So `$2a$10$...` means count = 1024 rounds
(approximately 100 ms on modern CPU), `$2a$12$...` means count = 4096
(~400 ms), `$2a$31$...` means 2^31 rounds (~~hours).

### Salt format check

`:619-631`:
- byte 0: `$`
- byte 1: `2`
- byte 2: `a` or `x` (the `x` variant preserves the historical
  sign-extension bug for compat)
- byte 3: `$`
- bytes 4-5: two-digit cost
- byte 6: `$`
- bytes 7-28: 22 base64 chars (salt)

### Sign-extension bug (`$2x$`)

The `BF_set_key` function at `crypt-blowfish.c:550-579` takes a
`sign_extension_bug` flag. When set, the key bytes are sign-extended
to BF_word_signed (signed int) before being shifted into `tmp`. This
reproduces a bug present in the original Solar Designer bcrypt for
about 13 years until fixed in 2011. The `$2x$` prefix opts into the
buggy behavior; `$2a$` uses the correct unsigned extension.

This is the **explicit upstream-Solar-Designer 2011 sign-extension
fix**, verified present:
- `BF_set_key` signature with `sign_extension_bug` flag at `:550-552`
- `$2x$` accepted at `:621`
- Selected at `:643`: `BF_set_key(key, ..., setting[2] == 'x')`
[verified-by-code]

### BF_init_state — Pi-digits table

`:78-548` (approx) — the standard Blowfish P-box / S-box tables
initialized with digits of π. Constant data; ~470 lines of hex.

### BF_ENCRYPT macro

Defined elsewhere in the file (within the 470 lines of tables); does
one round of Blowfish encryption with optional asm acceleration on
x86. `BF_ASM` is gated to 0 in this build (`crypt-blowfish.c:42-50`),
so pure C is used.

### `BF_swap`, `BF_decode`, `BF_encode`

Helper functions defined in the file (and one — `BF_encode` — also
in `crypt-gensalt.c`). Handle the base64-ish encoding using the
nonstandard bcrypt alphabet `"./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"`.

## Crypto trust boundary / Phase D surface

- **Cost-factor cap = 31** (`crypt-blowfish.c:625`). DoS surface:
  a single SQL `crypt(pw, '$2a$31$...')` call burns ~3 minutes of
  CPU on modern hardware. Multiplied by concurrent backends, this
  is a denial-of-service vector for any non-superuser.
  `CHECK_FOR_INTERRUPTS()` (`:676`) lets the admin cancel; without
  it the situation would be worse.
  [ISSUE-security: bcrypt cost up to 31 is a DoS vector
  (likely)]
- **`$2x$` (buggy) variant still callable**. A user can supply
  a `$2x$10$...` salt and pgcrypto will compute the
  sign-extension-bugged hash. This is intentional (for verifying
  legacy stored hashes from the 1998-2011 era) but means any
  pgcrypto user can opt into a known-broken algorithm. There is
  no warning. [ISSUE-security: `$2x$` (buggy bcrypt) silently
  callable (maybe)]
- **Stack scrub**: `px_memset(&data, ...)` at `:757`. Same
  LTO-elision risk as elsewhere. The comment at `:752-755` is
  Solar Designer's honest disclaimer.
- **Solar Designer's 2011 sign-extension fix is verified present.**
  This is the canonical upstream version, not a forked-and-broken
  copy. [verified-by-code]
- **Min cost = 4** is too low for 2026. Modern OWASP recommendation
  is 12+. But this is enforced by `_crypt_gensalt_blowfish_rn` (see
  crypt-gensalt.c) only when generating salts via `gen_salt('bf')`;
  the bcrypt verifier here will accept any cost 4-31 in a stored
  hash. (Necessary for verifying legacy hashes; not a bug per se.)

## Cross-references

- `crypt-gensalt.c:_crypt_gensalt_blowfish_rn` — generates the
  `$2a$NN$...` salt prefix.
- `px-crypt.c:px_crypt_list` — dispatches `$2a$`/`$2x$` here.
- `crypt-blowfish.c` itself is the canonical PostgreSQL-vendored
  copy of Solar Designer's reference.
- `openssl.c` has its own Blowfish (block cipher, not bcrypt) — the
  two implementations are unrelated.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: bcrypt cost=31 is a per-call DoS vector
  (likely)] — `:625`. `CHECK_FOR_INTERRUPTS` mitigates but does
  not prevent.
- [ISSUE-security: `$2x$` (sign-extension-buggy) variant still
  callable without warning (maybe)] — `:621, 643`. Intentional for
  legacy verification but worth flagging.
- [ISSUE-defense-in-depth: stack scrub may be elided under LTO
  (likely)] — `:757`. Same as px-memset issue.
- [ISSUE-correctness: comment at `:744-747` "bug-compatible with
  the original implementation, so only encode 23 of the 24 bytes"
  is itself a permanent compat-bug that's now part of the wire
  format. (Documentation nit.)] — Cannot be fixed without breaking
  every stored bcrypt hash in the world. Working as intended.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgcrypto.md](../../../subsystems/contrib-pgcrypto.md)
