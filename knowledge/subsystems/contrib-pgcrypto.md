# contrib-pgcrypto (cryptographic primitives)

- **Source path:** `source/contrib/pgcrypto/`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Extension version:** `1.4` (per `pgcrypto.control`)
- **Trusted:** yes (`trusted = true` in `.control`)

## 1. Purpose

Cryptographic functions exposed as SQL — hashes (`digest`,
`hmac`), symmetric encryption (`encrypt`/`decrypt`), legacy
`crypt`-style password hashing (`crypt`, `gen_salt`), random bytes
(`gen_random_bytes`, `gen_random_uuid`), and PGP-compatible
asymmetric + symmetric encryption (`pgp_pub_encrypt`,
`pgp_sym_encrypt`, etc.). Trusted extension — a database owner can
`CREATE EXTENSION pgcrypto` without being a superuser.

## 2. Mental model

- **Two crypto backends, picked at build time.**
  - **OpenSSL** (`openssl.c`) — preferred when `--with-ssl=openssl`
    is configured; gives modern algorithms + FIPS modes.
  - **Built-in** (`crypt-*.c`, `sha1.c`, `internal.c`, `blf.c`,
    `rijndael.c`) — fallback when OpenSSL isn't linked. AES, DES,
    Blowfish, SHA-1/256/512, MD5 in pure C.
  The PX (`px.h`) layer abstracts both — every SQL-callable function
  goes through `px_find_digest` / `px_find_cipher`, so the same
  SQL surface works with either backend.

- **PGP support is mostly self-contained.** The 16 `pgp-*.c` files
  implement RFC 4880 (OpenPGP) for compatibility with `gpg`.
  Used by `pgp_pub_*` / `pgp_sym_*` SQL functions.

- **`gen_random_uuid` is exported on PG 13+**, but the SQL surface
  in pgcrypto remained for backwards-compat; on modern PG you can
  use the in-core `gen_random_uuid()` directly.

## 3. Key files

- `pgcrypto.c` — fmgr wrappers for `digest` / `hmac` / `encrypt` /
  `decrypt` / `gen_random_bytes` / `crypt` / `gen_salt` (~480 LOC).
