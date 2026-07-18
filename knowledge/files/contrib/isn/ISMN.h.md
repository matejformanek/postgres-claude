# `contrib/isn/ISMN.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 52
- **Source:** `source/contrib/isn/ISMN.h`

Pure data header: two `static const` tables (`ISMN_index[10][2]` and
`ISMN_range[][2]`) for International Standard Music Numbers. Very
small — the ISMN namespace lives entirely under leading digit `0`
because every ISMN starts with `M-` (or `979-0-...` in 13-digit form).
Dated "recompiled November 12, 2004". Header includes worked
check-digit examples. [verified-by-code]

## API / entry points

- `ISMN_index[10][2]` `:33-44` — only digit 0 has nonzero count (5);
  digits 1-9 have `{5, 0}` (i.e. zero ranges). [verified-by-code]
- `ISMN_range[][2]` `:45-52` — five inclusive ranges plus the
  terminator. [verified-by-code]

## Notable invariants / details

- See **`knowledge/files/contrib/isn/isn_data_headers.md`** for the
  combined analysis. [verified-by-code]
- The "M counts as 3" rule explained in the comment `:13`-ish is a
  historical convention; `M-...` ISMNs convert to `979-0-...` for
  EAN-13 compatibility. [from-comment]
- All ISMN ranges live under index 0 because the encoded
  EAN-13 form starts `9-7-9-0-...` and `hyphenate()` indexes on the
  *registration-group* digit, which is always 0. [verified-by-code +
  inferred]

## Potential issues

- Stale table dated 2004 (see combined doc ISSUE-D2). [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-isn.md](../../../subsystems/contrib-isn.md)
