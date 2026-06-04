# px-crypt.c / px-crypt.h

## One-line summary

Dispatch layer between the SQL `crypt(pw, salt)` / `gen_salt(type)`
functions and the underlying password-hashing implementations
(traditional DES, MD5-crypt, bcrypt, SHA-256/512-crypt, extended DES).
This is the ONLY place in pgcrypto where `CheckBuiltinCryptoMode` is
called — i.e. the GUC-gated path.

Covers `source/contrib/pgcrypto/px-crypt.c` (190 lines) and
`source/contrib/pgcrypto/px-crypt.h` (113 lines).

## Public API / entry points

- `char *px_crypt(const char *psw, const char *salt, char *buf, unsigned len)`
  — `px-crypt.c:101-120`. Dispatches by salt prefix to one of:
  - `"$2a$"` / `"$2x$"` → bcrypt (`crypt-blowfish.c`)
  - `"$2$"` → reserved, no implementation (returns NULL)
  - `"$1$"` → MD5-crypt (`crypt-md5.c`)
  - `"$5$"` → SHA-256-crypt (`crypt-sha.c`)
  - `"$6$"` → SHA-512-crypt (`crypt-sha.c`)
  - `"_"` → extended DES (`crypt-des.c`)
  - empty / no prefix → traditional DES (`crypt-des.c`)
- `int px_gen_salt(const char *salt_type, char *buf, int rounds)`
  — `px-crypt.c:155-190`. Salt-string generator. Calls
  `pg_strong_random(rbuf, g->input_len)` for entropy, then dispatches
  to one of the `_crypt_gensalt_*_rn` functions (defined in
  `crypt-gensalt.c` and `crypt-blowfish.c`).

### Header (`px-crypt.h`)

The header exposes:

- `PX_MAX_CRYPT` = 128 (`px-crypt.h:36`)
- `PX_MAX_SALT_LEN` = 128 (`px-crypt.h:39`, duplicate of `px.h:41`)
- `PX_XDES_ROUNDS` = `29 * 25` = 725 (`px-crypt.h:43`)
- `PX_BF_ROUNDS` = 6 — default bcrypt cost (`px-crypt.h:46`)
- `PX_SHACRYPT_SALT_MAX_LEN` = 16
- `PX_SHACRYPT_ROUNDS_DEFAULT` = 5000
- `PX_SHACRYPT_ROUNDS_MIN` = 1000
- `PX_SHACRYPT_ROUNDS_MAX` = 999_999_999

Plus prototypes for `_crypt_gensalt_*_rn`, `_crypt_blowfish_rn`,
`px_crypt_des`, `px_crypt_md5`, `px_crypt_shacrypt`.

## Key invariants

- **`CheckBuiltinCryptoMode()` is called at the entry of both
  `px_crypt` and `px_gen_salt`** (`px-crypt.c:106, 162`). If the GUC
  is `off`, or is `fips` and OpenSSL is in FIPS mode, both functions
  ereport(ERROR) before dispatching to vendored code. [verified-by-code]
- **Dispatch is by salt prefix string match**, not by hash type name
  (`px_crypt`). For `gen_salt`, dispatch is by case-insensitive name
  match (`pg_strcasecmp`) (`px-crypt.c:165`).
- **Empty salt → DES**. The table sentinel `{"", 0, run_crypt_des}` at
  `px-crypt.c:97` is matched by the `!c->id_len` break at `:110-111`.
  Any salt without a `$xx$` magic prefix is interpreted as
  traditional DES. [verified-by-code]
- **`px_gen_salt` validates rounds against per-algorithm
  `min_rounds`/`max_rounds`** (`px-crypt.c:176-178`) — but only for
  algos that have `def_rounds != 0` (i.e. xdes, bf, sha256crypt,
  sha512crypt). DES and MD5 have no rounds parameter validation.
- **Entropy buffer is scrubbed**: `px_memset(rbuf, 0, sizeof(rbuf))`
  at `px-crypt.c:184` — but the 16-byte stack buffer is only scrubbed
  after consumption; the generated salt is in `buf` which is returned
  to caller. [verified-by-code]

## Notable internals

### Generator table (`px-crypt.c:137-153`)

```
{"des",         _crypt_gensalt_traditional_rn,  2,  0,             0,                     0}
{"md5",         _crypt_gensalt_md5_rn,          6,  0,             0,                     0}
{"xdes",        _crypt_gensalt_extended_rn,     3,  PX_XDES_ROUNDS, 1,                    0xFFFFFF}
{"bf",          _crypt_gensalt_blowfish_rn,     16, PX_BF_ROUNDS,  4,                     31}
{"sha256crypt", _crypt_gensalt_sha256_rn,       16, 5000,          1000,                  999999999}
{"sha512crypt", _crypt_gensalt_sha512_rn,       16, 5000,          1000,                  999999999}
```

Fields: `name, gen_fn, input_len, def_rounds, min_rounds, max_rounds`.