- `px.c`, `px.h` — algorithm-lookup abstraction (PX = "PostgreSQL
  eXtended"). Provides `px_find_digest` / `px_find_cipher` / `px_get_random_bytes`.
- `px-crypt.c`, `px-crypt.h` — `crypt(3)`-compatible password
  hashing dispatch.
- `crypt-md5.c`, `crypt-sha.c`, `crypt-blowfish.c`, `crypt-des.c`,
  `crypt-gensalt.c` — built-in `crypt(3)` variants.
- `openssl.c` — OpenSSL-backed implementations of `px_find_*`.
- `internal.c`, `internal-sha2.c` — built-in implementations.
- `mbuf.c`, `mbuf.h` — multi-buffer chained-byte-stream abstraction
  used by PGP code for streaming encrypt/decrypt.
- `pgp.c`, `pgp.h`, `pgp-*.c` (16 files) — OpenPGP implementation
  (packets, sessions, MDC, MPI, S2K, compression, armor).

## 4. Key data structures

- **PX algorithm descriptors** (`px.h`):
  - `PX_MD` — message-digest interface (init/update/finish/reset/free).
  - `PX_HMAC` — keyed HMAC interface.
  - `PX_Cipher` — symmetric block-cipher interface.
- **`mbuf` / `PullFilter` / `PushFilter`** (`mbuf.h`) — chained
  streaming buffers for PGP packet processing.
- **`PGP_Context`** (`pgp.h`) — OpenPGP encryption / decryption
  state machine: session keys, S2K, MDC, compression, armor.

## 5. SQL surface

Defined in `pgcrypto--1.3.sql` + upgrade scripts. Major categories:

- `digest(data, type)` / `digest(data text, type text)` — hashes
  (`md5`, `sha1`, `sha224`, `sha256`, `sha384`, `sha512`).
- `hmac(data, key, type)` — keyed HMAC.
- `encrypt(data, key, type)` / `decrypt(data, key, type)` /
  `encrypt_iv` / `decrypt_iv` — symmetric block ciphers
  (`aes-cbc/pkcs`, `aes-ecb/none`, `bf-cbc/pkcs`, etc.).
- `crypt(password text, salt text)` / `gen_salt(type, [iter_count])` —
  Unix-style password hashing.
- `gen_random_bytes(n)` / `gen_random_uuid()` — CSPRNG.
- `pgp_sym_encrypt`, `pgp_sym_decrypt`, `pgp_pub_encrypt`,
  `pgp_pub_decrypt`, `pgp_key_id`, `armor`, `dearmor` — PGP.

## 6. Invariants and gotchas

- **[INV-1] `volatile` is wrong on most pgcrypto fns.** They are
  `IMMUTABLE` from SQL's perspective (deterministic for fixed input)
  EXCEPT `gen_random_bytes`, `gen_random_uuid`, `crypt(_, gen_salt)`
  patterns where the salt is RNG-derived. Check `provolatile` in
  the install SQL when adding a new SQL function.
- **[INV-2] Don't `palloc` the secret material across error
  boundaries.** Memory contexts are released on `ereport(ERROR)`
  but key material can survive in the freelists. The `px.c`
  free path zeroizes; preserve that contract in any new digest /
  cipher wrapper.
- **OpenSSL FIPS mode** changes which algorithms are available at
  runtime — `px_find_digest("md5")` may return failure on a FIPS
  build. Handle the error path; don't assume MD5 is always
  available.

## 7. Owners (as of 2026-06-12)

- Historical author: Marko Kreen (per the file headers).
- Recent committer activity touches mostly the security-sensitive
  surface (Noah Misch, Daniel Gustafsson, Heikki Linnakangas).
- Persona drivers (`knowledge/personas/`): `noah-misch.md` for
  security review reflexes; `daniel-gustafsson.md` for OpenSSL +
  cleanup-path discipline.

## 8. Local reviewer reflexes

- Any new SQL-callable digest or cipher: cite the PX descriptor's
  init/update/finish discipline; confirm error path frees state.
- Any new RNG callsite: never use `random()` / `arc4random` —
  always go through `px_get_random_bytes`.
- Any new PGP-touching code: trace through the `mbuf` chain;
  filters are reference-counted via `pullf_create` / `pushf_create`.
- Trusted-extension boundary: pgcrypto exposes
  cryptographic primitives — be doubly careful with any SQL that
  could leak side-channel info (timing, error-message-shape).


## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**25 files.**

| File |
|---|
| [`contrib/pgcrypto/crypt-blowfish`](../files/contrib/pgcrypto/crypt-blowfish.md) |
| [`contrib/pgcrypto/crypt-des`](../files/contrib/pgcrypto/crypt-des.md) |
| [`contrib/pgcrypto/crypt-gensalt`](../files/contrib/pgcrypto/crypt-gensalt.md) |
| [`contrib/pgcrypto/crypt-md5`](../files/contrib/pgcrypto/crypt-md5.md) |
| [`contrib/pgcrypto/crypt-sha`](../files/contrib/pgcrypto/crypt-sha.md) |
| [`contrib/pgcrypto/mbuf`](../files/contrib/pgcrypto/mbuf.md) |
| [`contrib/pgcrypto/openssl`](../files/contrib/pgcrypto/openssl.md) |
| [`contrib/pgcrypto/pgcrypto`](../files/contrib/pgcrypto/pgcrypto.md) |
| [`contrib/pgcrypto/pgp`](../files/contrib/pgcrypto/pgp.md) |
| [`contrib/pgcrypto/pgp-armor`](../files/contrib/pgcrypto/pgp-armor.md) |
| [`contrib/pgcrypto/pgp-cfb`](../files/contrib/pgcrypto/pgp-cfb.md) |
| [`contrib/pgcrypto/pgp-compress`](../files/contrib/pgcrypto/pgp-compress.md) |
| [`contrib/pgcrypto/pgp-decrypt`](../files/contrib/pgcrypto/pgp-decrypt.md) |
| [`contrib/pgcrypto/pgp-encrypt`](../files/contrib/pgcrypto/pgp-encrypt.md) |
| [`contrib/pgcrypto/pgp-info`](../files/contrib/pgcrypto/pgp-info.md) |
| [`contrib/pgcrypto/pgp-mpi`](../files/contrib/pgcrypto/pgp-mpi.md) |
| [`contrib/pgcrypto/pgp-mpi-openssl`](../files/contrib/pgcrypto/pgp-mpi-openssl.md) |
| [`contrib/pgcrypto/pgp-pgsql`](../files/contrib/pgcrypto/pgp-pgsql.md) |
| [`contrib/pgcrypto/pgp-pubdec`](../files/contrib/pgcrypto/pgp-pubdec.md) |
| [`contrib/pgcrypto/pgp-pubenc`](../files/contrib/pgcrypto/pgp-pubenc.md) |
| [`contrib/pgcrypto/pgp-pubkey`](../files/contrib/pgcrypto/pgp-pubkey.md) |
| [`contrib/pgcrypto/pgp-s2k`](../files/contrib/pgcrypto/pgp-s2k.md) |
| [`contrib/pgcrypto/px`](../files/contrib/pgcrypto/px.md) |
| [`contrib/pgcrypto/px-crypt`](../files/contrib/pgcrypto/px-crypt.md) |
| [`contrib/pgcrypto/px-hmac`](../files/contrib/pgcrypto/px-hmac.md) |

<!-- /files-owned:auto -->

## Cross-references

- `.claude/skills/fmgr-and-spi/SKILL.md` — SQL-callable C-function conventions.
- `.claude/skills/extension-development/SKILL.md` — `.control` file + trusted-extension policy.
- `.claude/skills/error-handling/SKILL.md` — error path that must not leak key material.
- `.claude/skills/catalog-conventions/SKILL.md` — `provolatile` choice for crypto functions.
- `doc/src/sgml/pgcrypto.sgml` — user-facing reference.
- RFC 4880 — OpenPGP message format (basis for the `pgp_*` family).
