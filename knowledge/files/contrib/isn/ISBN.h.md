# `contrib/isn/ISBN.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 990
- **Source:** `source/contrib/isn/ISBN.h`

Pure data header: two `static const` tables (`ISBN_index[10][2]` and
`ISBN_range[][2]`) declaring ISBN registration-group ranges used by
`isn.c::hyphenate()` to format ISBN-13. The biggest of the five data
headers (~24K, ~970 ranges). Dated "recompiled June 20, 2006".
Header comment also contains a worked check-digit example for the
ISBN 0-393-04002-X / 978-0-393-04002-9 conversion. [verified-by-code]

## API / entry points

- `ISBN_index[10][2]` — keyed by leading digit of ISBN-13; each
  entry is `{start_offset_into_range, count}`. [verified-by-code]
- `ISBN_range[][2]` — `{lo_str, hi_str}` inclusive range pairs,
  terminated by `{NULL, NULL}`. [verified-by-code]

## Notable invariants / details

- See **`knowledge/files/contrib/isn/isn_data_headers.md`** for the
  full analysis covering all five data headers. This per-file doc is
  a pointer; the analytical content lives in the combined doc.
  [verified-by-code]
- ISBN data is the largest by far (~24K of header text) because
  the ISBN registration namespace is the most-populated of the five
  ISN families. [verified-by-code]
- Header includes a worked example of the ISBN check-digit
  computation `:12-25`-ish. [from-comment]

## Potential issues

- Stale tables (see combined doc ISSUE-D2). [from-comment]
- Silent fallback on unknown prefix (see combined doc ISSUE-D1).
