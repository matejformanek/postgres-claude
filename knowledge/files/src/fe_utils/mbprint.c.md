# `src/fe_utils/mbprint.c`

- **File:** `source/src/fe_utils/mbprint.c` (405 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

Multibyte-aware display-width and formatting helpers for frontend table output (consumed
by `print.c`). Computes how many terminal columns a string occupies (`pg_wcswidth`),
sizes/renders a string into per-line buffers expanding control characters to escape
sequences (`pg_wcssize`/`pg_wcsformat`), and strips unvalidatable bytes from a string
(`mbvalidate`). All width/length decisions defer to libpq's `PQmblen`/`PQdsplen` rather
than backend `pg_wchar.h`, deliberately, to avoid version skew between the libpq the tool
links against and the headers it compiled with. `[from-comment]` (mbprint.c:20-29)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `pg_wcswidth` | :177 | "Dumb" single-line display width of `len` bytes; sums `PQdsplen` per char. |
| `pg_wcssize` | :211 | Compute longest-line width, line count (height), and bytes needed for the formatted form. Must stay in sync with `pg_wcsformat`. |
| `pg_wcsformat` | :294 | Render the string into a `struct lineptr[]` array, expanding `\r`/`\t`/control chars; sets each line's `width`. Must stay in sync with `pg_wcssize`. |
| `mbvalidate` | :392 | Delete unvalidatable characters in place; UTF-8 only today. Returns the same buffer. |

## Internal landmarks

- `pg_get_utf8_id()` / `PG_UTF8` macro `mbprint.c:33-43` — resolves the UTF-8 encoding ID
  *at runtime* via `pg_char_to_encoding("utf8")`, cached in a static. This is the concrete
  mechanism for the version-skew avoidance. `[verified-by-code]`
- `utf8_to_unicode()` `mbprint.c:52-72` — decode one UTF-8 sequence to a code point with
  **no error checking**; caller must guarantee a long-enough buffer. Returns `0xffffffff`
  for an unrecognized lead byte. Used only to render `\uXXXX` escapes in `pg_wcsformat`. `[from-comment]` (:48-51)
- `utf_charcheck()` `mbprint.c:81-132` — "Unicode 3.1 compliant" per-sequence validator;
  returns byte length 1-4 for a valid sequence or `-1`. Rejects overlongs, `0xFFFE/0xFFFF`
  noncharacters, the `0xFDD0..0xFDEF` range, and surrogates. `[from-comment]` (:75-80)
- `mb_utf_validate()` `mbprint.c:135-165` — walks the string; copies valid sequences down
  in place (compaction), skips invalid bytes one at a time, re-terminates with `\0`. `[verified-by-code]`
- **Control-char width/format encoding** (shared contract between `pg_wcssize` and
  `pg_wcsformat`): `\n` ends a line; `\r` → `\r` literal, width 2 (mbprint.c:238-242, :324-329);
  `\t` → spaces to next multiple of 8 (mbprint.c:243-250, :330-337); single-byte control
  → `\xNN`, width 4 (mbprint.c:251-255, :338-343); non-ASCII control (UTF-8) → `\uXXXX`,
  width 6 (mbprint.c:262-266, :350-365). `[verified-by-code]`

## Invariants & gotchas

- **`pg_wcssize` and `pg_wcsformat` MUST stay in sync.** Both files say so explicitly
  (mbprint.c:208, :291). `pg_wcssize` precomputes `result_format_size`; `pg_wcsformat`
  then writes into a buffer of exactly that size. A mismatch is a buffer overrun, not a
  graceful failure. `[from-comment]`
- **Hard `exit(1)` on undersized `lines[]` array.** `pg_wcsformat` calls `exit(1)` if the
  caller passed too few `lineptr` slots for the newlines it finds (mbprint.c:318-319, :379-380).
  Callers (print.c) size the array from `pg_wcssize`'s height result, so the exit is an
  internal-consistency guard, commented "Screwup". `[from-comment]`
- **mbvalidate validates UTF-8 only.** Every other encoding is passed through untouched —
  the `else` branch is an empty placeholder (mbprint.c:396-402). So for, e.g., a malformed
  EUC/SJIS byte stream, downstream width math relies entirely on libpq's `PQmblen`/`PQdsplen`
  treating it sanely. `[verified-by-code]`
- **`pg_wcswidth` stops at the first truncated multibyte char** (`len < chlen`) and returns
  the width accumulated so far, silently (comment: "Invalid string"). It does not signal the
  truncation to the caller (mbprint.c:187-188). `[from-comment]`
- Negative `PQdsplen` (control chars) contributes 0 to `pg_wcswidth` (the `chwidth > 0` guard,
  mbprint.c:191-192) but is expanded to a multi-column escape in `pg_wcssize`/`pg_wcsformat`.
  The two width notions intentionally differ. `[verified-by-code]`
- Memory: this file allocates nothing of its own; `pg_wcsformat` writes into a buffer the
  caller (print.c `format_buf[]`) owns. `mbvalidate` mutates in place. `[verified-by-code]`

## Cross-references

- `knowledge/files/src/fe_utils/print.c.md` — sole consumer; `print_aligned_text` calls
  `pg_wcssize`/`pg_wcsformat` to lay out cells (`source/src/fe_utils/print.c:731`, `:750`),
  and `printTableAddHeader`/`printTableAddCell` call `mbvalidate` (`source/src/fe_utils/print.c:3254`, `:3296`).
- `source/src/include/fe_utils/mbprint.h` — declares these symbols and `struct lineptr`.
- libpq width primitives: `source/src/interfaces/libpq/fe-misc.c` (`PQmblen`, `PQdsplen`),
  `source/src/interfaces/libpq/fe-connect.c` (`pg_char_to_encoding`).

## Potential issues

- **[ISSUE-undocumented-invariant: pg_wcsformat trusts caller-sized buffers]** `mbprint.c:294`
  — `pg_wcsformat` writes into `lines->ptr` (caller's `format_buf[i]`) with no length
  parameter; correctness depends entirely on the caller having sized that buffer from a
  prior `pg_wcssize` call on the *same* string with the *same* encoding. The two functions
  carry "MUST be kept in sync" comments but nothing enforces it at the type level. This is a
  known, longstanding contract, not a live bug. (maybe)
- **[ISSUE-correctness: mbvalidate is a no-op for non-UTF-8 encodings]** `mbprint.c:396-402`
  — for any non-UTF-8 multibyte encoding, malformed input is not stripped, so invalid byte
  sequences reach `PQmblen`/`PQdsplen` and the terminal. The file's own comment ("other
  encodings needing validation should add their own routines here") acknowledges the gap.
  Impact is cosmetic (garbled output) rather than a memory-safety issue, since width math
  still advances by `PQmblen`. (nit)

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 6
