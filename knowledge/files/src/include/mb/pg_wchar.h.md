# `src/include/mb/pg_wchar.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~626
- **Source:** `source/src/include/mb/pg_wchar.h`

The central encoding/multibyte header: defines `pg_wchar`, the
`pg_enc` enum (canonical encoding IDs — pinned for ABI), the
per-encoding callback table (`pg_wchar_tbl`), radix-tree types for
UTF-8 ↔ local conversions, UTF-8 helpers, and the full set of
encoding-aware string routines. Pulled into the backend AND many
frontend tools — "should not be included by libpq client programs"
because libpq's encoding IDs are version-pinned independently.
[from-comment]

## API / declarations

### Core typedef

- `typedef unsigned int pg_wchar;` — wide-char representation
  (32-bit). `MAX_MULTIBYTE_CHAR_LEN = 4`.

### Encoding identifiers

- `enum pg_enc` — `PG_SQL_ASCII = 0` (default, MUST be 0), then
  EUC family, `PG_UTF8`, `PG_UNUSED_1`, Latin1-10, Windows-125x,
  KOI8, ISO_8859_*, etc. Ends with client-only encodings (SJIS,
  BIG5, GBK, UHC, GB18030, JOHAB, SHIFT_JIS_2004) and the sentinel
  `_PG_LAST_ENCODING_`. [verified-by-code]
- `PG_ENCODING_BE_LAST = PG_KOI8U` — boundary marker; encodings
  above this are client-only. [verified-by-code]
- Predicates: `PG_VALID_BE_ENCODING`, `PG_ENCODING_IS_CLIENT_ONLY`,
  `PG_VALID_ENCODING`, `PG_VALID_FE_ENCODING`,
  `PG_UNUSED_ENCODING`.

### Conversion growth bounds

- `MAX_CONVERSION_GROWTH = 4` — worst-case bytes-out/bytes-in;
  "SJIS JIS X0201 half width kana -> UTF8 is the worst case."
- `MAX_CONVERSION_INPUT_LENGTH = 16` — bytes of input always
  sufficient to convert at least one character.
- `MAX_UNICODE_EQUIVALENT_STRING = 16` — bytes needed for the
  representation of any single Unicode code point in any backend
  encoding. [from-comment]

### Per-encoding callbacks

- Function-pointer typedefs: `mb2wchar_with_len_converter`,
  `wchar2mb_with_len_converter`, `mblen_converter`,
  `mbdisplaylen_converter`, `mbcharacter_incrementer`,
  `mbchar_verifier`, `mbstr_verifier`.
- `pg_wchar_tbl { mb2wchar_with_len, wchar2mb_with_len, mblen,
  dsplen, mbverifychar, mbverifystr, maxmblen }`.
- `extern const pg_wchar_tbl pg_wchar_table[]` — indexed by pg_enc.
- `extern const pg_enc2name pg_enc2name_tbl[]` (with optional
  Windows codepage),
- `extern const char *pg_enc2gettext_tbl[]`.

### UTF-8 ↔ local conversion radix trees

- `pg_mb_radix_tree { chars16, chars32, b1root..b4root, b{1..4}_*_
  {lower,upper} }` — separate radix structures for 1-/2-/3-/4-byte
  input. Initial all-zeros table guards intermediate lookups.
  [from-comment]
- `pg_utf_to_local_combined { utf, code }` and
  `pg_local_to_utf_combined { utf, code }` — sorted arrays for
  combining-character mappings that don't fit the radix tree.
- `utf_local_conversion_func` — final fallback function-pointer.

### UTF-8 inlines

- `utf8_to_unicode(c)` → `char32_t` — branched decode for 1-/2-/3-/
  4-byte sequences; invalid input returns `0xffffffff`.
- `unicode_to_utf8(c, utf8string)` → encoded string pointer.
- `unicode_utf8len(c)` → 1..4.
- `pg_utf8_islegal(source, length)` — full validation.

### libpq ABI shim

- Under `USE_PRIVATE_ENCODING_FUNCS || !FRONTEND`,
  `pg_char_to_encoding` / `pg_encoding_to_char` /
  `pg_valid_server_encoding{,_id}` / `pg_utf_mblen` are macro-
  redirected to `_private` versions to avoid colliding with libpq's
  exports. Static-link callers (e.g. libpgcommon_srv.a) bind the
  `_private` symbols. [from-comment]

### String length / display

