# pgp-pgsql.c

## One-line summary

PostgreSQL SQL bindings for the OpenPGP layer: the V1 fmgr wrappers for
`pgp_sym_encrypt`/`_decrypt`, `pgp_pub_encrypt`/`_decrypt` (both `_bytea`
and `_text` variants), plus `armor`, `dearmor`, `pgp_armor_headers`
(SRF), `pgp_key_id`. Also implements the option-string parser
(`cipher-algo=aes128, s2k-mode=3, ...`), the optional UTF-8 conversion
for text mode, and the `expect-*` debugging hooks used by the regression
tests.

## Public API / entry points

PG_FUNCTION_INFO_V1 declarations at
`source/contrib/pgcrypto/pgp-pgsql.c:48-62`:

- `pgp_sym_encrypt_bytea` (`:554`), `pgp_sym_encrypt_text` (`:576`).
- `pgp_sym_decrypt_bytea` (`:599`), `pgp_sym_decrypt_text` (`:621`).
- `pgp_pub_encrypt_bytea` (`:648`), `pgp_pub_encrypt_text` (`:670`).
- `pgp_pub_decrypt_bytea` (`:693`), `pgp_pub_decrypt_text` (`:720`).
- `pgp_key_id_w` (`:984`) — backs SQL `pgp_key_id(bytea)`.
- `pg_armor` (`:842`), `pg_dearmor` (`:880`),
  `pgp_armor_headers` (`:914`).

All are SQL functions exposed via `pgcrypto--1.X.sql`.

## Key invariants

- All bytea/text args use `PG_GETARG_*_PP` (no copy unless necessary) +
  `PG_FREE_IF_COPY` cleanup.
- `_text` variants call `pg_verifymbstr(VARDATA_ANY(res),
  VARSIZE_ANY_EXHDR(res), false)` after decrypt to enforce server
  encoding,
  `source/contrib/pgcrypto/pgp-pgsql.c:634,736` [verified-by-code]. The
  `false` arg means "throw ERROR on invalid".
- Option string parsed by `parse_args` (`:306`) — comma-separated
  `key=value` pairs, lowercased first.
- `init_work` (`:351`) calls `pgp_init` + `parse_args` + sets text mode.
- Error code from `pgp_*` layer → `px_THROW_ERROR(err)` (defined in
  `px.h`) which `ereport(ERROR, ...)`s.

## Notable internals

- **`fill_expect` + `check_expect`** — these are the test hooks. The
  `expect-cipher-algo=aes128` style options compare actual context
  state vs expected and `ereport(NOTICE, ...)` on mismatch. Used by
  `sql/pgp-*-cfb.sql` regression tests.
  `source/contrib/pgcrypto/pgp-pgsql.c:121-159` [verified-by-code].
- **Recognized option keys** (line 173-194): `cipher-algo`,
  `disable-mdc`, `sess-key`, `s2k-mode`, `s2k-count`,
  `s2k-digest-algo`, `s2k-cipher-algo`, `compress-algo`,
  `compress-level`, `convert-crlf`, `unicode-mode`. Plus
  debug/expect-* if `ex != NULL`.
- **`convert_charset` / `convert_to_utf8` / `convert_from_utf8`** —
  text-mode args may be transcoded to/from UTF-8 via
  `pg_do_encoding_conversion`,
  `source/contrib/pgcrypto/pgp-pgsql.c:67-94`. Only triggered if
  `unicode-mode=1`.
- **`clear_and_pfree(text *)`** — wipes via `px_memset` before pfree.
  Used for the transcoded text buffer (`:97-101`). **But only this
  one buffer.** Other intermediates (the bytea result of decrypt)
  are pfree'd without wiping in some paths.
- **`pgp_armor_headers` is an SRF** — uses the
  `SRF_IS_FIRSTCALL/SRF_RETURN_NEXT/SRF_RETURN_DONE` pattern,
  `source/contrib/pgcrypto/pgp-pgsql.c:914-975`. State allocated in
  `multi_call_memory_ctx`. Keys/values converted from UTF-8 to server
  encoding per row via `pg_any_to_server`.

