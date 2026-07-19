# px-hmac.c

## One-line summary

HMAC construction (RFC 2104) layered over `PX_MD` digests, used by the
SQL `hmac()` function and indirectly by S2K key derivation in PGP.
Implements `hmac_init` / `hmac_update` / `hmac_finish` as the standard
`H(opad || H(ipad || msg))` pattern.

Covers `source/contrib/pgcrypto/px-hmac.c` (176 lines).

## Public API / entry points

- `int px_find_hmac(const char *name, PX_HMAC **res)` —
  `px-hmac.c:142-176`. Calls `px_find_digest(name, &md)`, rejects
  hashes whose block size < 2 (which would be malformed) with
  `PXE_HASH_UNUSABLE_FOR_HMAC`, then allocates the `ipad`/`opad`
  buffers (block-size each) and wires up the vtable.

## Key invariants

- **HMAC bases on PX_MD**, so any digest exposed by openssl.c is
  usable. The block-size check at `px-hmac.c:153-158` is the only
  filter. [verified-by-code]
- **Key shorter than block size**: copied into a `palloc0(bs)` buf,
  rest is zero-padded (`px-hmac.c:60-61, 68-69`).
- **Key longer than block size**: replaced with `H(key)` — see
  `px-hmac.c:62-67`. RFC 2104 § 2.
- **`ipad` and `opad` are stored in the PX_HMAC**: 2 × block_size
  bytes total. For SHA-512 (128-byte block) that's 256 bytes per
  HMAC handle. [verified-by-code]
- **`hmac_free` scrubs ipad/opad** before pfree
  (`px-hmac.c:131-132`). Uses `px_memset`. The intermediate keybuf
  in `hmac_init` is also scrubbed (`px-hmac.c:77`). Buf in
  `hmac_finish` (holds inner H output, NOT a secret per RFC 2104)
  is also scrubbed (`px-hmac.c:119`).

## Notable internals

### HMAC ipad/opad constants

`HMAC_IPAD = 0x36`, `HMAC_OPAD = 0x5C` (`px-hmac.c:36-37`). Standard
RFC 2104 values.

### `hmac_init` flow

1. Get block-size `bs` from the underlying digest.
2. Allocate `keybuf` of `bs` bytes, zero-init.
3. If `klen > bs`: hash the key into keybuf via the same digest,
   then reset the digest for fresh use.
4. Otherwise: `memcpy(keybuf, key, klen)`.
5. XOR keybuf into `h->p.ipad` and `h->p.opad` with the constants.
6. Scrub keybuf and pfree.
7. Update the digest with `ipad` to start the inner-hash stream.

### `hmac_finish` flow

1. Finalize inner hash into temp `buf`.
2. Reset digest, update with `opad`, then `buf`, then finalize into
   caller's `dst`.
3. Scrub temp buf.

### `hmac_reset` flow

Reset digest + update with ipad → ready for new message with same key.
This means the original key is no longer needed after `hmac_init` —
the ipad/opad XOR'd state suffices. [verified-by-code `px-hmac.c:83-91`]

## Crypto trust boundary / Phase D surface

- **Key handling**: short keys are zero-extended to block size — not
  a vulnerability per RFC 2104 but worth noting. Long keys go through
  one hash compression. [verified-by-code]
- **Memory scrubbing**: ipad/opad and intermediate buffers are
  scrubbed with `px_memset`. Same caveat as in `px.md` —
  `px_memset` may be elided by LTO.
  [ISSUE-security: px_memset elision risk applies here (likely)]
- **The output bytes from `hmac_finish` are returned raw to
  pgcrypto.c**, which returns them as bytea. Constant-time
  comparison is the caller's responsibility (see pgcrypto.md
  HMAC issue). px-hmac.c does not expose a verify helper.
- **No truncation check on the output digest** — the full
  `result_size(md)` bytes are written. So pgcrypto.c's `pg_hmac`
  allocates exactly that many bytes. Fine.

## Cross-references

- `openssl.c:px_find_digest` — provides the underlying `PX_MD`.
- `px.h:PX_HMAC` struct definition.
- `crypt-sha.c` — uses `px_find_digest` directly (NOT via HMAC) for
  password hashing.
- A5 `src/common/hmac_openssl.c` — the core SCRAM HMAC implementation.
  Parallel code; pgcrypto duplicates the RFC 2104 logic here instead
  of reusing.
- RFC 2104 — Krawczyk et al, "HMAC: Keyed-Hashing for Message
  Authentication".

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: no constant-time-compare helper exposed (likely)]
  — px-hmac.c returns the raw tag and lets SQL compare. Same as the
  pgcrypto.md finding.
- [ISSUE-defense-in-depth: duplicate HMAC implementation vs
  src/common/hmac_openssl.c (nit)] — the corpus has TWO HMAC impls.
  Drift risk.
- [ISSUE-security: `px_memset` LTO-elision risk applies (likely)] —
  see px.md.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgcrypto.md](../../../subsystems/contrib-pgcrypto.md)
