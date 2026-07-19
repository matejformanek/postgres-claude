# `contrib/isn/EAN13.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 148
- **Source:** `source/contrib/isn/EAN13.h`

Pure data header: two `static const` tables (`EAN13_index[10][2]`
and `EAN13_range[][2]`) declaring the GS1 country-prefix registration
ranges used by `isn.c::hyphenate()` to pretty-print EAN-13 codes.
Dated "recompiled August 23, 2006". Included exclusively by `isn.c`.
[verified-by-code]

## API / entry points

- `EAN13_index[10][2]` `:14-25` — keyed by leading digit 0-9 of the
  EAN; each entry is `{start_offset_into_range, count}`. [verified-by-code]
- `EAN13_range[][2]` `:26-…` — `{lo_str, hi_str}` inclusive range
  pairs (hyphenated GS1 country/registrant prefix), terminated by
  `{NULL, NULL}`. ~119 ranges total. [verified-by-code]

## Notable invariants / details

- See **`knowledge/files/contrib/isn/isn_data_headers.md`** for the
  full cross-cutting analysis of all five `EAN13.h`, `ISBN.h`,
  `ISMN.h`, `ISSN.h`, `UPC.h` headers — invariants INV-1..INV-4,
  hyphenate fallback semantics, table-staleness issue, and
  ASSERT-only `check_table` consistency check. This per-file doc
  exists only to satisfy the file-by-file registry; the analytical
  content lives in the combined doc. [verified-by-code]
- Date in header `:5` reads "Information recompiled by Kronuz on
  August 23, 2006" — stale by ~20 years vs. live GS1 registry.
  [from-comment]

## Potential issues

- Stale tables (see combined doc ISSUE-D2). [from-comment]
- Silent fallback on unknown prefix (see combined doc ISSUE-D1).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-isn.md](../../../subsystems/contrib-isn.md)
