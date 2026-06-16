# src/common/wchar.c

## Purpose

The PG-wide multibyte-encoding support module. Implements the
per-encoding `(mb2wchar, wchar2mb, mblen, dsplen, verifychar,
verifystr)` function table and the public
`pg_encoding_*` wrappers used everywhere a backend or libpq needs
to count, validate, or convert characters in any of the 41
supported server/client encodings.

## Role in PG

Shared **frontend + backend**. Backend uses it for client→server
encoding conversion, COPY parsing, regex, identifier length
checks, and the `OCTET_LENGTH`/`CHAR_LENGTH` family. libpq uses it
for client-side `PQescapeString`, `PQescapeIdentifier`, and the
client_encoding plumbing. Every wire-protocol byte that claims to
be in a particular encoding eventually goes through
`pg_encoding_verifymbstr()` here.

## Architecture

- Each encoding contributes a tuple of static functions, plugged
  into the global `pg_wchar_table[]` array indexed by `pg_enc`
  enum value (`wchar.c:1865-1907`). All public
  `pg_encoding_*` calls dispatch through this table.
- The encoding-specific functions come in pairs:
  - `*_mblen(s)` — byte length of the character at `s`. Allowed to
    assume valid input; caller responsibility.
  - `*_dsplen(s)` — display column width (0 / 1 / 2; or -1 for
    control chars). Drives psql formatting.
  - `*_verifychar(s, len)` — paranoid validation of one character,
    returns char byte length on success or -1.
  - `*_verifystr(s, len)` — paranoid validation of a whole string,
    returns the number of valid bytes (which equals `len` iff the
    whole string is valid). (`wchar.c:893-907`)
  - `*2wchar_with_len(from, to, len)` / `*_wchar2_with_len(...)` —
    conversion to/from the internal `pg_wchar` (32-bit codepoint
    or encoding-specific 32-bit value).

## Key functions

### UTF-8 (the high-traffic path)

- `pg_utf2wchar_with_len(from, to, len)` static —
  byte-stream → `pg_wchar[]`. Greedy decode by leading-byte
  prefix bits; `MB2CHAR_NEED_AT_LEAST(len, need)` guards short
  trailing sequences (just breaks the loop — no error). Bogus
  leading bytes get passed through as length 1. (`wchar.c:462-515`)
- `pg_utf_mblen(s)` — byte length per leading byte: 1/2/3/4. Returns
  1 for any illegal or >4-byte sequence start (UTF-8 in PG is
  capped at 4 bytes; comment at `:546-554` notes the cap is
  intentional and several other call sites would need updating to
  raise it). (`wchar.c:556-...`)
- `pg_utf8_verifychar(s, len)` — single-character verify; calls
  `pg_utf_mblen(s)` then `pg_utf8_islegal(s, l)` to enforce the
  RFC 3629 constraints. (`wchar.c:1502-...`)
- `pg_utf8_verifystr(s, len)` — vectorised fast path
  (`utf8_advance` state machine) over `STRIDE_LENGTH = 2 *
  sizeof(Vector8)` chunks, fall-back to per-character verify for
  the tail or after a state-machine ERR. Critical hot path; the
  vectorisation handles all-ASCII strides with a single
  `is_valid_ascii` check, skipping the full UTF-8 validation for
  ASCII-only input. (`wchar.c:1692-1773`)
- `pg_utf8_islegal(source, length)` — implements the RFC 3629
  constraints in a `switch(length)` cascade with `case 0xE0/0xED/
  0xF0/0xF4` boundaries. Explicitly mentions the overlong-encoding
  security hazard: "you may not use a longer-than-necessary byte
  sequence with high order zero bits to represent a character
  that would fit in fewer bytes. To do otherwise is to create
  security hazards (eg, create an apparent non-ASCII character
  that decodes to plain ASCII)." (`wchar.c:1775-1844`)

### Other encodings (one each)

- EUC-JP / EUC-CN / EUC-KR / EUC-TW / EUC-JIS-2004 — each has its
  own state machine for the SS2/SS3 single-shift bytes and CS2/CS3
  half-zone constraints. (`wchar.c:184-396`, verifiers `:933-1075`)
- SJIS / SHIFT-JIS-2004, BIG5, GBK, UHC, JOHAB, GB18030 —
  lead-byte-range table-driven `_mblen` and matching verifiers.
  (later in file)
- LATIN-1 family — single-byte; mblen = 1, dsplen via ASCII fold
  for printable, -1 for control. (`wchar.c:..._latin1_*`)

### `NONUTF8_INVALID_BYTE0/1`

- A canary two-byte pair `(0x8D, ' ')` (`wchar.c:36-37`) chosen
  so that `pg_encoding_mblen()` claims 2 bytes but every encoding's
  `_verifychar` rejects it. Used by `pg_encoding_set_invalid` to
  let callers stash a known-invalid character into a buffer for
  later replacement. For UTF-8 the canary is `(0xC0, ' ')`.
  (`wchar.c:1847-1858`)

### Dispatch wrappers

- `int pg_encoding_mblen(int encoding, const char *mbstr)` — table
  dispatch with SQL_ASCII fallback for out-of-range `encoding`.
  Requires `mbstr` non-empty AND at least 1 readable byte; for
  buffer-bounded use, the comment at `:1920-1933` recommends
  `pg_encoding_mblen_or_incomplete` or `_bounded`.
  (`wchar.c:1935-1939`)
