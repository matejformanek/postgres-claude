---
path: src/bin/psql/crosstabview.c
anchor_sha: 02f699c14163
loc: 738
depth: deep
---

# crosstabview.c

- **Source path:** `source/src/bin/psql/crosstabview.c`
- **Lines:** 738
- **Last verified commit:** `02f699c14163` (re-verified + re-pinned
  2026-06-30 by pg-quality-auditor AUDIT mode after anchor-bump
  `4abf411e2328..02f699c14163`; triggering commit `4df5fe3833a8`
  "Make crosstabview honor boolean/null display settings" added the
  `displayValue()` helper (now `crosstabview.c:439`) and shifted all
  cell-fill / column-resolve cites downward. Prior pin `4b0bf0788b0`.)
- **Companion files:** `crosstabview.h`, `psqlscanslash.h` (`dequote_downcase_identifier`), `fe_utils/print.{h,c}` (`printTable*` API the pivoted result is fed into), `settings.h` (consumes `pset.ctv_args[4]`, `pset.popt`, `pset.queryFout`, `pset.logfile`).

## Purpose

Implementation of the `\crosstabview` meta-command: turn a result set with `(row_key, col_key, data[, sort_key])` tuples into a 2D pivot table and print it via the standard `printTable*` engine. Includes a from-scratch AVL tree to deduplicate row/column keys in O(N log N).

## Public surface

- `PrintResultInCrosstab(const PGresult *res)` (107) — main entry. Reads `pset.ctv_args[0..3]` as the column-spec arguments. Returns true on success. [verified-by-code, crosstabview.c:107-280]

## Algorithm

1. **Validate result.** Status must be `PGRES_TUPLES_OK`; at least 3 columns. [verified-by-code, crosstabview.c:125-133]
2. **Resolve column references.** `pset.ctv_args[0]` → `field_for_rows` (default: column 0). `[1]` → `field_for_columns` (default: 1). `[2]` → `field_for_data` (default: the remaining one, requires exactly 3 columns in the result). `[3]` → `sort_field_for_columns` (optional). Each resolution goes through `indexOfColumn`. [verified-by-code, crosstabview.c:139-203]
3. **First pass.** Walk all tuples; insert each distinct row-key into `piv_rows` AVL tree, each distinct column-key into `piv_columns` AVL tree (along with optional sort_value), via `avlMergeValue`. Bail if `piv_columns.count > CROSSTABVIEW_MAX_COLUMNS` (1600). [verified-by-code, crosstabview.c:214-241]
4. **Flatten.** `avlCollectFields` does an in-order DFS into the pre-allocated `array_columns` / `array_rows`. [verified-by-code, crosstabview.c:251-256, 601-609]
5. **Optional rank sort.** If `sort_field_for_columns >= 0`, `rankSort` reorders by parsed numeric sort-value. [verified-by-code, crosstabview.c:262-263, 612-657]
6. **`printCrosstab`** fills a `printTableContent` and calls `printTable`. [verified-by-code, crosstabview.c:287-430]

## AVL tree

The whole tree implementation lives here (463-609). Notable details:

- Sentinel `tree->end` is a single allocated node where children point to themselves; eliminates NULL checks. [verified-by-code, crosstabview.c:465-468]
- `avlInsertNode` is recursive; depth bounded by O(log N) so safe even at 1600 columns. [verified-by-code, crosstabview.c:554-583]
- Comparator: `pivotFieldCompare` treats NULL > non-NULL and equal to NULL. So NULL keys sort last and dedupe with each other. [verified-by-code, crosstabview.c:719-731]
- `avlFree` recurses children then frees node; takes care to free `tree->end` exactly once at the root call. [verified-by-code, crosstabview.c:473-493]

## printCrosstab cells

Result is a flat `cont.cells[]` of size `(num_columns + 1) * num_rows`. The +1 is for the row-header column. Slot index = `1 + col_number + row_number * (num_columns + 1)`. Empty cells get `""` after the fill pass. Cell strings now route through `displayValue()` so boolean/null display settings are honored. [verified-by-code, crosstabview.c:303, 341-343, 392, 417-420]

