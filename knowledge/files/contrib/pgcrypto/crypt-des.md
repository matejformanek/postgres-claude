# crypt-des.c

## One-line summary

Traditional Unix crypt(3) DES password hash plus the BSD "extended"
DES variant (`_` salt prefix). David Burren's FreeSec implementation,
adopted into FreeBSD-2.0 and vendored here. Provides `px_crypt_des`,
called from `px-crypt.c` for empty-prefix and `_`-prefix salts.

Covers `source/contrib/pgcrypto/crypt-des.c` (791 lines).

## Public API / entry points

- `char *px_crypt_des(const char *key, const char *setting)` —
  `crypt-des.c:650-791`. Returns a pointer to a static buffer
  (NOT thread-safe — but PG backends are single-threaded so this is
  OK). The `setting` is the 2-byte salt for traditional crypt or
  the 9-byte `_RRRRSSSS` for extended crypt.

## Key invariants

- **Returns static `output[21]`** at `crypt-des.c:662`. Subsequent
  calls overwrite. Single-threaded backend makes this safe; concurrent
  use within one backend (e.g. callback from PL/perl?) would race.
  [verified-by-code]
- **Key is 8 bytes max for traditional DES** (`:737-739`). Bits 7
  of each byte are shifted out via `*q++ = *key << 1` at `:675`,
  yielding the classic 56-bit effective key. Anything beyond 8
  characters is silently ignored. [verified-by-code]
- **Extended DES uses full key** (`:705-722`) — iteratively
  encrypts the key with itself and XORs in the next 8 chars of
  password, letting the full password length contribute.
- **`des_init` is called lazily** on first invocation (`:626, 664`).
  The S-box and key-schedule tables are computed once and cached.
  `des_initialised` is the latch.
- **`CHECK_FOR_INTERRUPTS()` inside the inner DES round loop** at
  `crypt-des.c:541` — found by grep. (Inside `do_des`.) Mitigates
  extended-DES with high count. [verified-by-code]
- **Count = 25 for traditional DES** (`:740`). Hardcoded. The
  original 1976 crypt(3) iteration count.
- **Salt is 2 bytes (12 bits) for traditional DES** (`:747-748`).
  4096 possible salts — rainbow tables work.
- **For extended DES, salt is 4 bytes (24 bits) and count is 4
  bytes (24 bits)** (`:699-703`). Better than traditional but
  still weak.

## Notable internals

### Key shift trick

`crypt-des.c:673-678`:
```
while (q - (uint8 *) keybuf - 8)
{
    *q++ = *key << 1;
    if (*key != '\0') key++;
}
```
Each password byte is shifted left by 1 to discard the parity bit.
After NUL terminator, the loop continues filling zeros. So
`pass = "abcdefgh"` produces 8 bytes; `pass = "abc"` produces 3 shifted
bytes + 5 zeros.

### Setup of S-boxes etc

`des_init` (called from `:627, 665`) initializes:
- `IP[64]` — initial permutation
- `key_perm[56]`, `key_shifts[16]`, `comp_perm[48]` — key schedule
- 8 S-boxes (sb[8])
- Final permutation, etc.

All static tables. ~600 lines of constants and init code.

### Output encoding

Traditional DES: 13 chars total (2-char salt + 11-char hash).
Extended DES: 20 chars total (1 `_` + 4 count + 4 salt + 11 hash).

Encoded in `_crypt_a64`:
```
"./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
```
Same alphabet as MD5-crypt (NOT bcrypt's).

## Crypto trust boundary / Phase D surface

- **DES has been considered weak since at least 1998.** With
  modern GPU hardware, a single 13-char traditional DES hash can be
  brute-forced in seconds. **Yet `px_crypt_des` is the empty-salt
  default in `px-crypt.c:97`.** A user calling
  `crypt('password', 'aa')` gets a DES hash.
  [ISSUE-security: DES still the default for empty/unknown salt
  (confirmed)]
- **Extended DES (`_RRRRSSSS`)** is moderately better (configurable
  count up to 16M, 24-bit salt) but still 56-bit effective key.
  Solar Designer's bcrypt has been the recommended replacement
  since ~1998. [ISSUE-security: extended DES dispatch path still
  available (likely)]
- **8-character password truncation** for traditional DES means
  `crypt('passwordX', salt)` == `crypt('password', salt)`. Silent
  truncation. [ISSUE-security: silent 8-char key truncation (likely)]
- **`output[21]` static buffer** is a thread-unsafe pattern but
  safe within PG's single-threaded-backend model. **The buffer is
  NOT scrubbed between calls**, so the previous user's hash sits in
  bss memory until next call. [ISSUE-security: static output buffer
  not scrubbed (likely)]
- **No `px_memset(keybuf, 0, ...)` after use** — the local
  `keybuf` (the DES key) on the stack at `:659` is not explicitly
  scrubbed. Stack memory persists until overwritten by next call
  chain. [ISSUE-security: keybuf not scrubbed (likely)]
- **`CHECK_FOR_INTERRUPTS()` mitigates extended-DES DoS** with
  large counts, but max count = 0xFFFFFF means at most ~16M rounds
  ≈ a few seconds — not a serious DoS even at the cap.

## Cross-references

- `px-crypt.c:px_crypt_list` — dispatches empty and `_` prefixes
  here.
- `crypt-gensalt.c:_crypt_gensalt_traditional_rn`,
  `_crypt_gensalt_extended_rn` — generate the salt prefixes.
- `openssl.c:ossl_des_*` — OpenSSL's DES (for AES-style encrypt/
  decrypt SQL functions, NOT for password hashing). Distinct code
  paths.
- FreeBSD `secure/lib/libcrypt/crypt-des.c` — upstream.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: DES is the silent default for `crypt(pw,
  weak_salt)` (confirmed)] — entry point from px-crypt.c is the
  empty-prefix dispatch.
- [ISSUE-security: extended DES still dispatchable (likely)] —
  used for `_`-prefix salts.
- [ISSUE-security: 8-char password truncation in traditional DES
  (likely)] — `:737-739`.
- [ISSUE-security: static `output[21]` buffer not scrubbed
  (likely)] — `:662`.
- [ISSUE-security: stack-local keybuf not scrubbed (likely)] —
  `:659`. Compare with crypt-blowfish.c's explicit `px_memset(&data,
  ...)`.
- [ISSUE-defense-in-depth: `DISABLE_XDES` is defined-out
  (`px-crypt.h:97`) (nit)] — could be flipped on at build time to
  remove the extended-DES path. Default is on.
