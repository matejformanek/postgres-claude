# pgp-cfb.c

## One-line summary

Implements two CFB modes for OpenPGP: the **normal** CFB used by
`SYMENCRYPTED_DATA_MDC` (tag 18) and the **resync** CFB ("PGP CFB") used by
the legacy `SYMENCRYPTED_DATA` (tag 9) — the latter performs an unusual
block-2 IV resynchronization that is the historical EFAIL-class attack
surface.

## Public API / entry points

- `pgp_cfb_create(ctx_p, algo, key, key_len, resync, iv)` — init CFB
  state, `source/contrib/pgcrypto/pgp-cfb.c:52` [verified-by-code]. `resync`
  flag picks `mix_*_resync` vs `mix_*_normal`.
- `pgp_cfb_encrypt(ctx, data, len, dst)` — encrypt in place,
  `source/contrib/pgcrypto/pgp-cfb.c:252` [verified-by-code].
- `pgp_cfb_decrypt(ctx, data, len, dst)` —
  `source/contrib/pgcrypto/pgp-cfb.c:260` [verified-by-code].
- `pgp_cfb_free(ctx)` — px_memsets state, `source/contrib/pgcrypto/pgp-cfb.c:83`.

## Key invariants

- One `PX_Cipher` per `PGP_CFB`. Block size pulled from
  `px_cipher_block_size(ciph)`, stored in `ctx->block_size`.
- `fr`, `fre`, `encbuf` are each `PGP_MAX_BLOCK=32` bytes — only the first
  `block_size` are used.
- IV passed in is copied into `ctx->fr` if non-NULL; otherwise `palloc0`
  zero-fills it. `source/contrib/pgcrypto/pgp-cfb.c:70,75-76`.
- `ctx->block_no` tracks blocks 0..5 (saturating). Used only in
  `mix_*_resync` to detect "block 2" — the OpenPGP-specific resync moment.
  `source/contrib/pgcrypto/pgp-cfb.c:131-148,163-182,226`.
- Resync resync moment (resync mode only): after the 2-byte "block 2", the
  next `fr` is computed as `encbuf[2..bs] || encbuf[0..2]` — i.e. the IV is
  reseeded from the (decrypted) checksum bytes. Spelled out at
  `source/contrib/pgcrypto/pgp-cfb.c:142-148`.

## Notable internals

- Two pairs of "mix_data" functions: `mix_encrypt_normal` /
  `mix_decrypt_normal` (just XOR with cipher stream),
  `source/contrib/pgcrypto/pgp-cfb.c:93-116`; and `mix_encrypt_resync` /
  `mix_decrypt_resync` for the legacy mode,
  `source/contrib/pgcrypto/pgp-cfb.c:124-191`.
- `cfb_process` is the dispatch loop: drain partial buffer, then run full
  blocks. `source/contrib/pgcrypto/pgp-cfb.c:196-245`.
- The "horror" comment at line 121 is sincere — block-2 resync is a
  PGP-specific quirk with no analogue in NIST CFB.

## Crypto trust boundary / Phase D surface

- **Resync-mode CFB is the EFAIL-relevant code path.** EFAIL (Poddebniak
  et al., 2018) exploited two facts: (1) MDC-less ciphertexts (tag 9 =
  `SYMENCRYPTED_DATA`) lack any integrity check, and (2) the "PGP CFB
  quick check" (the 2-byte prefix check in `prefix_init`) gives only weak
  evidence. Pgcrypto's defense: when `SYMENCRYPTED_DATA` (no MDC) is
  parsed, errors are *delayed* to `pgp_decrypt` finalization
  (`pgp-decrypt.c:1186-1187`) to avoid the
  Mister-Zuccherato CFB-quick-check oracle.
- **Old PGP CFB resync mode is still reachable** from SQL via
  `disable-mdc=1` on encrypt, or by feeding old ciphertexts (tag 9) to
  `pgp_sym_decrypt`. `pgp_decrypt` sets `ctx->disable_mdc = 1` when it
  sees a tag-9 packet (`source/contrib/pgcrypto/pgp-decrypt.c:1149`), so
  the resync mode IS used, and the prefix quick check still leaks an
  oracle that pgcrypto mitigates only by delaying error reporting.
  [ISSUE-security: legacy `SYMENCRYPTED_DATA` (no-MDC) ciphertexts still
  parsed by `pgp_decrypt`; only mitigation is delayed-error reporting
  (likely)] — `source/contrib/pgcrypto/pgp-decrypt.c:1141-1152`.
- **No constant-time XOR.** `mix_encrypt_normal` uses a plain `for` loop
  (`source/contrib/pgcrypto/pgp-cfb.c:97-101`). Modern CFB attacks don't
  rely on per-byte timing leaks here — the cipher itself does — so this
  is informational.
- `px_memset(ctx, 0, sizeof(*ctx))` on free, including the `encbuf` last
  cipherstream block. Good.
- **No memory wiping inside `mix_*` between blocks**, but `encbuf` is a
  per-context buffer that gets scrubbed at free time.

## Cross-references

- `pgp-decrypt.md` — `parse_symenc_data` (no MDC) vs `parse_symenc_mdc_data`
  build different filter chains; both go through `pgp_decrypt_filter`,
  which calls `pgp_cfb_decrypt`.
- `pgp-encrypt.md` — `encrypt_init` calls `pgp_cfb_create` with
  `resync = (ctx->disable_mdc != 0)`,
  `source/contrib/pgcrypto/pgp-encrypt.c:163-177`.
- A11-3 pgcrypto core — `PX_Cipher` API (`px_cipher_encrypt`,
  `px_cipher_block_size`).
- EFAIL paper, Mister-Zuccherato 2005 "An Attack on CFB Mode Encryption As
  Used By OpenPGP" — referenced in `pgp-decrypt.c:1194-1196` comment.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: legacy resync-CFB path remains reachable on decrypt; an
  attacker feeding tag-9 ciphertext gets the no-MDC code path without any
  warning to the SQL user (likely)] —
  `source/contrib/pgcrypto/pgp-decrypt.c:1141-1152`.
- [ISSUE-defense-in-depth: `pgp_cfb_decrypt` does not return an error
  signal if `len` were negative; only the cipher does. Caller passes
  controlled `len` from packet reader, so no overflow, but guard would
  document intent (nit)] — `source/contrib/pgcrypto/pgp-cfb.c:260`.
- [ISSUE-correctness: `block_no` saturates at 5 (`if (ctx->block_no < 5)`),
  but resync mode only checks `block_no == 2`; if a single CFB context is
  used across multiple short messages, block_no semantics get fuzzy. In
  practice each PGP packet creates a fresh CFB context, so harmless (nit)]
  — `source/contrib/pgcrypto/pgp-cfb.c:131,226`.
- [ISSUE-documentation: "block #2 is 2 bytes long" without explanation of
  the OpenPGP quirk (nit)] — `source/contrib/pgcrypto/pgp-cfb.c:130`.
  See RFC 4880 §13.9 for the rationale.
