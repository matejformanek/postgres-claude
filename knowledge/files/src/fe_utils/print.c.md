# `src/fe_utils/print.c`

- **File:** `source/src/fe_utils/print.c` (3974 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

The psql/frontend result-set formatter. Given a `printTableContent` (headers,
flat cell array, footers, alignment, options) it renders the table in any of
the supported output formats — unaligned, aligned, wrapped, csv, html,
asciidoc, latex, latex-longtable, troff-ms — each with a "horizontal" and an
"expanded/vertical" variant. It owns column-width computation, optional word
wrap to terminal width, numeric-locale grouping, the Unicode/ASCII line-style
tables, and pager spawning. Entry points are `printTable` (data already in a
`printTableContent`) and `printQuery` (build a `printTableContent` from a
`PGresult`). `[verified-by-code]`

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `printTable` | :3636 | Top-level format dispatch; spawns pager for non-aligned formats. |
| `printQuery` | :3742 | Build a `printTableContent` from a `PGresult`, then call `printTable` + cleanup. |
| `printTableInit` | :3191 | Init a content struct; allocates headers/cells/aligns with overflow check. |
| `printTableAddHeader` | :3239 | Append a header (validated via `mbvalidate`, optionally translated). |
| `printTableAddCell` | :3279 | Append a cell; lazily allocates `cellmustfree[]`. |
| `printTableAddFooter` | :3329 | Append a footer (strdup'd, linked list). |
| `printTableSetFooter` | :3354 | Replace the last footer's text. |
| `printTableCleanup` | :3372 | Free all owned memory; re-usable after re-init. |
| `PageOutput` | :3078 | Open a pager pipe if output exceeds the screen. |
| `ClosePager` | :3160 | Close a pager pipe, restoring SIGPIPE state. |
| `set_sigpipe_trap_state` | :3060 | Set the "always ignore SIGPIPE" flag. |
| `column_type_alignment` | :3811 | Map a column type OID to 'l'/'r' alignment. |
| `setDecimalLocale` | :3839 | Cache decimal point / thousands sep / grouping from locale. |
| `get_line_style` | :3875 | Pick the active `printTextFormat` (ascii/unicode). |
| `refresh_utf8format` | :3889 | Rebuild the unicode line-style table from `\pset` border/column/row style. |

The `printTextFormat` tables `pg_asciiformat` `:61`, `pg_asciiformat_old`
`:82`, and `unicode_style` `:145` are file-scope constants consumed by the
aligned writers. `[verified-by-code]`

## Internal landmarks

### Format dispatch (`printTable`, `:3660`)

`switch (cont->opt->format)` selects a per-format writer, each branching on
`expanded == 1` (vertical) vs. horizontal:

| `format` | horizontal | vertical (`expanded==1`) |
|---|---|---|
| `PRINT_UNALIGNED` | `print_unaligned_text` :438 | `print_unaligned_vertical` :529 |
| `PRINT_ALIGNED` / `PRINT_WRAPPED` | `print_aligned_text` :651 | `print_aligned_vertical` :1304 |
| `PRINT_CSV` | `print_csv_text` :1865 | `print_csv_vertical` :1905 |
| `PRINT_HTML` | `print_html_text` :1978 | `print_html_vertical` :2067 |
| `PRINT_ASCIIDOC` | `print_asciidoc_text` :2171 | `print_asciidoc_vertical` :2281 |
| `PRINT_LATEX` | `print_latex_text` :2439 | `print_latex_vertical` :2702 |
| `PRINT_LATEX_LONGTABLE` | `print_latex_longtable_text` :2546 | `print_latex_vertical` :2702 |
| `PRINT_TROFF_MS` | `print_troff_ms_text` :2812 | `print_troff_ms_vertical` :2904 |

`PRINT_NOTHING` returns early `:3644`; unknown format → `exit(EXIT_FAILURE)`
`:3718-3721`. In expanded-auto mode (`expanded==2`) a pager forces vertical
`:3676-3677`. `[verified-by-code]`

### Column-width computation (`print_aligned_text`, `:651`)

The workhorse. Per-column metric arrays are allocated with `pg_malloc0_array`
`:695-706`. Two scan passes feed `pg_wcssize` (from `mbprint.c`):

1. headers `:725-741` — fill `max_width[]`, `max_nl_lines[]`, `max_bytes[]`,
   `width_header[]`.
2. cells `:744-765` — update the same maxima plus `width_average[]`; cell
   count derives row count for the average `:768-773`.

`width_total` accumulates border overhead + every `max_width[i]` `:776-789`.
Line-pointer + format buffers are sized from `max_nl_lines`/`max_bytes`
`:798-807`. Target terminal width comes from `\pset columns`, else `$COLUMNS`,
else `TIOCGWINSZ` ioctl `:813-831`. For `PRINT_WRAPPED`, columns with the
highest max/avg ratio are shrunk in a loop until `width_total <= output_columns`
`:833-...`. `[verified-by-code]`

### Per-format escaping helpers

`csv_escaped_print` :1825, `html_escaped_print` :1937, `asciidoc_escaped_print`
:2153, `latex_escaped_print` :2377, `troff_ms_escaped_print` :2795. Numeric
locale grouping: `format_numeric_locale` :330, `integer_digits` :294,
`additional_numeric_locale_len` :305. `_print_horizontal_line` :609 draws
aligned rule lines. `[verified-by-code]`

### Pager handling

`PageOutput` :3078 → `PageOutputInternal` :3090 decides via `IsPagerNeeded`
:3430 / `count_table_lines` :3463 whether output exceeds the screen, then
`popen`s `$PAGER`. SIGPIPE is trapped around pager writes via
`disable_sigpipe_trap` :3024 / `restore_sigpipe_trap` :3047. The aligned
writers manage the pager themselves; `printTable` only auto-pages the other
formats `:3647-3654`. `[verified-by-code]` `[from-comment]`

## Invariants & gotchas

- **Frontend memory model.** All allocations are `pg_malloc*` / `pg_strdup`;
  frees are plain `free`. `printTableContent` does NOT duplicate headers,
  cells (unless `mustfree`), or the title — the caller must keep them alive
  for the struct's lifetime. `:3184-3185`, `:3229-3230`, `:3269-3270`
  `[from-comment]`
- **`printTableContent` lifecycle.** `printTableInit` (alloc) → repeated
  `printTableAddHeader`/`AddCell`/`AddFooter` (which advance the `header` /
  `cell` / `footer` walk pointers) → `printTable` → `printTableCleanup`.
  Cleanup frees only cells flagged in `cellmustfree[]`, then headers/cells/
  aligns arrays and the footer list `:3374-3413`. `printQuery` does the full
  cycle for you `:3745-3807`. `[verified-by-code]`
- **Overflow guard at init.** `total_cells = (uint64) ncolumns * nrows` is
  checked against `SIZE_MAX / sizeof(*cells)` before allocation; on overflow
  it prints and `exit(EXIT_FAILURE)` rather than allocating a truncated array
  `:3203-3212`. `printTableAddCell` re-checks `cellsadded < total_cells`
  `:3288-3294`. `[verified-by-code]`
- **Every header/cell is `mbvalidate`d.** Add-time scrubbing (`:3254`,
  `:3296`) means the width passes can assume the UTF-8 invariant; see
  `mbprint.c.md`. `[verified-by-code]`
- **`border > 2` is clamped to 2** in the aligned writer `:689-690`.
  `[verified-by-code]`
- **`cancel_pressed` short-circuits** `printTable` `:3641`, `printQuery`
  `:3750`, and `print_aligned_text` `:686` so a Ctrl-C mid-render bails
  cleanly. `[verified-by-code]`

## Cross-references

- `source/src/fe_utils/mbprint.c:210` (`pg_wcssize`), `:293` (`pg_wcsformat`),
  `:391` (`mbvalidate`) — width/format/validation backend.
  `knowledge/files/src/fe_utils/mbprint.c.md`
- `source/src/bin/psql/` — psql consumes this API via `fe_utils/print.h`
  (the `\pset` machinery sets `printTableOpt`). `[inferred]`
- `source/src/include/fe_utils/print.h` — `printTableContent`,
  `printTableOpt`, `printQueryOpt`, the `printFormat` enum, `printTextFormat`.
- `column_type_alignment` `:3811` uses type OIDs (`INT4OID`, `NUMERICOID`, …)
  from `catalog/pg_type_d.h`. `[verified-by-code]`

## Potential issues

- **[ISSUE-correctness: `width_total` is `unsigned int`, additive over all
  columns]** `print.c:673`, `:776-789` — the giant width sum and the per-format
  border overhead (`col_count * 3 + 1`) accumulate into a 32-bit `unsigned
  int`. A pathological result set (very many columns and/or extremely wide
  cells whose `max_width` sum exceeds ~4 G) could wrap, corrupting the wrap
  decision and buffer math. The cell-count overflow is guarded at init
  (`:3203`), but the *display-width* sum is not range-checked. Requires
  multi-gigabyte-wide output to trigger, so practically unreachable. (maybe)
- **[ISSUE-doc-drift: latex-longtable vertical reuses plain latex writer]**
  `print.c:3706-3710` — `PRINT_LATEX_LONGTABLE` dispatches its vertical case to
  `print_latex_vertical` (the non-longtable writer), same as `PRINT_LATEX`.
  This is intentional (longtable only differs in the horizontal/tabular case)
  but is undocumented at the switch site; a reader may mistake it for a
  copy-paste bug. (nit)

## Confidence tag tally

- `[verified-by-code]` × 15
- `[from-comment]` × 3
- `[inferred]` × 2
