# `contrib/isn/ISSN.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 49
- **Source:** `source/contrib/isn/ISSN.h`

Pure data header: two `static const` tables (`ISSN_index[10][2]` and
`ISSN_range[][2]`) for International Standard Serial Numbers.
Tiny — ISSN has only ONE range `{"0000-000", "9999-999"}` covering
the entire 7-digit ISSN space. Dated "recompiled November 12, 2004".
Header comment includes worked check-digit examples. [verified-by-code]

## API / entry points

- `ISSN_index[10][2]` `:34-45` — every digit 0-9 maps to
  `{0, 1}`: the single range covers all leading digits. [verified-by-code]
- `ISSN_range[][2]` `:46-49` — one inclusive range plus the
  `{NULL, NULL}` terminator. [verified-by-code]

## Notable invariants / details

- See **`knowledge/files/contrib/isn/isn_data_headers.md`** for the
  combined analysis. [verified-by-code]
- Because there's only one range, hyphenation is always
  `XXXX-YYY` — four digits, hyphen, three digits — for every
  ISSN. [verified-by-code + inferred]
- The comment at `:11-29` walks through both the 7-digit and 13-digit
  (with `977` GS1 prefix) check-digit calculations. [from-comment]

## Potential issues

- Stale table dated 2004 (see combined doc ISSUE-D2). [from-comment]
