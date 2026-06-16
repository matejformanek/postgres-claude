# pgp-encrypt.c

## One-line summary

Build and emit a complete OpenPGP encrypted message: assemble the filter
push-chain (encrypt → optional MDC-hash → optional compress → literal-data
packetizer → optional CRLF text mode), generate the random session key,
write the symmetric-key or public-key session-key packet, then push
plaintext through. Backs SQL `pgp_sym_encrypt` / `pgp_pub_encrypt`.

## Public API / entry points

- `pgp_encrypt(PGP_Context *, MBuf *src, MBuf *dst)` —
  `source/contrib/pgcrypto/pgp-encrypt.c:599` [verified-by-code].
- `pgp_create_pkt_writer(PushFilter *dst, int tag, PushFilter **)` —
  general partial-length-stream packet writer,
  `source/contrib/pgcrypto/pgp-encrypt.c:311`.

## Key invariants

- Must have either `sym_key` or `pub_key` set; else
  `PXE_ARGUMENT_ERROR`,
  `source/contrib/pgcrypto/pgp-encrypt.c:610-611` [verified-by-code].
- When `ctx->disable_mdc == 0` (default), writes packet tag
  `SYMENCRYPTED_DATA_MDC` (18) + a leading `ver=1` byte, CFB with
  `resync=0`, plus SHA-1 MDC trailer.
  `source/contrib/pgcrypto/pgp-encrypt.c:166-175,462-465` [verified-by-code].
- When `disable_mdc == 1`, writes legacy tag `SYMENCRYPTED_DATA` (9),
  CFB with `resync=1`, no MDC. (The footgun mode.)
- The 16/22-byte prefix: `bs` random bytes + 2 bytes that repeat the
  last 2 of the random prefix, `source/contrib/pgcrypto/pgp-encrypt.c:480-493`.
  Forms the OpenPGP "quick check" (cf. `prefix_init` in
  `pgp-decrypt.c`).
- Session-key derivation:
  - Symmetric-only + `use_sess_key=0` → session key = S2K-derived key
    (default).
  - Symmetric-only + `use_sess_key=1` → fresh random session key
    encrypted with S2K key.
  - Public-key → always fresh random session key.
  `source/contrib/pgcrypto/pgp-encrypt.c:577-593` [verified-by-code].

## Notable internals

- **Filter chain assembled top-down**:
  `MBuf writer → key-packet writer (one-shot) → enc-data packet shell →
  encrypt_filter → mdc_filter? → write_prefix → compress_filter? →
  litdata_packet (pkt_stream_filter) → crlf_filter?`.
  Push direction = the user pushes plaintext into `pf`, which is the
  outermost wrapper. `source/contrib/pgcrypto/pgp-encrypt.c:613-691`.
- **`pkt_stream_filter`** writes RFC 4880 partial-length packets in
  16 KiB (`STREAM_BLOCK_SHIFT=14`) blocks until the last block which
  uses normal-length encoding. `source/contrib/pgcrypto/pgp-encrypt.c:232-308`.
- **`mdc_init`** loads SHA-1; `mdc_write` updates it on every push;
  `mdc_flush` writes the MDC packet (`0xD3 0x14 || SHA1(20)`) at the
  end. `source/contrib/pgcrypto/pgp-encrypt.c:91-144`.
- **`init_litdata_packet`** writes the literal-data header (`type ||
  name_len=0 || time(4B)`) inline. `type` = `'t'` (text), `'u'`
  (unicode-text), or `'b'` (binary).
  `source/contrib/pgcrypto/pgp-encrypt.c:373-423`.
- **`symencrypt_sesskey`** for the symmetric-key-encrypted-session-key
  packet: CFB-encrypt `cipher_algo || sess_key` with the S2K-derived
  key. CFB resync=0. `source/contrib/pgcrypto/pgp-encrypt.c:500-517`.

## Crypto trust boundary / Phase D surface

- **MDC ON by default** — verified at `def_disable_mdc = 0` in pgp.c.
  All new ciphertexts use SYMENCRYPTED_DATA_MDC. Good.
