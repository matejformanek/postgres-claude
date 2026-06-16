# pgp-compress.c

## One-line summary

PushFilter/PullFilter adapters around zlib `deflate` / `inflate` for ZIP
(raw deflate, `-15` window) and ZLIB (RFC 1950, default window) OpenPGP
compression. Returns `PXE_PGP_UNSUPPORTED_COMPR` when built without
`HAVE_LIBZ`. BZIP2 is *not* implemented (decrypt-side flags it as
`unsupported_compr`, see `pgp-decrypt.c:846-848`).

## Public API / entry points

- `pgp_compress_filter(PushFilter **, PGP_Context *, PushFilter *)` —
  build a push-filter that compresses to `dst`,
  `source/contrib/pgcrypto/pgp-compress.c:185` [verified-by-code].
- `pgp_decompress_filter(PullFilter **, PGP_Context *, PullFilter *)` —
  pull-filter that inflates from `src`,
  `source/contrib/pgcrypto/pgp-compress.c:328` [verified-by-code].
- `#ifdef HAVE_LIBZ` — when off, both functions just return
  `PXE_PGP_UNSUPPORTED_COMPR`,
  `source/contrib/pgcrypto/pgp-compress.c:332-345`.

## Key invariants

- Internal buffer is `ZIP_OUT_BUF = 8192` bytes. Input chunk is
  `ZIP_IN_BLOCK = 8192`. `source/contrib/pgcrypto/pgp-compress.c:45-46`
  [verified-by-code].
- ZIP mode uses `deflateInit2(stream, level, Z_DEFLATED, -15, 8,
  Z_DEFAULT_STRATEGY)` — the `-15` makes raw-deflate, no zlib header.
  `source/contrib/pgcrypto/pgp-compress.c:89-90` [verified-by-code]. ZLIB
  mode uses `deflateInit(stream, level)`.
- Custom zlib alloc hooks `z_alloc`/`z_free` route to `palloc/pfree` —
  zlib allocations land in the current MemoryContext.
  `source/contrib/pgcrypto/pgp-compress.c:57-67` [verified-by-code]. If
  `palloc` ereports OOM, that longjmps out of zlib, leaving zlib state
  inconsistent — but the parent MemoryContext is torn down on error so
  in-flight `z_stream` heap is reclaimed. **HOWEVER**, `inflateEnd`
  /`deflateEnd` will NOT be called, so any OS-level resource zlib held
  (none, in practice) would leak. Pure palloc, so safe.
- `decompress_read` reads at most `len` bytes per call but pulls 8 KiB at
  a time from the source. `source/contrib/pgcrypto/pgp-compress.c:236-310`.
- After `Z_STREAM_END`, the function checks that the underlying packet
  also ended (`pullf_read(src, 1, &tmp)` must return 0), else returns
  `PXE_PGP_CORRUPT_DATA`. `source/contrib/pgcrypto/pgp-compress.c:298-306`
  [verified-by-code].

## Notable internals

- `decompress_init` only succeeds for `PGP_COMPR_ZIP` or `PGP_COMPR_ZLIB`
  — bzip2 is rejected with `PXE_PGP_UNSUPPORTED_COMPR` at the dispatch
  level (`pgp-decrypt.c:846`), so the bzip2 branch here is dead.
- The compress side uses `Z_NO_FLUSH` per chunk and `Z_FINISH` at flush
  time (`source/contrib/pgcrypto/pgp-compress.c:122,152`).
- Decompress side uses `Z_SYNC_FLUSH` if there's more input, `Z_FINISH`
  when input is exhausted (`source/contrib/pgcrypto/pgp-compress.c:277`).
  Comment notes the choice is conservative.

## Crypto trust boundary / Phase D surface