- `int pg_encoding_mblen_or_incomplete(int encoding, const char
  *mbstr, size_t remaining)` — for callers walking a possibly
  partial buffer. Returns `remaining` if `remaining < 1` or the
  encoding-specific min lead-byte check fails.
  (`wchar.c:1947-...`)
- `int pg_encoding_mblen_bounded(int encoding, const char *mbstr)`
  — clamps `mblen` against `strnlen` for safety with
  zero-terminated input. (`wchar.c:1967-1969`)
- `int pg_encoding_dsplen(int encoding, const char *mbstr)` —
  display width. (`wchar.c:...`)
- `int pg_encoding_verifymbchar(int encoding, const char *mbstr,
  int len)` (`wchar.c:1989-1993`),
  `int pg_encoding_verifymbstr(int encoding, const char *mbstr,
  int len)` (`wchar.c:2002-2007`),
  `int pg_encoding_max_length(int encoding)` (`wchar.c:2012-2024`)
  — public verify and capacity entries.
- `void pg_encoding_set_invalid(int encoding, char *dst)` — write
  the canary pair into `dst[0..1]`; asserts
  `pg_encoding_max_length(encoding) > 1`. (`wchar.c:1851-1858`)

## State / globals

- `pg_wchar_table[]` const — the per-encoding function-pointer
  dispatch table, sparse-indexed by `pg_enc` enum.
  (`wchar.c:1865-1907`)

## Phase D notes

This is **the** trust boundary for "client claims encoding X is
this byte stream". Specific points:

- **Overlong UTF-8 rejection is explicit.** `pg_utf8_islegal` has
  dedicated case-blocks for the E0/ED/F0/F4 lead bytes precisely to
  block overlong encodings — e.g. C0 80 (overlong NUL) would slip
  through a naive "any 0x80-0xBF trailer" check, so the function
  requires the trailer to be 0xA0-0xBF for E0, etc.
  (`wchar.c:1799-1843`). `[verified-by-code]`
- **Surrogate range explicitly excluded for UTF-8.** The 0xED case
  restricts the second byte to 0x80-0x9F, blocking U+D800-U+DFFF
  (UTF-16 surrogate range) which UTF-8 must not encode.
  (`wchar.c:1817-1820`). `[verified-by-code]`
- **NONUTF8_INVALID canary is a documented compromise.** The 30-line
  comment at `wchar.c:21-35` explains that historically every
  encoding's `_verifychar` accepted "any non-NUL byte" as a
  trailer, even values outside the formal encoding spec. To avoid
  tightening verifiers in a security patch (which would break
  existing data), PG instead reserves `(0x8D, ' ')` as a known-bad
  byte pair that all verifiers reject. This is the byte pair
  `pg_encoding_set_invalid` writes when, e.g., a conversion fails
  mid-character and the caller wants a placeholder.
- **Tail-of-buffer truncation is the caller's problem.**
  `pg_encoding_mblen` does NOT take a length and may read past the
  buffer end if the first byte indicates a multi-byte sequence and
  the buffer is shorter than that. Hence
  `pg_encoding_mblen_or_incomplete` / `_bounded` — but the unsafe
  form is also exported and used. Anyone parsing a possibly-partial
  message in libpq must pick the right one. `[verified-by-code]`
- **Vectorised UTF-8 verify can backtrack.** When the fast-path
  loop exits in the middle of a multi-byte sequence,
  `pg_utf8_verifystr` walks backwards looking for the leading byte
  (`wchar.c:1731-1747`). The `Assert(s > start)` is the bound; in
  a non-cassert build a pathological input where the fast path
  thinks it's mid-sequence but actually started at offset 0 would
  underflow. The asserts cover the actual reachability.
- **GB18030 violates the "first byte tells you the length" rule.**
  The comment at `wchar.c:52-57` notes GB18030 is the exception,
  and that for any caller passing only the first byte the function
  still gives "a predictable answer" (treating a 4-byte char as
  two 2-byte chars). Any size-calculation that depends on
  byte-equals-char-length-1-by-1 needs to know this.

## Potential issues

`[ISSUE-trust-boundary: pg_encoding_mblen reads ahead by up to
maxmblen-1 bytes without length checking; callers must use
_or_incomplete or _bounded variants when buffer end is reachable.
The two contracts coexist as exported functions, easy to mix up.
(maybe)]`

`[ISSUE-correctness: NONUTF8_INVALID_BYTE0/1 canary doc says
"longstanding verifychar implementations accepted any non-NUL byte"
— meaning some legacy encodings still accept structurally-invalid
sequences other than the canary. Any conversion is paranoid, but
identity-encoded strings can still carry junk through verifymbstr
in non-UTF8 encodings. (maybe)]`

`[ISSUE-undocumented-invariant: pg_utf8_islegal rejects length 5/6
explicitly (returns false at default case, wchar.c:1796-1798) — so
a future change to enable longer UTF-8 must update at least four
named sites (`:546-554`). The list is documented in the function
header but not enforced. (low)]`

`[ISSUE-dos: pg_utf8_verifystr backtracks at the end of the
vectorised loop; well-bounded in practice but the do-while loop
relies on `IS_HIGHBIT_SET(*s)` being eventually true. (low)]`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
