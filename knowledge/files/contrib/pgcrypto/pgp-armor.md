# pgp-armor.c

## One-line summary

ASCII armor (Base64 + CRC24 framing, RFC 4880 §6) — encode wraps binary
PGP message bytes in `-----BEGIN PGP MESSAGE-----` headers with optional
key:value armor headers; decode strips headers, parses Base64, verifies
CRC24. Backs the SQL functions `armor`, `dearmor`, `pgp_armor_headers`.

## Public API / entry points

- `pgp_armor_encode(src, len, dst, num_headers, keys, values)` — encode,
  `source/contrib/pgcrypto/pgp-armor.c:207` [verified-by-code].
- `pgp_armor_decode(src, len, dst)` — decode + verify CRC,
  `source/contrib/pgcrypto/pgp-armor.c:314` [verified-by-code]. Returns
  `PXE_PGP_CORRUPT_ARMOR` on any framing/CRC failure.
- `pgp_extract_armor_headers(src, len, &nheaders, &keys, &values)` —
  parse just the headers (key/value strings) for SQL
  `pgp_armor_headers()`,
  `source/contrib/pgcrypto/pgp-armor.c:390` [verified-by-code].

## Key invariants

- Base64 alphabet hard-coded at
  `source/contrib/pgcrypto/pgp-armor.c:41-42` [verified-by-code]. Standard
  RFC 4648 alphabet with `+` and `/`.
- CRC24 with `CRC24_INIT=0x00b704ce`, `CRC24_POLY=0x01864cfb` per RFC
  4880. `source/contrib/pgcrypto/pgp-armor.c:185-204` [verified-by-code].
- Line wrap at 76 chars during encode,
  `source/contrib/pgcrypto/pgp-armor.c:76-80`.
- `pg_base64_decode` accepts whitespace (`\t \n \r`) silently and
  enforces `=` padding rules,
  `source/contrib/pgcrypto/pgp-armor.c:135-138` [verified-by-code].
- Encode produces `armor_header` then optional `key: value\n` lines, blank
  line, base64 body, `=` + 4-char CRC, `armor_footer`. The 4-char CRC is
  base64'd big-endian (24-bit → 4 base64 chars).
  `source/contrib/pgcrypto/pgp-armor.c:215-239` [verified-by-code].

## Notable internals

- `find_header(data, data_end, &start_p, is_end)` scans for `"-----BEGIN"`
  or `"-----END"` substrings via `memchr` (`source/contrib/pgcrypto/pgp-armor.c:265-311`).
  Requires the marker to start at line beginning (preceded by `\n` or at
  the very start).
- `find_str` is a substring search using `memchr` — O(n*m) worst case.
- Decode allows comment headers up to the blank line. CR/LF tolerated
  via `*p != '\n' && *p != '\r'` checks.
- `pgp_extract_armor_headers` mallocs a modifiable copy of the header
  region, NULs at `:` and `\n`. Both `keys[i]` and `values[i]` point
  inside that buffer. Lifetime: until the calling MemoryContext is
  reset. `source/contrib/pgcrypto/pgp-armor.c:438-441` [verified-by-code].

## Crypto trust boundary / Phase D surface

- **`pgp_armor_decode` is the FIRST decoder run on attacker-supplied
  bytea/text.** Untrusted input → Base64 decode → CRC24 check. If decode
  succeeds (returns blob length), the blob is fed to `pgp_decrypt`. A
  malformed-armor input that nevertheless decodes successfully could
  produce a "decrypted" output that's garbage, exposing
  `parse_literal_data` etc. to corrupt-data paths.
- **`pg_base64_decode` is custom — not the libpq common base64.** Comment
  at line 38 even says "duplicated :(". Custom crypto-adjacent decoders
  warrant fuzz testing.
  [ISSUE-defense-in-depth: custom base64 implementation duplicates
  `src/common/base64.c`; could diverge in edge cases (maybe)] —
  `source/contrib/pgcrypto/pgp-armor.c:38,45-160`.
- **CRC24 mismatch returns `PXE_PGP_CORRUPT_ARMOR`** — good.
  `source/contrib/pgcrypto/pgp-armor.c:373-376` [verified-by-code].
