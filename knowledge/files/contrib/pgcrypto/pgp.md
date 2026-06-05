# pgp.c / pgp.h

## One-line summary

OpenPGP context lifecycle (alloc/init/free), algorithm-code tables, default
parameters, and shared structs (`PGP_Context`, `PGP_S2K`, `PGP_PubKey`,
`PGP_MPI`) plus the public-API entry-point declarations consumed by every
other `pgp-*.c` file. Source pin `4b0bf0788b0`. Covers `pgp.c` (360 lines)
and `pgp.h` (326 lines).

## Public API / entry points

- `pgp_init(PGP_Context **)` — palloc0 a context with the static defaults,
  `source/contrib/pgcrypto/pgp.c:189` [verified-by-code].
- `pgp_free(PGP_Context *)` — `px_memset` then `pfree`; frees `pub_key` if
  owned, `source/contrib/pgcrypto/pgp.c:213` [verified-by-code]. Note the
  context is wiped, but transient session-key copies in encrypted-data filter
  state live on stack/MemoryContext and are scrubbed separately.
- `pgp_set_symkey(PGP_Context *, const uint8 *, int)` — stores POINTER (not
  copy), `source/contrib/pgcrypto/pgp.c:353` [verified-by-code]. Caller owns
  the buffer.
- `pgp_set_cipher_algo / pgp_set_s2k_*` — see `source/contrib/pgcrypto/pgp.c:243-336`.
- `pgp_set_s2k_count(ctx, count)` — bounded `1024 <= count <= 65011712`,
  `source/contrib/pgcrypto/pgp.c:263-271` [verified-by-code].
- `pgp_disable_mdc(ctx, disable)` — flips MDC off (legacy mode),
  `source/contrib/pgcrypto/pgp.c:222` [verified-by-code].
- The header declares the cross-file contract: `pgp_encrypt`, `pgp_decrypt`,
  `pgp_s2k_*`, `pgp_cfb_*`, `pgp_armor_*`, `pgp_compress_*`,
  `pgp_rsa_*`/`pgp_elgamal_*` MPI ops, `pgp_get_keyid`.
  `source/contrib/pgcrypto/pgp.h:239-326` [verified-by-code].

## Key invariants

- Default cipher is `PGP_SYM_AES_128` (`source/contrib/pgcrypto/pgp.c:40`)
  [verified-by-code]. Three-DES, CAST5, Blowfish, AES-192/256, Twofish are
  selectable; **IDEA / SAFER / DES_SK** enum values are listed but absent
  from `cipher_list`, so they cannot be used as the chosen algorithm — only
  *parsed* on input. `source/contrib/pgcrypto/pgp.c:79-90` and
  `source/contrib/pgcrypto/pgp.h:75-88`.
- Default S2K mode is `PGP_S2K_ISALTED` (iterated+salted),
  `source/contrib/pgcrypto/pgp.c:42`. Default digest is SHA-1
  (`source/contrib/pgcrypto/pgp.c:44`) — historically inevitable for OpenPGP
  v4 key fingerprints but still SHA-1.
- `PGP_MAX_KEY=32`, `PGP_MAX_BLOCK=32`, `PGP_MAX_DIGEST=64`,
  `PGP_S2K_SALT=8`. `source/contrib/pgcrypto/pgp.h:112-115` [verified-by-code].
- `s2k_decode_count(c) = (16 + (c & 15)) << ((c >> 4) + 6)` per RFC 4880
  3.7.1.3 — single-byte `iter` encodes 1 024 … 65 011 712 iterations.
  `source/contrib/pgcrypto/pgp.h:176-177` [verified-by-code].
- Defaults: `def_disable_mdc = 0` (MDC ON), `def_use_sess_key = 0`,
  `def_compress_algo = PGP_COMPR_NONE`, `def_compress_level = 6`.
  `source/contrib/pgcrypto/pgp.c:45-51` [verified-by-code].
- `PGP_Context.sym_key` is a NON-owning pointer; `sess_key[PGP_MAX_KEY]` is
  an inline 32-byte buffer cleared on `pgp_free` via `px_memset`,
  `source/contrib/pgcrypto/pgp.h:171,165` and
  `source/contrib/pgcrypto/pgp.c:217` [verified-by-code].

## Notable internals

- `PGP_Context` keeps both *attempted* (`disable_mdc`, `use_sess_key`) and
  *parsed* (`mdc_checked`, `corrupt_prefix`, `unsupported_compr`,
  `unexpected_binary`, `in_mdc_pkt`) flags — these are accumulated during a
  decrypt pass and only finally inspected by `pgp_decrypt`, the deliberate
  "delay-error-to-end" pattern documented in `pgp-decrypt.c:1181-1206`
  [from-comment].