- **DECOMPRESSION BOMB SURFACE — CRITICAL.** A5 found `pg_lzcompress` has
  no maximum-output-ratio check; **`pgp-compress.c` has the same gap.**
  `decompress_read` keeps reading until `Z_STREAM_END`; no ceiling on
  total output bytes vs input bytes. An attacker can craft a tiny PGP
  message (e.g. 10 KB) that decompresses to gigabytes — invoke
  `pgp_sym_decrypt('<10KB encrypted bomb>', 'pw')` and watch the backend
  consume RAM until OOM-killed by the kernel.
  [ISSUE-security: zlib decompression bomb — no output-size cap on
  `inflate`; small ciphertext → multi-GB plaintext; OOM the backend
  (critical)] — `source/contrib/pgcrypto/pgp-compress.c:278-310`. This is
  the highest-severity finding in the entire pgcrypto-PGP sweep.
- **Compression is performed BEFORE encryption** (see
  `pgp-encrypt.c:669-675`, the compressor filter wraps the encryptor in
  the push chain) — this is the CRIME / BREACH side-channel pattern.
  Attacker who controls part of plaintext and observes ciphertext length
  can iteratively guess unknown plaintext (chosen-plaintext attack on
  compression ratio). For `pgp_sym_encrypt` of mixed
  attacker+secret data, this is a real leak.
  [ISSUE-security: compress-then-encrypt enables CRIME-style adaptive
  chosen-plaintext attacks when attacker controls part of plaintext
  (likely)] — `source/contrib/pgcrypto/pgp-encrypt.c:669-675`. Mitigation:
  `compress_algo` default is `PGP_COMPR_NONE`, so the leak only fires if
  the user explicitly opts in via `compress-algo=1` arg.
- **`pullf_read` returns 8 KB at a time** with the buffer pointer owned
  by the source filter. No copy here. Means `decompress_read` and
  `inflate` operate on attacker-controlled bytes — relies on zlib's own
  hardening.
- **Z_BUF_ERROR not handled explicitly.** `inflate` returning anything
  other than `Z_OK` or `Z_STREAM_END` → `PXE_PGP_CORRUPT_DATA`. Good.
- **No explicit `explicit_bzero` on `dec->buf`** — but `px_memset` at free
  (`source/contrib/pgcrypto/pgp-compress.c:318`) covers it. The 8 KB
  buffer briefly holds plaintext on decompress, so this matters.

## Cross-references

- A5 `pg_lzcompress` decompression-bomb finding — same class of issue,
  same uncapped-ratio root cause.
- `pgp-decrypt.md` — `parse_compressed_data` invokes
  `pgp_decompress_filter`; bzip2 path triggers `unsupported_compr` flag.
- `pgp-encrypt.md` — `init_compress` invokes `pgp_compress_filter`.
- zlib `inflate` upstream — relied on for buffer-bounds safety on the
  decompressor side.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: zlib decompression bomb, no max-output cap on
  `pgp_sym_decrypt(compressed_blob, pw)`; small input → huge output;
  backend OOM (critical)] —
  `source/contrib/pgcrypto/pgp-compress.c:278-310`.
- [ISSUE-security: compress-then-encrypt enables CRIME-style attacks when
  user opts in to compression with attacker-influenced plaintext
  (likely)] — `source/contrib/pgcrypto/pgp-encrypt.c:669-675`.
- [ISSUE-correctness: bzip2 branch of `decompress_init` is dead code —
  the dispatch in `pgp-decrypt.c` rejects bzip2 before we get here;
  redundant but harmless (nit)] —
  `source/contrib/pgcrypto/pgp-compress.c:210-212`.
- [ISSUE-memory: `dec->buf[ZIP_OUT_BUF]` holds plaintext briefly; only
  scrubbed on free, not after each chunk drain (nit)] —
  `source/contrib/pgcrypto/pgp-compress.c:200,318`.
- [ISSUE-audit-gap: no telemetry or `ereport(LOG, ...)` when
  decompression ratio exceeds a sane threshold; impossible to detect a
  bomb from server logs (likely)] —
  `source/contrib/pgcrypto/pgp-compress.c:278-310`.