- **`disable_mdc=1` is still reachable** via SQL
  `pgp_sym_encrypt('data', 'pw', 'disable-mdc=1')`. Produces legacy
  ciphertext with no integrity. **A real footgun.**
  [ISSUE-defense-in-depth: `disable-mdc=1` SQL option still functional;
  produces ciphertext vulnerable to EFAIL/Mister-Zuccherato; could be
  deprecated with WARNING (likely)] —
  `source/contrib/pgcrypto/pgp-encrypt.c:462-465` and
  `pgp-pgsql.c:175-176`.
- **`pg_strong_random` for session key + prefix.** `init_sess_key`
  fails encryption if RNG returns 0,
  `source/contrib/pgcrypto/pgp-encrypt.c:583-585`. `write_prefix`
  same, line 485-486. Good.
- **`px_memset(prefix, 0, bs+2)` on the random prefix** after write,
  `source/contrib/pgcrypto/pgp-encrypt.c:492` [verified-by-code]. Good.
- **`px_memset(pkt, 0, pktlen)`** on the symenc-sesskey packet buffer,
  `source/contrib/pgcrypto/pgp-encrypt.c:554`. Good.
- **`px_memset(pkt, 0, 2+MDC_DIGEST_LEN)`** on the MDC packet after
  write, `source/contrib/pgcrypto/pgp-encrypt.c:130`. Good.
- **No scrub of `EncStat.buf[ENCBUF]`** between chunks — only at free
  (`source/contrib/pgcrypto/pgp-encrypt.c:220`). Holds CFB ciphertext
  briefly — not secret, but consistent hygiene would scrub.
- **Compress-then-encrypt** is the order set up here
  (`source/contrib/pgcrypto/pgp-encrypt.c:668-675`, compressor is
  outermost). CRIME-style attack surface noted in `pgp-compress.md`.
- **CRLF conversion happens BEFORE encryption** (crlf_filter is
  outermost). No issue but worth noting for text-mode round-trip
  reasoning.
- **No explicit_bzero in stack buffer of `write_symenc_sesskey`** —
  `pkt[256]` is `px_memset`'d but the function-local stack frame
  could leak via subsequent allocations using the same stack region.
  Minor.

## Cross-references

- `pgp-cfb.md` — `pgp_cfb_create(..., resync=ctx->disable_mdc ? 1 : 0)`.
- `pgp-compress.md` — `pgp_compress_filter` injection point.
- `pgp-pubenc.md` — when `pub_key` set, calls `pgp_write_pubenc_sesskey`.
- `pgp-s2k.md` — `init_s2k_key` calls `pgp_s2k_fill` + `pgp_s2k_process`.
- `pgp-decrypt.md` — matching reverse-direction filter chain.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-defense-in-depth: `disable-mdc=1` SQL option produces
  no-MDC legacy ciphertext (EFAIL-vulnerable); no WARNING emitted
  (likely)] — `source/contrib/pgcrypto/pgp-encrypt.c:462-465` +
  `pgp-pgsql.c:175-176`.
- [ISSUE-defense-in-depth: compress-then-encrypt is the chain order;
  CRIME-style attack surface when user opts in to compression
  (likely)] — `source/contrib/pgcrypto/pgp-encrypt.c:668-675`.
- [ISSUE-memory: `EncStat.buf` not scrubbed between chunks (nit)] —
  `source/contrib/pgcrypto/pgp-encrypt.c:153-154,213-221`.
- [ISSUE-memory: `pkt[256]` stack buffer in `write_symenc_sesskey`
  contains plaintext session-key-cipher_algo briefly; `px_memset`
  scrubs it, but compiler could DCE the memset (nit)] —
  `source/contrib/pgcrypto/pgp-encrypt.c:523,554`. Mitigated by
  `px_memset` being a non-inlinable function call.
- [ISSUE-correctness: `init_sess_key` calls `memcpy(sess_key,
  s2k.key, s2k.key_len)` when not using a separate session key; if
  s2k.key_len != cipher_key_len somehow, would copy wrong length.
  In practice `pgp_s2k_process` sets `s2k.key_len =
  pgp_get_cipher_key_size(cipher)`, so they match. (nit)] —
  `source/contrib/pgcrypto/pgp-encrypt.c:588-589`.
- [ISSUE-error-handling: `pushf_flush` failure paths in the chain are
  propagated, but `pushf_free_all(pf)` at `out:` swallows further
  errors. Standard pattern. (nit)] —
  `source/contrib/pgcrypto/pgp-encrypt.c:700-702`.