- **CRC24 is integrity-WEAK.** CRC24 is a checksum, not a MAC. An
  attacker can compute matching CRC24 for any chosen plaintext blob, so
  the armor CRC offers zero protection against malicious modifications
  — only transmission corruption. The actual integrity check is the MDC
  inside the encrypted packet (`pgp-decrypt.c:382`).
- **Headers are user-controlled.** `pg_armor(data, keys[], values[])` —
  the SQL wrapper *does* validate keys/values are ASCII, no `\n`, no
  `": "` substring (`pgp-pgsql.c:802-832`). Good defense in depth.
- **`find_header` looks for `-----BEGIN`/`-----END` anywhere**, requiring
  line-start. An attacker who can construct armor with a literal
  `-----BEGIN PGP MESSAGE-----` followed by junk and then a valid blob
  could confuse decoders, but the `find_header` requires the marker
  itself be valid header syntax (`>=' '` chars only after the marker, up
  to next `-`). Robust enough for typical input.
- **`elog(FATAL, ...)` on overflow** —
  `source/contrib/pgcrypto/pgp-armor.c:227,370`. FATAL terminates the
  *session*, not just the query. Reachable only if internal length
  estimation is wrong — should be unreachable but is a denial-of-service
  if triggered. [ISSUE-error-handling: `elog(FATAL)` on internal length
  miscalc kills entire backend session (maybe)] —
  `source/contrib/pgcrypto/pgp-armor.c:227,370`.

## Notable internals — `pgp_extract_armor_headers`

- Counts header lines via `memchr('\n')` scan before allocating
  return arrays.
- Returns `PXE_PGP_CORRUPT_ARMOR` on missing `": "` separator
  (`source/contrib/pgcrypto/pgp-armor.c:467-468`).
- Returned `keys[]` and `values[]` are pointers into a heap buffer; the
  caller must keep that buffer alive. SQL wrapper handles this via
  `palloc` in the SRF state context (`pgp-pgsql.c:931-934`).

## Cross-references

- `pgp-pgsql.md` — `pg_armor`, `pg_dearmor`, `pgp_armor_headers` wrappers.
- A11-3 pgcrypto core — `pgcrypto.c` shares no armor code; this is
  PGP-specific.
- `src/common/base64.c` — the in-tree base64 that this file duplicates.
- RFC 4880 §6 (Radix-64 Conversions) — the spec.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-defense-in-depth: custom `pg_base64_encode`/`pg_base64_decode`
  duplicates `src/common/base64.c`; divergence risk for edge cases
  (maybe)] — `source/contrib/pgcrypto/pgp-armor.c:38-175`.
- [ISSUE-error-handling: `elog(FATAL, "overflow - encode estimate too
  small")` on encode/decode length miscalc; FATAL kills the session,
  ERROR would suffice (maybe)] —
  `source/contrib/pgcrypto/pgp-armor.c:227,370`.
- [ISSUE-correctness: `find_str(p, data_end, str, strlen)` first arg
  `strlen` shadows the libc `strlen` name — confusing but not buggy;
  the local parameter wins (nit)] —
  `source/contrib/pgcrypto/pgp-armor.c:242`.
- [ISSUE-correctness: when `pos != 0` at end-of-input,
  `pg_base64_decode` returns `PXE_PGP_CORRUPT_ARMOR` — good. But
  the function returns either negative-error or output-byte-count,
  callers must check sign explicitly (nit)] —
  `source/contrib/pgcrypto/pgp-armor.c:157-159`.
- [ISSUE-audit-gap: no upper bound on output length in
  `pgp_armor_decode`; if attacker supplies 1 GB of "ASCII armor", we'll
  base64-decode 750 MB into a StringInfo (maybe)] —
  `source/contrib/pgcrypto/pgp-armor.c:366-368`. SQL-level `bytea`
  size limit (1 GB) is the only ceiling.
- [ISSUE-correctness: `pgp_extract_armor_headers` returns header k/v
  pointers into a heap buffer; if caller frees the wrong context the
  pointers dangle. Caller (pgp-pgsql.c) handles this correctly, but
  it's a footgun for direct C consumers (nit)] —
  `source/contrib/pgcrypto/pgp-armor.c:438-441`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgcrypto.md](../../../subsystems/contrib-pgcrypto.md)
