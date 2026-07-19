# `contrib/isn/UPC.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 28
- **Source:** `source/contrib/isn/UPC.h`

Pure data header: two `static const` tables for UPC (Universal Product
Code). Notably, **both tables are empty** — the header comment says
"No information available for UPC prefixes". `UPC_index[10][2]` is
all-zeros and `UPC_range[][2]` contains only the `{NULL, NULL}`
terminator. This means UPC values bypass range-based hyphenation
entirely in `isn.c::hyphenate()`. [verified-by-code]

## API / entry points

- `UPC_index[10][2]` `:14-25` — all entries `{0, 0}`. [verified-by-code]
- `UPC_range[][2]` `:26-28` — only `{NULL, NULL}` terminator.
  [verified-by-code]

## Notable invariants / details

- See **`knowledge/files/contrib/isn/isn_data_headers.md`** for the
  combined analysis. [verified-by-code]
- **UPC is intentionally undata'd** — comment `:5` says "No
  information available for UPC prefixes". `hyphenate()` therefore
  always falls through to the no-hyphen copy for UPC. The check-
  digit validation still works (it doesn't depend on the prefix
  tables). [from-comment + verified-by-code]
- The empty tables are still compiled in for symmetry with the
  other four families — keeps the `isn.c` dispatch code uniform.
  [inferred]

## Potential issues

- UPC has no pretty-printing — minor user-facing inconsistency vs
  ISBN/EAN13 (see combined doc ISSUE-D1). [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-isn.md](../../../subsystems/contrib-isn.md)