If two source rows would map to the same `(row_key, col_key)` cell, **error out**: "query result contains multiple data values for row %s, column %s". [verified-by-code, crosstabview.c:397-409]

## State owned

- The two AVL trees (heap, freed in `error_return` block).
- The two flattened arrays (heap, freed in `error_return`).
- The reverse-map `horiz_map` in `printCrosstab` (heap, freed before return).
- The two-int-per-entry `hmap` in `rankSort` (heap, freed before return).

`printCrosstab` uses `goto error` for the cleanup path; `PrintResultInCrosstab` uses `goto error_return`. All allocations are matched.

## Phase D notes

- **Pointers into `PGresult`.** `pivot_field.name` and `.sort_value` are pointers returned by `PQgetvalue`, which the docs say are valid until `PQclear`. So the AVL tree nodes hold borrowed pointers; the caller MUST keep `res` alive until `PrintResultInCrosstab` returns. This file does — it's all in one function. [verified-by-code, crosstabview.c:29-38, 214-241] [no concern]
- **No quoting of cell contents.** `printTable` handles the formatting; this file just routes bytes from `PQgetvalue` (via `displayValue`) into cell slots. If a query result contains terminal escape sequences, they reach the user's terminal raw. This is by design for psql in general; not specific to crosstabview. [verified-by-code, crosstabview.c:341-343, 409] [no concern]
- **`CROSSTABVIEW_MAX_COLUMNS = 1600` cap.** This stops the AVL-tree size at 1600 distinct column keys. **But** the source tuples list is already in memory (libpq has the whole `PGresult`), so the cap only stops the pivot from going O(N) wider — it doesn't help if the SQL itself returns 100M rows. The cap fires BEFORE allocating cells, so a result with 1600 distinct col-keys and 1M rows would still try to allocate `1601 * 1M` cell pointers = ~12.8GB on 64-bit. Hit it before then and you OOM the client. [verified-by-code, crosstabview.c:230-235, 251-256, 303] [ISSUE-dos: crosstabview cell-allocation is `num_cols * num_rows` pointers; unbounded `num_rows` × bounded `num_cols` still allows OOM (low — psql client-side, by-design loose cap)]
- **`indexOfColumn` modifies its `arg`.** Calls `dequote_downcase_identifier(arg, true, encoding)` which is an in-place mutation. The comment just above flags this. Since `arg` comes from `pset.ctv_args[i]` which is malloc'd by the slash-arg parser, the mutation is fine. [verified-by-code, crosstabview.c:678-684] [no concern]
- **`indexOfColumn` accepts pure-digit args as column numbers.** A query whose actual column name is `"1"` (quoted in the SQL identifier sense) gets misinterpreted unless the user quotes the `\crosstabview` arg. The check `strspn(arg, "0123456789") == strlen(arg)` happens BEFORE dequote, so `"1"` (with the quotes preserved by `OT_SQLIDHACK` or similar) would fall through to name matching. [verified-by-code, crosstabview.c:664-690] [no concern — caller-arg discipline]
- **`rankSort` parses sort_value as integer with `/^-?\d+$/`.** Anything else gets rank 0 (silently). A sort column containing real floats sorts unpredictably. [verified-by-code, crosstabview.c:622-639] [no concern — documented limitation]
- **Pivot duplicate-data error message reveals row/col-key strings.** If the keys are credentials (unlikely but possible from a SELECT password,...), the error message is logged to stderr. Trust boundary: the user already saw the result. [verified-by-code, crosstabview.c:397-401] [no concern]
- **`avlInsertNode` recursion depth.** AVL guarantees O(log N); at 1600 nodes that's ~11 levels. No stack-overflow risk. [verified-by-code, crosstabview.c:554-583] [no concern]

## Cross-references

- `dequote_downcase_identifier`: `psqlscanslash.l` (not in this batch).
- `printTable`/`printTableInit`/`printTableAddHeader`/`printTableCleanup`: `fe_utils/print.c` (not in this batch).
- `column_type_alignment`: `common.c` (not in this batch).

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=15 [no concern]=6 [ISSUE]=1`
