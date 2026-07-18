# contrib/isn/{EAN13,ISBN,ISMN,ISSN,UPC}.h — combined doc

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Verification depth:** spot read of EAN13/ISSN/UPC headers; ISBN.h
read partially (24K); ISMN.h header line confirmed pattern matches.

## Role

Five parallel data-only headers, each declaring two `static const`
tables that map registration-group ranges → hyphenation patterns for
one specific ISN family. They're included once each by `isn.c` and used
by the `hyphenate()` / `dehyphenate()` helpers.

| Header | Range-table name | Index-table name | Notes |
|---|---|---|---|
| `EAN13.h` | `EAN13_range[][2]` | `EAN13_index[10][2]` | GS1 country prefixes (~119 ranges as of 2006-08-23) |
| `ISBN.h` | `ISBN_range[][2]` | `ISBN_index[10][2]` | ISBN registration groups (large, ~24K) |
| `ISMN.h` | `ISMN_range[][2]` | `ISMN_index[10][2]` | Tiny — ISMN namespace is small |
| `ISSN.h` | `ISSN_range[][2]` | `ISSN_index[10][2]` | Tiny |
| `UPC.h` | `UPC_range[][2] = {{NULL,NULL}};` | `UPC_index[10][2]` all-zero | **No UPC data published** — table is empty |

[verified-by-code] `source/contrib/isn/EAN13.h:14-25` (first 25 lines
of EAN13_index layout), `source/contrib/isn/UPC.h:14-27` (NULL-only
range), `source/contrib/isn/ISSN.h:1-30`.

## Public API

- These headers expose only `static const` arrays — they are NOT
  part of any external linkage surface. Included exclusively by
  `isn.c` (lines 17-21).

## Invariants

- INV-1: Each `_index[10][2]` is keyed by leading digit 0-9 of the
  prefix; `_index[d][0]` = start offset into `_range[]`,
  `_index[d][1]` = count.
  [verified-by-code] `source/contrib/isn/EAN13.h:14-25` +
  `source/contrib/isn/isn.c:67-141` (`check_table` walks the relationship).
- INV-2: Each `_range[]` entry is `{lo_string, hi_string}` of inclusive
  registration ranges, terminated by `{NULL, NULL}`.
  [verified-by-code] `source/contrib/isn/EAN13.h:26-30`, `UPC.h:25-27`.
- INV-3: Both strings of a range must have IDENTICAL hyphenation
  pattern and length (`check_table` enforces in DEBUG; not enforced at
  runtime).
  [verified-by-code] `source/contrib/isn/isn.c:90-106`
- INV-4: The `check_table` consistency check runs only when
  `USE_ASSERT_CHECKING` builds — production builds never validate the
  tables.
  [verified-by-code] `source/contrib/isn/isn.c:31-35, 906-919`

## Trust-boundary / Phase-D surface

- **All five tables are compiled in** — operator cannot supply new
  ranges. So no injection vector.
- **Unknown-prefix behavior**: if an EAN13 doesn't match ANY range in
  the table, `hyphenate()` falls back to the no-hyphenation copy
  (`while (*bufI) *bufO++ = *bufI++;` — see `source/contrib/isn/isn.c:189-198`).
  The number is still accepted as syntactically valid — only the
  PRETTY-PRINTING degrades.
  **ISSUE-D1 (info)**: silent fallback on unknown registration group
  means a typo-bad prefix is accepted as a valid ISBN/EAN13 without
  hint. That's the documented "weak" semantic; the strict checking
  is only of the *check digit*, not of *registration-group existence*.
- **UPC table is empty by upstream design** [verified-by-code:UPC.h:25-26]
  — UPC values bypass range-based hyphenation entirely.
- **Table-drift staleness**: registration tables are dated
  "recompiled August 23, 2006" in EAN13.h. Real-world prefix
  registrations have changed since then. **ISSUE-D2 (info,
  documentation)**: tables go stale; not a security issue but
  worth noting for users.
  [from-comment] `source/contrib/isn/EAN13.h:5`,
  `source/contrib/isn/ISSN.h:5`.
- **`check_table` only runs under ASSERT builds** — a production
  postmaster never validates table integrity at startup. A maintainer
  who edits one of these headers by hand and breaks the index could
  ship a bug to production. **ISSUE-D3 (low)**: DEBUG-only invariant
  check is OK because the tables are static, but future contributors
  should be reminded.
  [verified-by-code] `source/contrib/isn/isn.c:31-35, 906-919`

## Cross-refs

- `source/contrib/isn/isn.c:67-141` — `check_table` consistency check
  routine.
- `source/contrib/isn/isn.c:172-300` — `hyphenate()` consumers.

## Issues raised

- **ISSUE-D1 (info)** — silent no-hyphen fallback on unknown
  registration prefixes.
- **ISSUE-D2 (info)** — tables dated 2006 (EAN13) / 2004 (ISSN); real
  registration assignments have moved on.
- **ISSUE-D3 (low)** — `check_table` runs only in assert builds; no
  startup integrity check in production.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-isn.md](../../../subsystems/contrib-isn.md)
