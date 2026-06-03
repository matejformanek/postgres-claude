---
path: src/common/md5_int.h
anchor_sha: 4b0bf0788b0
loc: 85
---

# md5_int.h

- **Source path:** `source/src/common/md5_int.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 85

## Purpose

Internal header for the in-tree MD5 fallback. Defines the
`pg_md5_ctx` state struct and the three primitive entry points
(`pg_md5_init`, `pg_md5_update`, `pg_md5_final`) implemented in
`md5.c`. Pulled in by `cryptohash.c` (which unions all six fallback
ctxs into one) and by `md5.c` itself. NOT pulled in by
`cryptohash_openssl.c` — that path uses OpenSSL's `EVP_md5()`.
[verified-by-code, md5_int.h:46-83]

## Key declarations

- `MD5_BUFLEN 64` (md5_int.h:51) — block buffer.
- `struct pg_md5_ctx` (md5_int.h:54-78): two unions for the 128-bit
  state (`md5_state32[4]` aliased to `md5_state8[16]`) and the
  64-bit message-bit counter (`md5_count64` aliased to
  `md5_count8[8]`), plus current buf-fill index `md5_i` and the
  64-byte working buffer. The `md5_sta`/`stb`/`stc`/`std` /
  `md5_n`/`md5_n8` macros provide named field access.
- Prototypes: `pg_md5_init / _update / _final` (md5_int.h:81-83). No
  `_create` / `_free`; the caller embeds the struct (cryptohash.c
  unions all algorithm ctxs into one `pg_cryptohash_ctx`).

## Phase D notes

- The whole struct is on-stack inside `pg_cryptohash_ctx.data.md5`
  (cryptohash.c:58). `pg_cryptohash_free` does
  `explicit_bzero(ctx, sizeof(pg_cryptohash_ctx))` (cryptohash.c:243)
  so the internal MD5 state is scrubbed. Good.
- WIDE-project licence header is preserved verbatim — touching the
  struct layout requires updating both unions in lockstep.

## Cross-refs

- Impl: `knowledge/files/src/common/md5.c.md`.
- Public API: `knowledge/files/src/include/common/md5.h.md`.
- Used via union in: `knowledge/files/src/common/cryptohash.c.md`.

## Tally

`[verified-by-code]=4`
