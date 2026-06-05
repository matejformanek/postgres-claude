# pgp-decrypt.c

## One-line summary

The OpenPGP decryption packet parser and filter chain: parses old/new
packet headers + partial-length streams, handles two encrypted-data
variants (`SYMENCRYPTED_DATA` legacy and `SYMENCRYPTED_DATA_MDC`
modern), drives `parse_symenc_sesskey` and `pgp_parse_pubenc_sesskey`,
runs CFB decryption, verifies the SHA-1 MDC, and **deliberately delays
all error reporting to the very end** to deny attackers a
chosen-ciphertext oracle.

## Public API / entry points

- `pgp_decrypt(PGP_Context *, MBuf *msrc, MBuf *mdst)` —
  `source/contrib/pgcrypto/pgp-decrypt.c:1093` [verified-by-code]. Top
  level for symmetric and public-key decrypt.
- `pgp_parse_pkt_hdr(PullFilter *, tag, len_p, allow_ctx)` —
  `source/contrib/pgcrypto/pgp-decrypt.c:129`. Reused by `pgp-info.c`
  and `pgp-pubkey.c`.
- `pgp_create_pkt_reader(...)` —
  `source/contrib/pgcrypto/pgp-decrypt.c:223`. Wraps a packet body in
  a pull filter that knows the length / stream rules.
- `pgp_skip_packet`, `pgp_expect_packet_end` — packet-tail handling
  used by every parser.
- `pgp_decrypt_filter` — exported PullFilter spec that applies
  `pgp_cfb_decrypt` to bytes pulled from below.

## Key invariants

- `MAX_CHUNK = 16 * 1024 * 1024` (16 MiB) per packet chunk —
  `source/contrib/pgcrypto/pgp-decrypt.c:49`. Both `parse_new_len`
  (`:84`) and `parse_old_len` (`:118`) reject anything larger.
- Old packet format (high bit 0x40 = 0): 4 length encodings (0, 1, 2
  bytes or indeterminate-context).
- New format (0x40 = 1): single-byte ≤191, 2-byte ≤8 383, 5-byte for
  >=8 384, or partial-length-stream for the "1 << (b & 0x1F)" branch.
  `source/contrib/pgcrypto/pgp-decrypt.c:52-92`.
- `parse_symenc_data` (tag 9, no MDC) sets `disable_mdc = 1` in the
  ctx and uses CFB resync=1; `parse_symenc_mdc_data` (tag 18) uses
  resync=0 + mandatory MDC verification.
  `source/contrib/pgcrypto/pgp-decrypt.c:978-1009,1011-1058,1149,1161`.
- The "quick check" prefix: `prefix_init` reads `bs+2` bytes, checks
  `buf[bs-2]==buf[bs] && buf[bs-1]==buf[bs+1]`. Mismatch sets
  `ctx->corrupt_prefix = 1` (DOES NOT immediately error),
  `source/contrib/pgcrypto/pgp-decrypt.c:267-272` [verified-by-code].
- MDC packet must be tag 19 with header bytes `0xD3 0x14`,
  `source/contrib/pgcrypto/pgp-decrypt.c:470-474`. MDC packet last in
  stream; data-after-MDC is corruption.
- `mdcbuf_filter` is the **combined** pkt-reader + MDC-hash for the
  context-length variant inside SYMENCRYPTED_DATA_MDC — buffers 22
  bytes ahead so MDC trailer can be peeled off the stream.
  `source/contrib/pgcrypto/pgp-decrypt.c:432-584`.

## Notable internals — the DELAYED-ERROR pattern

`pgp_decrypt`'s tail block (`source/contrib/pgcrypto/pgp-decrypt.c:1180-1212`)
is the most security-critical lines in pgcrypto. The comment is worth
quoting verbatim:

> Report a failure of the prefix_init() "quick check" now, rather than
> upon detection, to hinder timing attacks. pgcrypto is not generally
> secure against timing attacks, but this helps.
> ...
> Code interpreting purportedly-decrypted data prior to this stage
> shall report no error other than PXE_PGP_CORRUPT_DATA. (PXE_BUG is
> okay so long as it remains unreachable.) This ensures that an
> attacker able to choose a ciphertext and receive a corresponding
> decryption error message cannot use that oracle to gather clues
> about the decryption key. See "An Attack on CFB Mode Encryption As
> Used By OpenPGP" by Serge Mister and Robert Zuccherato.