## Crypto trust boundary / Phase D surface — **CENTRAL**

This file is the **attack surface** for everything in pgcrypto-PGP.
Every issue identified in the sibling docs is reachable from these
twelve SQL entry points.

- **`pgp_sym_decrypt(bytea, password [, options])`** — attacker
  controls the bytea AND optionally the option string. Specifically:
  - Crafted ciphertext can carry max-iter S2K → CPU DoS
    (`pgp-s2k.md`).
  - Crafted ciphertext can carry decompression bomb (`pgp-compress.md`).
  - Crafted ciphertext can carry tag-9 (no-MDC) packet → EFAIL surface
    (`pgp-cfb.md`).
  [ISSUE-security: `pgp_sym_decrypt` accepts arbitrary attacker
  bytea; all listed bottom-level surfaces are reachable from this
  single function (likely)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:599-617`.
- **`pgp_pub_decrypt(bytea, keypkt, [psw, options])`** — attacker
  ALSO controls the secret-key packet (`keypkt`). This is unusual:
  in production the keypkt is typically constant or app-supplied,
  but pgcrypto accepts attacker bytea here. Means
  `process_secret_key`'s S2K-iter surface
  (`pgp-pubkey.md`) is reachable.
  [ISSUE-security: `pgp_pub_decrypt` `keypkt` argument is
  attacker-controlled bytea; secret-key S2K iter can be forced to
  ~65M (likely)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:693-717`.
- **Option string is `downcase_convert`'d** — the key/value strings
  are lowercased before parsing,
  `source/contrib/pgcrypto/pgp-pgsql.c:287-303`. Means a password
  cannot be passed via the option string (it would be lowercased).
  But the password is a separate arg, so OK.
- **Option string mutation in place** — `parse_args` mutates the
  options text after `downcase_convert` (which palloc'd a copy).
  No aliasing risk because `downcase_convert` returns a fresh
  palloc.
- **`PG_FREE_IF_COPY` discipline** — every arg is paired with
  `PG_FREE_IF_COPY`. For password / key args, this means the
  toast-decompressed copy is pfree'd at function exit but NOT wiped.
  The original toast page is in shared buffers (cleartext password
  stored in a table!) which is its own can of worms.
  [ISSUE-defense-in-depth: password/key bytea args pfree'd without
  px_memset wipe; cleartext password lingers in palloc'd memory
  until context reset (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:568-571,613-617,710-715`.
- **`init_work` calls `px_set_debug_handler(show_debug)`** when
  `debug=1` is in options. `show_debug` does
  `ereport(NOTICE, ...)` with px_debug strings. **In production
  context, no user should pass `debug=1`** — the debug strings
  include packet-parsing details (e.g. "no pubkey?", "key sha1 check
  failed") that could form an oracle.
  `source/contrib/pgcrypto/pgp-pgsql.c:365-366,162-165`. The
  user-facing docs do NOT mention `debug` (it's marked "not
  documented" at line 196-199).
- **`pg_verifymbstr` on `_text` decrypt output** —
  `source/contrib/pgcrypto/pgp-pgsql.c:634,736`. Guards against
  decrypted-text bytes that violate the server's `client_encoding`.
  Important: a corrupt ciphertext + wrong-key combo could otherwise
  put invalid UTF-8 into a `text` value. Good defense.
- **`encrypt_internal` / `decrypt_internal`** are non-static and
  reused by all 8 SQL wrappers. The `is_pubenc` and
  `is_text`/`need_text` int flags pick the variant.
  `source/contrib/pgcrypto/pgp-pgsql.c:371-548`.
- **Result memory** — `mbuf_steal_data(dst, &restmp)` transfers
  ownership of the underlying buffer to `restmp`; SET_VARSIZE
  finalizes the bytea/text Datum. After this, the original `dst`
  MBuf is freed (line 449/528). Plaintext now lives in the
  `restmp` palloc and is returned via `PG_RETURN_TEXT_P` — caller
  (SQL executor) will route it into tuplestore, log files, error
  messages, etc. **Plaintext is now subject to all PG-wide memory
  handling: dropped via context reset, but not explicitly scrubbed.**
  [ISSUE-defense-in-depth: decrypted plaintext returned as palloc'd
  bytea/text; lives in expression-eval context until reset; never
  `explicit_bzero`'d (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:443-448,532-548`.
- **`pgp_key_id_w` returns the 64-bit key ID as text** — see
  `pgp-info.md`. Fingerprint truncation concern noted there.
- **`pg_armor` validates key/value header strings** — rejects
  non-ASCII, `\n`, `": "`,
  `source/contrib/pgcrypto/pgp-pgsql.c:802-832`. Good — this is the
  ONLY user-controlled-string-into-header surface, and pgcrypto
  validates it. (Compare with `pgp_armor_headers` SRF, which
  CONSUMES armor headers and converts UTF-8 → server encoding;
  inbound side does not validate header keys.)

## Cross-references

- All sibling `pgp-*.md` docs — every issue there is reachable from
  this file's SQL functions.
- A11-3 pgcrypto core — `px.h` `px_THROW_ERROR` is what turns
  `PXE_*` into `ereport(ERROR, ...)`.
- `pgp-pgsql.c:633` `pg_verifymbstr` — see `src/backend/utils/mb`.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `pgp_sym_decrypt`'s `data` bytea is fully
  attacker-controlled; reaches all bottom-level decryption surfaces
  (S2K iter, MDC bypass via tag 9, decompression bomb) (likely)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:599-617`.
- [ISSUE-security: `pgp_pub_decrypt`'s `keypkt` is attacker-
  controlled; secret-key packet S2K iter reaches ~65M (likely)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:693-717`.
- [ISSUE-defense-in-depth: undocumented `debug=1` option enables
  `ereport(NOTICE, ...)` of internal parsing strings; potential
  decryption-error oracle leak (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:200,365-366`.
- [ISSUE-defense-in-depth: password/key args pfree'd without
  `px_memset` wipe (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:568-571`.
- [ISSUE-defense-in-depth: decrypted plaintext returned via palloc'd
  text/bytea; lives in PG memory contexts until reset; no
  `explicit_bzero` (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:443-448,532`.
- [ISSUE-correctness: `clear_and_pfree(tmp_data)` only on error path
  for the UTF-8 conversion buffer; success path also calls it (line
  447), but the original `data` arg (often the user's plaintext) is
  NOT scrubbed (nit)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:431-450`.
- [ISSUE-api-shape: option-string parser silently ignores unknown
  keys ONLY if they're "expect-*" without ex; for `set_arg`,
  unknown key returns `PXE_ARGUMENT_ERROR`; consistent but the
  expect-only handling is non-obvious (nit)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:200-247`.
- [ISSUE-error-handling: `px_THROW_ERROR(err)` after `pgp_free(ctx)`
  in some paths but before in others; if `pgp_free` itself
  ereports (it doesn't, but contract isn't documented), order
  matters (nit)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:435-439,519-526`.
- [ISSUE-audit-gap: no `ereport(LOG, ...)` for repeated decryption
  failures (e.g. "10 `pgp_sym_decrypt` with wrong key in 1s");
  ratelimiting / lockout is outside pgcrypto scope but the lack of
  telemetry makes it hard to detect attacks (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:599-740`.
- [ISSUE-defense-in-depth: `pgp_armor_headers` SRF reads headers
  from attacker armor blob and routes them through
  `pg_any_to_server(... PG_UTF8)`; malformed UTF-8 yields a
  per-row ERROR that aborts the SRF mid-iteration (nit)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:968-969`.
- [ISSUE-correctness: `pgp_armor_headers` assumes UTF-8 input
  encoding for the armor headers; RFC 4880 does not mandate UTF-8;
  user-supplied headers could be in any encoding (maybe)] —
  `source/contrib/pgcrypto/pgp-pgsql.c:964-969`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgcrypto.md](../../../subsystems/contrib-pgcrypto.md)
