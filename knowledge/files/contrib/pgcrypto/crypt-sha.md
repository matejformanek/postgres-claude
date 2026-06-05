# crypt-sha.c

## One-line summary

Ulrich Drepper's `$5$`-style SHA-256-crypt and `$6$`-style
SHA-512-crypt password hashing, implemented from
[akkadia.org/drepper/SHA-crypt.txt](https://www.akkadia.org/drepper/SHA-crypt.txt).
Provides `px_crypt_shacrypt`, dispatched from `px-crypt.c` for
`$5$` and `$6$` salt prefixes. Currently the most modern
password-hashing primitive in pgcrypto besides bcrypt (no Argon2,
no scrypt).

Covers `source/contrib/pgcrypto/crypt-sha.c` (642 lines).

## Public API / entry points

- `char *px_crypt_shacrypt(const char *pw, const char *salt,
  char *passwd, unsigned dstlen)` — `crypt-sha.c:68-642`.
  Implements the full 21-step Drepper algorithm. `dstlen` must
  be ≥ `PX_SHACRYPT_BUF_LEN`.

## Key invariants

- **Magic byte determines digest**: `$5$` → SHA-256 (32-byte
  digest), `$6$` → SHA-512 (64-byte digest). Other prefixes →
  `elog(ERROR, "unknown crypt identifier ...")`.
  [verified-by-code `:158-167, 273-275`]
- **Rounds default = 5000**, range `[1000, 999_999_999]` (`px-crypt.h:64-70`).
  Values outside the range are **clamped with NOTICE** (`:209-226`)
  rather than rejected, for compat with Drepper's reference.
  [verified-by-code]
- **Salt max 16 bytes** (`PX_SHACRYPT_SALT_MAX_LEN`). Longer salt
  bytes silently absorbed up to that cap (`:293-294`).
- **Salt char set restricted to `_crypt_itoa64`** (`:325-330`).
  Invalid chars → `ERRCODE_INVALID_PARAMETER_VALUE`.
- **`CHECK_FOR_INTERRUPTS()` inside the per-round loop**
  (`crypt-sha.c:498`). Necessary because max rounds = 10^9
  could take hours. [verified-by-code]
- **`px_memset` scrubs intermediate `sha_buf_tmp`** at `:480` and
  `sha_buf` at `:621`. Same LTO caveat.
- **`p_bytes` and `s_bytes` are palloc'd, freed without scrub**
  (`:537-538`). These hold password and salt byte sequences used
  in the main loop. [ISSUE-security: p_bytes/s_bytes not scrubbed
  before pfree (likely)]

## Notable internals

### Salt parsing

`crypt-sha.c:124-352`:
- Strip `$5$` or `$6$` magic.
- Optional `rounds=N$` prefix at `:184-230`.
- Up to 16 chars of salt, terminated by `$` or end-of-string.
- Reject embedded `$5$`/`$6$`/`rounds=` (defense against malformed
  inputs).

### The 21-step Drepper algorithm

`crypt-sha.c:361-529`. Mirrors the steps in Drepper's spec exactly.
Two digest contexts (`digestA`, `digestB`) are used as the "main"
and "intermediate" hashes. The byte sequences `p_bytes` (P) and
`s_bytes` (S) are computed once in steps 13-20, then mixed into A
in the main loop (step 21) using `rounds` iterations of:
- Add P or A (depending on parity)
- Add S (if round % 3 != 0)
- Add P (if round % 7 != 0)
- Add A or P (depending on parity)
- Finalize into A

### Output encoding

After the loop, `sha_buf` contains the final digest (32 or 64
bytes). The b64-encode pattern `b64_from_24bit` at
`crypt-sha.c:546-555` packs three bytes into four base64 chars.
The reordering tables at `:561-571` (SHA-256) and `:578-599`
(SHA-512) follow Drepper's spec for output byte permutation.

### Rounds clamping

`crypt-sha.c:209-226`: if user passes `rounds=` higher than max or
lower than min via the salt string, pgcrypto emits a NOTICE and
clamps to the bound. Drepper's reference does this too. Note that
`px_gen_salt` rejects out-of-range rounds via `PXE_BAD_SALT_ROUNDS`,
but if the salt is hand-crafted, clamping happens here.

### Two `PX_MD` per call

`:241-247, 259-265`. SHA-256 needs two SHA-256 digest contexts;
SHA-512 needs two SHA-512. The second is needed for the
intermediate digest B.

## Crypto trust boundary / Phase D surface

- **Rounds default 5000** is reasonable for 2008 (Drepper's spec)
  but light for 2026. Modern recommendation for SHA-512-crypt is
  ~200,000 rounds (1 second on modern CPU). pgcrypto's default is
  ~2 ms. [ISSUE-security: default rounds=5000 is too low for 2026
  (likely)]
- **Min rounds = 1000** — gives ~0.4 ms hashing. Trivially fast
  for brute-force. [ISSUE-security: min rounds=1000 too low (maybe)]
- **Max rounds = 999_999_999** — at ~5 µs/round for SHA-512, that
  is ~83 minutes of CPU per call. **DoS surface**: a non-superuser
  can call `crypt(pw, '$6$rounds=999999999$...')` and burn a backend
  for over an hour. `CHECK_FOR_INTERRUPTS` lets admin cancel.
  [ISSUE-security: shacrypt max rounds = ~1B → ~hour-long
  CPU consumption (confirmed)]
- **`p_bytes`/`s_bytes` not scrubbed** before pfree
  (`:537-541`). These contain password material derived from the
  user's password. Leaked into the freelist. [ISSUE-security:
  p_bytes/s_bytes scrub gap (likely)]
- **Pretty consistent scrub elsewhere** — `sha_buf` and
  `sha_buf_tmp` are scrubbed. The output `out_buf` is
  `destroyStringInfo`'d which `pfree`s but doesn't scrub.
- **`StringInfo` allocation** — `makeStringInfoExt(PX_SHACRYPT_BUF_LEN)`
  at `:117-118`. Uses palloc; on error path goes to `error:` label
  which destroys both StringInfos.
- **Cleartext password never scrubbed**. Same caller-side gap as
  crypt-md5.md.

## Cross-references

- `px-crypt.c:px_crypt_list` — dispatches `$5$`/`$6$` here.
- `crypt-gensalt.c:_crypt_gensalt_sha256_rn`,
  `_crypt_gensalt_sha512_rn` — generate the salt prefixes.
- `openssl.c:px_find_digest` — provides the SHA-256/SHA-512 PX_MD.
- A5 `src/common/sha2.c` — standalone SHA-2 implementation
  (used by libpq SCRAM). Different code path.
- Drepper's spec: https://www.akkadia.org/drepper/SHA-crypt.txt.

## Issues spotted

- [ISSUE-security: shacrypt max rounds = ~1B = ~hour-long CPU
  per call (confirmed)] — `px-crypt.h:70`. DoS for any SQL
  caller.
- [ISSUE-security: default rounds = 5000 is too low for 2026
  (likely)] — `:96, px-crypt.h:64`.
- [ISSUE-security: min rounds = 1000 too low for 2026 (maybe)] —
  `px-crypt.h:67`.
- [ISSUE-security: p_bytes/s_bytes (password-derived material)
  pfree'd without scrub (likely)] — `:537-541`.
- [ISSUE-defense-in-depth: out_buf->data pfree'd via
  destroyStringInfo without scrub (maybe)] — `:622`. Contains
  the salt + hash, less sensitive but still.
- [ISSUE-correctness: typo `PGCRYPTO_SHA_UNKOWN` (missing N)
  (nit)] — `:59, 273, 604`. Cosmetic.