Concretely:
- `corrupt_prefix` flag set by `prefix_init` but error returned only
  at end (line 1187).
- `unsupported_compr` set when bzip2 seen in `parse_compressed_data`,
  returned only at end (line 1208).
- `unexpected_binary` set when `parse_literal_data` sees binary in
  text mode (line 789); returned only at end (line 1210).
- The deliberate `disable_mdc = 1` on legacy tag-9 (line 1149) means
  MDC checking is skipped without erroring — instead the prefix-check
  oracle is the sole (weak) integrity signal, and even that is
  delayed.

## Notable internals — `MDCBuf` ring

`MDCBufData` (`:432-444`) is a ring of 8 KiB plus a 22-byte trailing
"MDC suspect" buffer. The trick: we don't know if a given chunk
contains data or the trailing MDC packet until we've seen 22 bytes
beyond it. So `mdcbuf_refill`
(`source/contrib/pgcrypto/pgp-decrypt.c:505-546`) reads new data,
treats the last 22 bytes as "possibly MDC", and rolls them forward.
On EOF, those 22 bytes are validated as the MDC packet:
`0xD3 || 0x14 || SHA1(20)`.

## Notable internals — `process_data_packets`

`source/contrib/pgcrypto/pgp-decrypt.c:872-975`. Iterates inner
packets after CFB decryption. Allowed inner tags: `LITERAL_DATA`,
`COMPRESSED_DATA` (only if `allow_compr`), `MDC` (only if
`need_mdc`). Anything else → `PXE_PGP_CORRUPT_DATA`. Enforces
"compressed data must be alone, MDC must be last".

## Crypto trust boundary / Phase D surface

