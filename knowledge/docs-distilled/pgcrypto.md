---
source_url: https://www.postgresql.org/docs/current/pgcrypto.html
fetched_at: 2026-07-15T20:50:00Z
anchor_sha: 8f71f64deee6
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.26 pgcrypto — cryptographic functions"
maps_to_skill: [extension-development, fmgr-and-spi, error-handling]
---

# Docs distilled — pgcrypto (hashing, password crypt, PGP, raw ciphers)

The largest SQL-callable-C contrib in the tree and the reference implementation
behind "expose OpenSSL to SQL safely". Four function families — general
hashing, adaptive password hashing, PGP messages, and raw block ciphers — plus
a small CSPRNG surface. **Requires OpenSSL to build at all**; a subset of
primitives also has a PG-builtin path gated by a GUC.

## Non-obvious claims

- **Won't install without OpenSSL.** The whole module fails to build if PG was
  configured without OpenSSL. On OpenSSL 3.0+, DES/Blowfish need the *legacy
  provider* enabled in `openssl.cnf` or those algorithms error at runtime.
  [from-docs]
- **`digest(data, type)` / `hmac(data, key, type)` return `bytea`** — hex it
  with `encode()`. Algorithms `md5, sha1, sha224, sha256, sha384, sha512` plus
  any OpenSSL-registered digest. HMAC hashes keys longer than the block size
  first. [from-docs]
- **`crypt()` + `gen_salt()` are deliberately slow and self-describing** — the
  salt encodes the algorithm and cost, so verification just re-runs
  `crypt(candidate, stored_hash)` and compares. Algorithm/limit table
  (max-password-len, salt-bits, adaptive?): `bf` 72/128/yes, `sha256crypt` &
  `sha512crypt` unlimited/up-to-32/yes, `md5` unlimited/48/no, `xdes` 8/24/yes,
  `des` 8/12/no. [from-docs]
- **`gen_salt()` iteration bounds** — `bf` default 6 (4–31), `xdes` default 725
  (must be **odd**, 1–16777215), `sha256crypt`/`sha512crypt` default 5000
  (1000–999999999). The docs explicitly warn the **5000 default for the
  sha*crypt schemes is too low for modern hardware** — pick a higher count.
  [from-docs]
- **Builtin-crypto GUC gates `crypt()`/`gen_salt()`.**
  `pgcrypto.builtin_crypto_enabled` is an enum GUC (`on`/`off`/`fips`) defined at
  `source/contrib/pgcrypto/pgcrypto.c:70`, default `BC_ON`
  (`pgcrypto.c:62`). `fips` disables the builtin path when OpenSSL is in FIPS
  mode; `fips_mode()` reports that state. [verified-by-code]
- **`gen_random_bytes(count)` is hard-capped at 1024 bytes.**
  `pgcrypto.c:462` — `if (len < 1 || len > 1024)` errors out, to avoid draining
  the kernel randomness pool in one call. [verified-by-code]
- **`gen_random_uuid()` is now a thin shim to core** (v4), kept for
  back-compat; core `gen_random_uuid()` exists without pgcrypto. [from-docs]
- **PGP: symmetric (`pgp_sym_encrypt/decrypt`) and public-key
  (`pgp_pub_encrypt/decrypt`)**, plus `armor`/`dearmor` (base64 + CRC) and
  `pgp_armor_headers`. Options string tunes `cipher-algo` (default **aes128**),
  `compress-algo` (default 0/none; ZIP/ZLIB need build-time zlib), `s2k-mode`
  (default 3 = salted+iterated), `s2k-digest-algo` (default sha1), `unicode-mode`.
  **Limitations: no signing, no master-key, no multiple subkeys.** [from-docs]
- **Raw `encrypt/decrypt[_iv]` are discouraged.** Type string is
  `algo[-mode][/pad:pad]` — `bf`/`aes`, modes `cbc`(default)/`cfb`/`ecb`,
  padding `pkcs`(default)/`none`. The docs list four foot-guns: the user key is
  used *directly* as the cipher key, no integrity check, no IV management, no
  text handling. Prefer the PGP functions. [from-docs]
- **Side-channel + cleartext caveats.** Data travels in clear between client and
  pgcrypto, so a local socket or SSL is required to keep keys off the wire; and
  decryption time varies with ciphertext (not side-channel resistant). Any NULL
  argument yields NULL — a silent-failure risk in careless key handling.
  [from-docs]
- **Trusted extension** — installable by a non-superuser with `CREATE` on the
  database. [from-docs]

## Links into corpus

- `[[docs-distilled/uuid-ossp.md]]` — the other UUID surface; pgcrypto only does
  v4 (shim), uuid-ossp adds v1/v3/v5. Core now covers v4 + v7.
- `[[docs-distilled/sslinfo.md]]` — companion "OpenSSL exposed to SQL" module;
  both are `--with-ssl=openssl`-gated.
- `[[docs-distilled/runtime-config-custom.md]]` — `pgcrypto.builtin_crypto_enabled`
  is a `DefineCustomEnumVariable` example (extension GUC with an enum table).
- `extension-development` / `fmgr-and-spi` skills — a large, real example of an
  OpenSSL-linked contrib exposing dozens of `PG_FUNCTION_INFO_V1` scalar
  functions plus a custom enum GUC.
