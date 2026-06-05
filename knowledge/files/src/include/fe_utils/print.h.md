---
path: src/include/fe_utils/print.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 238
depth: read
---

# `src/include/fe_utils/print.h`

- **File:** `source/src/include/fe_utils/print.h` (238 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Public API + data model for the frontend query-result table formatter implemented
in [[knowledge/files/src/fe_utils/print.c]]. Declares the eight output formats
(`enum printFormat`), the option struct (`printTableOpt`), the content-accumulator
struct (`printTableContent`), and the higher-level `printQueryOpt`. This is the
struct that `psql`'s `\pset` machinery, `pg_amcheck`, `clusterdb`, etc. populate to
control aligned/CSV/HTML/LaTeX/troff output. The load-bearing definitions live here;
the rendering logic lives in `print.c`. `[verified-by-code]`

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `enum printFormat` | :28 | 8 output formats — `PRINT_NOTHING`(0) sentinel + aligned/asciidoc/csv/html/latex/latex-longtable/troff-ms/unaligned/wrapped. |
| `printTextLineFormat` | :43 | Line-drawing character set for one rule context (hrule + 3 vrules). |
| `printTextRule` | :52 | Enum indexing `lrule[4]` (TOP/MIDDLE/BOTTOM/DATA). |
| `printTextLineWrap` | :61 | Wrap conditions (NONE/WRAP/NEWLINE). |
| `printXheaderWidthType` | :69 | Expanded-header width policy (FULL/COLUMN/PAGE/EXACT_WIDTH). |
| `printTextFormat` | :81 | A complete line style (name + `lrule[4]` + wrap/newline marks). |
| `unicode_linestyle` | :99 | SINGLE(0)/DOUBLE for unicode border/column/header. |
| `printTableOpt` | :111 | The big options struct — format, border, pager, separators, encoding, columns, unicode styles. |
| `printTableFooter` | :153 | Singly-linked footer list node. |
| `printTableContent` | :163 | Cell/header/footer accumulator — `Init()` then `AddHeader`/`AddCell`/`AddFooter`. |
| `printQueryOpt` | :183 | `printTableOpt` + null/true/false-print + title/footer overrides + header translation. |
| `printTableInit` etc. | :215-229 | Content lifecycle + `printTable`/`printQuery` entry points. |
| `column_type_alignment` | :232 | Map a column type Oid → `'l'`/`'r'` alignment. |
| `get_line_style` / `refresh_utf8format` | :235-236 | Resolve/refresh the active `printTextFormat`. |

## Internal landmarks

- `printTableContent` (`:163-181`) is a **dual-pointer accumulator**: `headers`/`header`,
  `cells`/`cell`, `footers`/`footer`, `aligns`/`align` each pair a base array with a
  "last added" cursor. `cellsadded` (`uint64`, :174) counts cells; `cellmustfree` (:175)
  is a parallel bool array marking which cells `printTableCleanup` must `free()`. `[verified-by-code]`
- Footers are a linked list (`:146-157`) explicitly so the count needn't be known at
  `Init()` time — convenient for `describeOneTableDetails` building complex footers. `[from-comment]` (:147-152)
- `csvFieldSep[2]` (:134) is a 1-char + NUL field separator for CSV; `fieldSep`/`recordSep`
  are `struct separator` (string + zero-byte flag) for unaligned mode. `[verified-by-code]`

## Invariants & gotchas

- **`pg_utf8format` is a mutable non-const global** (`:202-203`), unlike its const siblings
  `pg_asciiformat`/`pg_asciiformat_old` (:200-201). The comment admits "ideally would be
  const, but...": `refresh_utf8format()` rewrites it in place from the active `printTableOpt`.
  Frontend code is single-threaded so this is benign, but it means the UTF-8 line style is
  process-global mutable state, not per-call. `[from-comment]` (:202)
- `cancel_pressed` (`:198`) is a `volatile sig_atomic_t` exported here even though it is a
  cancellation flag (the natural home would be `cancel.h`); `print.c` checks it in the row
  loop to abort long output. Cross-module global. `[verified-by-code]`
- `PRINT_NOTHING = 0` (`:30`) is a deliberate "someone forgot to initialize" sentinel —
  a zeroed `printTableOpt` selects no format and is caught rather than silently aligned. `[from-comment]` (:30)

## Cross-refs

- Implementation: [[knowledge/files/src/fe_utils/print.c]] (the 8-format dispatch, width math).
- Multibyte width helpers it relies on: [[knowledge/files/src/include/fe_utils/mbprint.h]].
- Companion accumulator gotcha (`width_total` 32-bit overflow flag) tracked in
  `knowledge/issues/fe_utils.md` row `print.c:776`.

## Potential issues

- **[ISSUE-undocumented-invariant: `pg_utf8format` is mutable process-global state]**
  `print.h:202` — `pg_utf8format` is exported non-const and mutated in place by
  `refresh_utf8format()`. Benign under the frontend single-threaded model, but it is the one
  `printTextFormat` that is not immutable; any future threaded consumer of `fe_utils` (e.g. a
  parallel formatter) would race on it. Severity `nit`. Mirrored to `knowledge/issues/fe_utils.md`.
