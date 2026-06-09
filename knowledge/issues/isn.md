# Issues — `contrib/isn`

International Standard Numbers (ISBN/ISSN/ISMN/EAN13/UPC) datatype. 9 source files / ~2442 LOC.

**Parent docs:** `knowledge/files/contrib/isn/*` (3 docs: `isn.c.md`, `isn.h.md`, `isn_data_headers.md` combining EAN13/ISBN/ISMN/ISSN/UPC headers).

**Source:** 6 entries surfaced 2026-06-09 by A14-2.

## Headlines

1. **`isn.weak` is `PGC_USERSET`** — any role can opt their session into accepting bad ISBN check digits. Combined with `accept_weak_input(bool)` SQL function that side-effects the GUC, this is the module's main "weak input" surface. By design but worth tracking for integrity-sensitive applications.
2. **Registration tables dated 2004/2006** — real-world ISBN/ISSN assignments have moved on; silent no-hyphen fallback on unknown prefixes.
3. **`check_table` consistency check runs only under ASSERT** — corrupt data tables wouldn't be caught in production builds.

## Entries — `isn.c`

- [ISSUE-correctness: unknown registration prefix silently accepted; only check digit validated (nit)] — by design.
- [ISSUE-api-shape: `accept_weak_input(bool)` SQL function mutates session GUC (nit)] — `:1126-1136`

## Entries — `isn.h`

- [ISSUE-api-shape: orphan `extern void initialize(void);` declaration with no definition (nit)] — `:30`

## Entries — data headers (`EAN13.h` / `ISBN.h` / `ISMN.h` / `ISSN.h` / `UPC.h`)

- [ISSUE-correctness: silent no-hyphen fallback on unknown registration prefixes (nit)] — `isn.c:189-198`
- [ISSUE-documentation: registration tables dated 2004/2006; real assignments have moved on (nit)] — `EAN13.h:5`, `ISSN.h:5`
- [ISSUE-correctness: `check_table` consistency check runs only under ASSERT (maybe)] — `isn.c:31-35,906-919`