- **bf max_rounds = 31** — this is the bcrypt cost factor cap.
  Bcrypt cost = `1 << rounds` iterations. Cost=31 means 2^31
  Blowfish key schedules ≈ multiple hours per call on modern
  hardware. Cost=20 ≈ ~3 seconds. **No upper-bound DoS protection
  beyond 31.** The bcrypt implementation itself bounds the encoded
  cost field at "0-31" via `setting[4] < '0' || setting[4] > '3'`
  and `setting[4] == '3' && setting[5] > '1'`
  (`crypt-blowfish.c:622-625`). [verified-by-code]
- **xdes max_rounds = 0xFFFFFF** — 16M iterations, capped by the
  4-character base64 encoding in the salt.
- **shacrypt max_rounds = 999999999** — about 12 hours of CPU on a
  modern box at PG_SHACRYPT_ROUNDS_DEFAULT speed.
  [ISSUE-security: shacrypt rounds cap at ~1B is a DoS vector for
  a non-superuser SQL caller (maybe)]
- **Min rounds for bcrypt = 4**. Cost factor 4 is fast enough
  (~1ms) to be useless for password hashing. Should probably be
  10 or 12 in 2026. [ISSUE-defense-in-depth: bcrypt min_rounds=4
  too low (likely)]
- **DES and MD5 have no `def_rounds`** so the rounds-validation block
  at `px-crypt.c:171-178` is skipped. They accept any caller's
  `rounds` argument silently (it's just ignored).

### Random salt input

`px_gen_salt` always uses `pg_strong_random` for the salt-input
entropy (`px-crypt.c:180`), regardless of algorithm. So even
`gen_salt('des')` gets strong randomness for its 2-byte salt — but
**the 2-byte DES salt has only 4096 possible values**, so rainbow
tables are trivial. The RNG quality is irrelevant. [verified-by-code]

## Crypto trust boundary / Phase D surface

- **`crypt(pw, 'aa')` returns a DES hash** with no warning.
  `px-crypt.c:97` empty-prefix → `run_crypt_des`.
  [ISSUE-security: DES path still accessible (confirmed)]
- **`gen_salt('des')` produces a 2-byte salt for traditional DES,
  no warning** (`px-crypt.c:138`).
  [ISSUE-security: weak DES gen_salt accepted (confirmed)]
- **`gen_salt('xdes')` produces an extended-DES salt, no warning**
  (`px-crypt.c:140`). XDES is better than DES but still uses 8-char
  key truncation.
  [ISSUE-security: xdes gen_salt accepted without warning (likely)]
- **`gen_salt('md5')` produces a `$1$`-style MD5-crypt salt**
  (`px-crypt.c:139`). MD5-crypt itself is considered weak by modern
  standards (1000 hardcoded rounds — see `crypt-md5.c:119`).
  [ISSUE-security: gen_salt('md5') accepted without warning (likely)]
- **`gen_salt('bf')` defaults to cost=6**, way below modern OWASP
  recommendation (cost=12+). `PX_BF_ROUNDS` at `px-crypt.h:46`.
  [ISSUE-security: bcrypt default cost=6 is too low (confirmed)]
- **`CheckBuiltinCryptoMode`** is the GUC kill-switch for
  `pgcrypto.builtin_crypto_enabled`. Setting it to `off` disables
  ALL of `crypt` and `gen_salt` (including bcrypt and SHA-crypt).
  Setting it to `fips` defers to OpenSSL's FIPS mode.
- **RNG**: salt entropy comes from `pg_strong_random` — same as the
  rest of the corpus. Verified.

## Cross-references

- `crypt-blowfish.c` — bcrypt implementation, called via `_crypt_blowfish_rn`.
- `crypt-des.c` — `px_crypt_des`.
- `crypt-md5.c` — `px_crypt_md5`.
- `crypt-sha.c` — `px_crypt_shacrypt`.
- `crypt-gensalt.c` — `_crypt_gensalt_traditional_rn`,
  `_crypt_gensalt_extended_rn`, `_crypt_gensalt_md5_rn`,
  `_crypt_gensalt_blowfish_rn`, `_crypt_gensalt_sha256_rn`,
  `_crypt_gensalt_sha512_rn`.
- `openssl.c:CheckBuiltinCryptoMode` — the GUC enforcement.
- `pg_strong_random` — corpus-wide RNG.

## Issues spotted

- [ISSUE-security: DES dispatch path accessible without warning
  (confirmed)] — `px-crypt.c:96-97`.
- [ISSUE-security: bcrypt default cost=6 (confirmed)] —
  `px-crypt.h:46`. OWASP recommends 12+ as of 2023.
- [ISSUE-security: bcrypt min_rounds=4 (likely)] — `px-crypt.c:141`.
- [ISSUE-security: gen_salt('md5'|'des'|'xdes') accepted without
  warning (likely)] — `px-crypt.c:138-140`.
- [ISSUE-security: shacrypt max_rounds = 999_999_999 is a CPU DoS
  surface for a non-superuser SQL caller (maybe)] — `px-crypt.h:70`.
- [ISSUE-audit-gap: rounds argument for DES/MD5 silently ignored
  (nit)] — `px-crypt.c:171-178` only validates rounds for algos
  with def_rounds. User calling `gen_salt('md5', 100000)` gets the
  same output as `gen_salt('md5', 0)`.