- `digest_list` allows `md5`, `sha1`, `sha-1`, `ripemd160`, `sha256/384/512`
  — both legacy MD5 and SHA-1 selectable from SQL via `s2k-digest-algo=md5`.
  `source/contrib/pgcrypto/pgp.c:68-77` [verified-by-code].
- Algorithm-code lookups are O(N) linear scans of `cipher_list` /
  `digest_list`. Tables are short (~9 / ~7 entries) so this is fine, but no
  hash dispatch. `source/contrib/pgcrypto/pgp.c:92-134` [verified-by-code].

## Crypto trust boundary / Phase D surface

- **Defaults are reasonable for 2026**: AES-128, ISALTED S2K, MDC enabled.
  But `disable_mdc=1` and legacy ciphers (3DES, CAST5, Blowfish) are still
  reachable via SQL `cipher-algo=3des` / `disable-mdc=1` args.
  [ISSUE-defense-in-depth: legacy ciphers (3DES, CAST5, Blowfish) selectable
  by user-supplied algo string (maybe)] — `source/contrib/pgcrypto/pgp.c:80-83`.
- **S2K iteration count NOT capped on read.** The encoded `iter` byte
  decodes to up to 65 011 712 iterations (`source/contrib/pgcrypto/pgp.h:177`).
  `pgp_set_s2k_count` rejects values >65 011 712 on the *encrypt* side
  (`source/contrib/pgcrypto/pgp.c:265-269`), but `pgp_s2k_read` does no
  bounds check on the byte read from ciphertext
  (`source/contrib/pgcrypto/pgp-s2k.c:270`); a ciphertext can request the
  maximum, which is still the RFC-bounded ~65M iterations.
  [ISSUE-defense-in-depth: attacker-supplied S2K count uses full RFC range,
  no SQL-level cap (maybe)] — `source/contrib/pgcrypto/pgp-s2k.c:270`.
- **Defaults `s2k_count = -1`** signals "let `decide_s2k_iter` pick 65 536 …
  262 144 iterations randomly", `source/contrib/pgcrypto/pgp-s2k.c:213-214`
  [verified-by-code]. Modest by 2026 standards (NIST SP 800-132 recommends
  >= 1M for password-derived key wrapping).
  [ISSUE-defense-in-depth: default S2K iteration upper bound (262 144) too
  low for 2026 GPU-cracking economics (maybe)] —
  `source/contrib/pgcrypto/pgp-s2k.c:214`.
- `pgp_free` calls `px_memset(ctx, 0, sizeof *ctx)` *before* `pfree`. Good.
  But a `sym_key` pointer it does NOT own is **not** scrubbed —
  caller-supplied passwords passed via `pgp_set_symkey` remain in palloc'd
  text variants in the SQL layer; see `pgp-pgsql.md` for the wider story.
- `cipher_list` exposes the literal OpenSSL `int_name` (e.g. `"3des-ecb"`)
  for `px_find_cipher`. Pgcrypto-internal lookup, not a string supplied by
  the user, so no injection surface.

## Cross-references

- A11-3 pgcrypto core (px.c, gen_random_bytes) — `pg_strong_random` feeds
  `pgp_s2k_fill` salt and `init_sess_key` session-key bytes.
- A5 `pg_lzcompress` decompression-bomb finding — `pgp-compress.md` notes
  zlib `inflate` has the same uncapped-ratio risk.
- `pgp-decrypt.md` — uses every flag here (`corrupt_prefix`,
  `unsupported_compr`, `unexpected_binary`, `disable_mdc`) at finalization.
- `pgp-s2k.md` — concrete implementation of the three S2K modes referenced
  by `s2k_mode` enum here.

## Issues spotted

- [ISSUE-defense-in-depth: SHA-1 and MD5 still permitted as `s2k-digest-algo`
  via SQL string lookup (maybe)] — `source/contrib/pgcrypto/pgp.c:68-72`.
  No deprecation gate; documented but not removed.
- [ISSUE-audit-gap: `def_s2k_count = -1` falls through to `decide_s2k_iter`'s
  65 536-262 144 range, which is 2009-era GPG default (maybe)] —
  `source/contrib/pgcrypto/pgp.c:43` + `pgp-s2k.c:213`.
- [ISSUE-api-shape: `pgp_set_symkey` stores a non-owning pointer; lifetime
  bound to caller's palloc context, not the `PGP_Context` (nit)] —
  `source/contrib/pgcrypto/pgp.c:357`. Subtle for future maintainers.
- [ISSUE-documentation: `PGP_Context.unsupported_compr` flag's purpose ("has
  bzip2 compression seen during parse") is only obvious from `pgp-decrypt.c`
  cross-reference (nit)] — `source/contrib/pgcrypto/pgp.h:158`.