- Family of `pg_mblen_*` (cstr / range / with_len / unbounded /
  deprecated `pg_mblen`) and `pg_dsplen`, `pg_mbstrlen`,
  `pg_mbstrlen_with_len`, `pg_mbcliplen`, `pg_encoding_mbcliplen`,
  `pg_mbcharcliplen`, `pg_database_encoding_max_length`.

### Client/database encoding state

- `PrepareClientEncoding`, `SetClientEncoding`,
  `InitializeClientEncoding`, `pg_get_client_encoding`,
  `pg_get_client_encoding_name`.
- `SetDatabaseEncoding`, `GetDatabaseEncoding`,
  `GetDatabaseEncodingName`.
- `SetMessageEncoding`, `GetMessageEncoding`.

### Conversion engines

- `pg_do_encoding_conversion(src, len, src_enc, dest_enc)` (palloc'd
  result), `pg_do_encoding_conversion_buf(...)`.
- `pg_client_to_server`, `pg_server_to_client`, `pg_any_to_server`,
  `pg_server_to_any`.
- `pg_unicode_to_server(c, s)` / `_noerror`.
- BIG5 ↔ CNS: `BIG5toCNS`, `CNStoBIG5`.
- Radix-tree drivers: `UtfToLocal`, `LocalToUtf` (with noError
  bool).
- Validators: `pg_verifymbstr`, `pg_verify_mbstr`,
  `pg_verify_mbstr_len`.
- `check_encoding_conversion_args`.
- `pg_noreturn` error reporters: `report_invalid_encoding`,
  `report_untranslatable_char`.

### Misc

- `is_encoding_supported_by_icu(encoding)` / `get_encoding_name_for_icu`.
- `local2local(l, p, len, src, dest, tab, noError)` — generic
  byte-substitution conversion (KOI/Win/ISO families).
- `pgwin32_message_to_UTF16` (WIN32-only).

## Notable invariants / details

- `PG_SQL_ASCII = 0` is reserved and MUST stay zero (default in
  zeroed memory). [from-comment]
- "XXX We must avoid renumbering any backend encoding until libpq's
  major version number is increased beyond 5" — the enum values
  are baked into libpq 8.2 era ABI. [from-comment]
- `_PG_LAST_ENCODING_` is the count, not a real encoding — never
  pass it to a converter.
- The 4-1 conversion bound (`MAX_CONVERSION_GROWTH=4`) is the
  worst measured case; "currently supported encoding pairs are
  within 3." Tightening would break the safety margin.
  [from-comment]
- The libpq-shim trick relies on the macro definitions firing
  BEFORE the function prototypes; reordering the conditional in a
  refactor would silently link the wrong symbol.
  [verified-by-code] [from-comment]
- `pg_unused_encoding(_enc) := _enc == PG_UNUSED_1` —
  `PG_UNUSED_1` is what was once Mule internal code. Reusing the
  slot would silently break valid-encoding checks.

## Potential issues — Phase D angles

- `utf8_to_unicode` returns `0xffffffff` on invalid 4-byte
  sequences (and treats the leading-byte family-check as
  authoritative). Callers must check the return; the inline
  signature doesn't enforce it. [ISSUE-correctness: invalid-UTF8
  silently returns FFFFFFFF (likely)]
- `pg_enc` is a public enum but ANY renumbering of backend
  encodings breaks the libpq 8.2-era ABI. Comment flags this but
  there is no compile-time check. [ISSUE-undocumented-invariant:
  pg_enc numbering pinned to libpq major (likely)]
- `MAX_CONVERSION_GROWTH=4` is a global cap — a future user-defined
  conversion that exceeds it would silently overrun output buffers
  sized to `4*srclen`. [ISSUE-security: user-defined conversion
  exceeding growth cap (maybe)]
- `local2local` takes a "tab" pointer with no length argument; the
  table is sized by the caller's encoding pair and not bounded by
  the prototype. [ISSUE-security: local2local table bounds
  external (maybe)]
- `pg_database_encoding_character_incrementer()` returns a function
  pointer — caller responsible for invoking under the right
  database-encoding context, no GUC-state sync.
  [ISSUE-undocumented-invariant: incrementer must match
  current database encoding (likely)]
- `pgwin32_message_to_UTF16` (and PG_UNUSED_1 special-case) are
  carrying historical baggage; the comment chain is consistent
  but readability suffers. [ISSUE-style: historical-baggage
  density high (nit)]
