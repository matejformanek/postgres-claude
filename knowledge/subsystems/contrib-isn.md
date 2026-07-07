# contrib-isn (international product numbering: EAN/UPC/ISBN/ISSN/ISMN)

- **Source path:** `source/contrib/isn/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.3` (per `isn.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

PG data types for **international product identifiers**:

- **EAN13** — European Article Number (13-digit, the modern
  barcode standard).
- **UPC** — Universal Product Code (12-digit, US/Canada
  legacy).
- **ISBN** — International Standard Book Number (10 or 13
  digits).
- **ISSN** — International Standard Serial Number
  (periodicals).
- **ISMN** — International Standard Music Number (sheet music).
- **EAN13/UPC/etc. unions** — for columns that may store
  any of the above.

Stored as `int8` internally; the type system ensures
correctness (check digits validated, ranges respected, format
output is hyphenated appropriately).

## 2. The single 1143-LOC file

```
source/contrib/isn/isn.c    1143 LOC
```

[verified-by-code `wc -l source/contrib/isn/isn.c`]

Compact for what it does — most of the volume is the lookup
table of country-and-publisher prefixes that determine where
the hyphens go.

## 3. The shared int8 representation

[verified-by-code `isn.c:338-353`]

All ISN types share a common internal representation: an
`int8` holding the 13-digit EAN form. Converting between
types is conversion of how the same int8 is INTERPRETED:

- An ISBN13 stored as EAN13 starts with 978 or 979.
- An ISSN13 starts with 977.
- An ISMN13 starts with 9790.
- A UPC is converted to EAN13 by prefixing 0.

The `ean2isn` function tries the conversion; succeeds if the
prefix matches; fails otherwise.

## 4. SQL surface — types + casts

| Type | Stored As | Valid input |
|---|---|---|
| `ean13` | int8 | 13-digit EAN |
| `isbn13` | int8 | 978/979-prefixed |
| `issn13` | int8 | 977-prefixed |
| `ismn13` | int8 | 9790-prefixed |
| `isbn` | int8 (legacy) | 10 or 13 digit ISBN |
| `issn` | int8 | 8-digit ISSN (auto-padded to ISSN13) |
| `ismn` | int8 | ISMN |
| `upc` | int8 | 12-digit UPC |

Implicit casts among the types where format-compatibility
allows. Strict types (`isbn13`, `issn13`, etc.) reject
mismatched prefixes; permissive types (`ean13`) accept
anything.

## 5. The check digit

Every ISN includes a **check digit** computed from the other
digits using a weighted-modulo formula. The library validates
on input — `'9780123456788'::isbn13` parses OK; mutating one
digit causes `ERROR: invalid check digit`.

```c
static ean13 string2ean(...)
```

[verified-by-code `isn.c:662`]

Parses the input string, validates the check digit, returns
the int8. The check function is exposed via SQL:

```sql
SELECT is_valid('9780123456788'::isbn13);  -- true
SELECT is_valid('9780123456787'::isbn13);  -- false (bad check digit)
```

## 6. Output formatting

The output is hyphenated:

```
'9780123456788'::isbn13 displays as '978-0-12-345678-8'
```

[verified-by-code `isn.c:528`]

The hyphens come from a lookup table that maps publisher
ranges (`isn-ranges.c` is generated from the ISO 2108
ranges). The publisher prefix determines where hyphens go.

There's a GUC `isn.weak` (default off) — when on, weakly-
formatted output is allowed (e.g. unhyphenated). Strong
formatting is the default.

## 7. Range table

The `isn-ranges.c` file is a generated table of valid
prefixes per publisher group. It's the part of the
extension that gets updated as ISBN agencies allocate new
publisher prefixes — typically every few PG versions.

Storing a value with an unknown prefix succeeds, but
hyphenation falls back to the generic pattern.

## 8. Production-use guidance

- **For e-commerce catalogs**, use the appropriate
  specific type (`upc`, `isbn13`) for strict validation.
- **For union storage** (mixed product types), use
  `ean13` and tag the row with a category enum.
- **For sorting**, all ISN types compare as int8 — no
  special handling needed.
- **Indexes work normally** with btree.

## 9. Invariants

- **[INV-1]** Stored as int8 internally; type tagged at
  the catalog level.
- **[INV-2]** Check digit validated on input; ERRORs on
  mismatch.
- **[INV-3]** Hyphenation determined by prefix lookup
  table; unknown prefixes get generic format.
- **[INV-4]** Implicit casts among compatible types
  (e.g., ISBN13 → EAN13).
- **[INV-5]** Trusted extension; CREATE EXTENSION without
  superuser.

## 10. Useful greps

- All ISN types:
  `grep -RIn 'typedef.*ean\|isbn\|issn\|ismn' source/contrib/isn/*.h`
- The input parser:
  `grep -n 'string2ean\|ean2isn' source/contrib/isn/isn.c | head -5`
- The output formatter:
  `grep -n 'ean2string' source/contrib/isn/isn.c`

## 11. Cross-references

- `.claude/skills/fmgr-and-spi/SKILL.md` — custom type
  registration pattern.
- `.claude/skills/catalog-conventions/SKILL.md` —
  pg_type catalog entries.
- `knowledge/subsystems/contrib-citext.md` — sibling
  custom-type contrib.
- `knowledge/data-structures/heap-tuple-layout.md` —
  int8 storage layout.
- `source/contrib/isn/isn.c` — implementation.
- `source/contrib/isn/isn-ranges.c` — the prefix-to-
  hyphen-position lookup table.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**8 files.**

| File |
|---|
| [`contrib/isn/EAN13.h`](../files/contrib/isn/EAN13.h.md) |
| [`contrib/isn/ISBN.h`](../files/contrib/isn/ISBN.h.md) |
| [`contrib/isn/ISMN.h`](../files/contrib/isn/ISMN.h.md) |
| [`contrib/isn/ISSN.h`](../files/contrib/isn/ISSN.h.md) |
| [`contrib/isn/UPC.h`](../files/contrib/isn/UPC.h.md) |
| [`contrib/isn/isn.c`](../files/contrib/isn/isn.c.md) |
| [`contrib/isn/isn.h`](../files/contrib/isn/isn.h.md) |
| [`contrib/isn/isn_data_headers`](../files/contrib/isn/isn_data_headers.md) |

<!-- /files-owned:auto -->