- **The single most important security property in pgcrypto** lives
  in `pgp_decrypt` lines 1180-1212. The delayed-error pattern is
  intentional and well-commented. Maintainers MUST NOT add early
  `ereport`s in the inner decryption paths.
  [ISSUE-audit-gap: no unit test asserts the delayed-error invariant
  (e.g. crafted ciphertext A + crafted ciphertext B differing only in
  prefix_init outcome should produce identical user-visible error and
  similar timing); regression risk on future patches (maybe)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:1180-1212`.
- **MDC IS mandatory** for SYMENCRYPTED_DATA_MDC packets:
  `process_data_packets` (line 969) sets res = corrupt-data if
  `need_mdc && !got_mdc && !use_mdcbuf_filter`. `parse_symenc_mdc_data`
  passes `NEED_MDC` (line 1045). So tag-18 ciphertexts without trailing
  MDC are rejected. Good.
- **Legacy SYMENCRYPTED_DATA (tag 9) skips MDC** — `parse_symenc_data`
  passes `NO_MDC` to `process_data_packets` (line 998). This is the
  EFAIL surface. Mitigated only by the delayed-error pattern.
  [ISSUE-security: tag-9 ciphertexts (no MDC) accepted on decrypt;
  only mitigation is delayed-error reporting on prefix_init failure;
  CFB-malleability attack surface (likely)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:1141-1152`.
- **`MAX_CHUNK = 16 MiB`** per packet chunk. Total ciphertext via
  partial-length streams can be much larger. No global ceiling — a
  multi-GB encrypted blob would be processed.
- **MDC SHA-1 collision** is theoretical (2017 SHAttered showed SHA-1
  collision is feasible). For MDC integrity, what matters is
  second-preimage resistance, which is still ~2^160 work for SHA-1.
  Acceptable but ages poorly.
  [ISSUE-defense-in-depth: MDC uses SHA-1; modern OpenPGP (SEIPD v2,
  RFC 9580) uses HMAC-SHA-256 or AEAD; pgcrypto stuck on SHA-1 MDC
  (maybe)] — `source/contrib/pgcrypto/pgp-decrypt.c:329`.
- **Compressed-then-encrypted is allowed inside encrypted body**:
  `parse_symenc_*_data` → `process_data_packets` allows
  `COMPRESSED_DATA` → `parse_compressed_data` → `pgp_decompress_filter`
  → THEN `process_data_packets(... NO_COMPR, NO_MDC)`. The
  decompressor sits BETWEEN the decryptor and the literal-data
  reader. **This is the decompression bomb surface from
  `pgp-compress.md`**: attacker-controlled compressed data after
  decryption.
- **`decrypt_key` (line 591)** decrypts a separate session key when
  the symenc-sesskey packet has additional bytes after the S2K spec.
  Uses CFB resync=0. The S2K-derived key encrypts the actual
  session key. `cipher_algo` is the FIRST decrypted byte.
- **`parse_symenc_sesskey` reads `s2k.iter` from ciphertext**
  (`source/contrib/pgcrypto/pgp-s2k.c:270`), then runs S2K with that
  iter count. **Attacker controls iter byte** → ~65M digest ops per
  call. **Confirmed exploitable from SQL via `pgp_sym_decrypt(craft,
  pw)`.**
- **`mdc_finish` does `memcmp` of SHA-1**, non-constant-time
  (`source/contrib/pgcrypto/pgp-decrypt.c:383`). 20-byte memcmp
  timing leak is below noise for any practical attacker, but
  belt-and-braces would use a constant-time compare.
- **`parse_literal_data` text-mode binary detection sets
  `unexpected_binary`** but does NOT immediately error — propagation
  again deferred to `pgp_decrypt` finalization. Good.
- **`copy_crlf` handles split CR at chunk boundary** via `*got_cr`
  state, `source/contrib/pgcrypto/pgp-decrypt.c:693-741`. Subtle —
  text-mode CRLF normalization while streaming.

## Cross-references

- `pgp-cfb.md` — `pgp_decrypt_filter` runs `pgp_cfb_decrypt`.
- `pgp-s2k.md` — `parse_symenc_sesskey` runs `pgp_s2k_read` +
  `pgp_s2k_process` with attacker-controlled `iter`.
- `pgp-pubdec.md` — `pgp_parse_pubenc_sesskey` is the parallel
  asymmetric path.
- `pgp-compress.md` — invoked for inner compressed packets;
  decompression-bomb surface.
- Mister-Zuccherato 2005, EFAIL 2018 — the attack history this code
  is defending against.

## Issues spotted

- [ISSUE-security: tag-9 legacy (no-MDC) ciphertexts still accepted;
  delayed-error mitigation only (likely)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:1141-1152`.
- [ISSUE-security: attacker-controlled S2K iter byte in
  `parse_symenc_sesskey` → ~65M digest ops per `pgp_sym_decrypt`
  call; DoS via repeated calls (likely)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:642-647` +
  `pgp-s2k.c:270`.
- [ISSUE-security: decompression bomb via inner COMPRESSED_DATA
  packet; no output-size cap (critical)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:834-843` +
  `pgp-compress.c:278-310`.
- [ISSUE-defense-in-depth: MDC uses SHA-1; modern AEAD / HMAC-SHA-256
  unavailable (maybe)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:329`.
- [ISSUE-audit-gap: no regression test asserts the delayed-error
  invariant; future patches could accidentally introduce a
  timing/error oracle (maybe)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:1180-1212`.
- [ISSUE-correctness: `mdc_finish` memcmp non-constant-time;
  theoretical 20-byte timing leak (nit)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:383`.
- [ISSUE-correctness: `MAX_CHUNK=16 MiB` per chunk but no global
  ceiling on total decrypted-output size; partial-length streams
  enable arbitrarily large outputs (maybe)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:49`.
- [ISSUE-error-handling: `decrypt_key` (line 591) ignores return
  value of `pgp_cfb_decrypt` (line 602, 606); `pgp_cfb_decrypt`
  always returns 0 so practically OK, but signature suggests it can
  fail (nit)] — `source/contrib/pgcrypto/pgp-decrypt.c:602-606`.
- [ISSUE-memory: `tmpbuf[PGP_MAX_KEY+2]` and `tmpbuf[20]` stack
  buffers hold ciphertext / hash briefly; `px_memset` scrubs them on
  the success path but not on every early-return path (nit)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:250,628,689,348`.
- [ISSUE-documentation: `disable_mdc = 1` set silently on tag-9 (line
  1149); no log/notice that user is on the EFAIL-prone path (maybe)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:1149`.
