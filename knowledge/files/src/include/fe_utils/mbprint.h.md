---
path: src/include/fe_utils/mbprint.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 30
depth: read
---

# `src/include/fe_utils/mbprint.h`

- **File:** `source/src/include/fe_utils/mbprint.h` (30 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Declares the multibyte-aware display-width helpers the frontend table formatter uses to align
columns correctly under wide/combining characters. Defines `struct lineptr` (a display line +
its width) and four functions for validating, measuring, and laying out multibyte strings.
Implementation in [[knowledge/files/src/fe_utils/mbprint.c]]. `[from-comment]` (:1-12)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `struct lineptr` | :16 | One wrapped display line: `unsigned char *ptr` + `int width`. |
| `mbvalidate` | :22 | Validate/repair a multibyte string for an encoding (UTF-8 only; see gotcha). |
| `pg_wcswidth` | :23 | Display width of a string (accounts for wide/zero-width chars). |
| `pg_wcsformat` | :24 | Lay a string out into `struct lineptr lines[count]`. |
| `pg_wcssize` | :26 | Measure width/height/format-size before laying out. |

## Internal landmarks

- `pg_wcssize` (`:26-28`) is the "measure" pass that `print.c` runs before `pg_wcsformat`
  (`:24`) "lays out": the former returns `result_width`/`result_height`/`result_format_size`,
  the latter fills caller-allocated `struct lineptr` lines. The two must be called with the
  same string + encoding. `[verified-by-code]`
- `pg_wcswidth` (`:23`) is the lighter single-line width used where only column-width math is
  needed (no layout). `[inferred]`

## Invariants & gotchas

- **`pg_wcsformat` writes into a caller buffer with no length parameter** — correctness depends
  on a matching prior `pg_wcssize` call producing the array size. The "keep in sync" obligation
  is comment-only; a mismatched pair overruns. Tracked in `knowledge/issues/fe_utils.md` row
  `mbprint.c:294`. `[verified-by-code]`
- **`mbvalidate` is effectively a no-op for non-UTF-8 multibyte encodings** — malformed bytes
  in e.g. EUC/SJIS reach the terminal; width math still advances by `PQmblen`. Cosmetic, tracked
  in `knowledge/issues/fe_utils.md` row `mbprint.c:396`. `[verified-by-code]`

## Cross-refs

- Implementation + both register rows: [[knowledge/files/src/fe_utils/mbprint.c]].
- Sole consumer: [[knowledge/files/src/include/fe_utils/print.h]] / `print.c`.

## Potential issues

None new at the header level — the `pg_wcssize`/`pg_wcsformat` sync contract and the
`mbvalidate` UTF-8-only behavior are tracked against `mbprint.c` in
`knowledge/issues/fe_utils.md`. Cross-linked.
