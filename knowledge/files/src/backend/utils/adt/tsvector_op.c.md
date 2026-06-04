# `src/backend/utils/adt/tsvector_op.c`

## Purpose

All non-I/O `tsvector` operations: `strip` (drop position info),
`setweight` (uniformly or by lexeme filter), `tsvector_concat`,
`ts_delete`, `ts_filter` (by weight), `to_tsvector`, `tsvector_to_array`,
`array_to_tsvector`, lexeme statistics (`ts_stat`), and the
`@@` match operator for tsvector × tsquery. Plus update-trigger
helpers `tsvector_update_trigger*`. 2896 lines — biggest file in
this batch.

## Key functions

- `tsvector_strip` — `tsvector_op.c:168`. Drop all position info.
- `tsvector_setweight` — `:211`. Apply uniform weight to all
  positions.
- `tsvector_setweight_by_filter` — `:273`. Per-lexeme weight (taking
  a text[] of lexemes).
- `tsvector_delete_by_indices` — `:464`. Internal driver; sorts +
  dedups indices via `qunique`.
- `tsvector_delete_str`, `tsvector_delete_arr` — `:554`, `:577`.
- `tsvector_filter` — `:720`. Keep only lexemes with selected
  weights.
- `tsvector_concat` — `:926`. Position-shifted union of two
  tsvectors. Second-operand positions shifted by max position of
  first; capped at `MAXENTRYPOS - 1` (positions clamp, not error).
- `ts_match_vq`, `ts_match_qv`, `ts_match_tt`, `ts_match_tq` — `@@`
  operator implementations. Polish-notation tree walk via `TS_execute`
  (in `tsearch/ts_utils.c`).
- `ts_stat` / `ts_stat1`/`2` — table statistics over a tsvector
  column.
- `tsvector_update_trigger_byid`, `tsvector_update_trigger_bycolumn`
  — `:2693`, `:2737`. Generic trigger for maintaining a tsvector
  column from text columns.

## Phase D notes

`tsvector_concat` performs position clamping at `MAXENTRYPOS - 1`
instead of erroring on overflow. A user concatenating many large
tsvectors loses position information silently. `[from-comment]`

Output sizing for all operations is bounded by `MAXSTRPOS`
(`palloc` bounded indirectly) — an output >1MB would be rejected by
the post-construction `SET_VARSIZE` check.

`tsvector_update_trigger_*` calls user-named text-search
configurations and column names via `SPI` and `regprocedureoid`
lookups — typical trigger-time catalog access patterns. No
qualified-name handling oddities visible.

`ts_stat` walks SPI rows of a SELECT and aggregates lexeme counts
into an in-memory binary tree (`StatEntry` at `:46`). Tree depth is
unbounded — long-tail distributions yield deep trees. Could OOM on
very large vocabularies, but bounded by per-query memory context.

## Potential issues

- [ISSUE-correctness: `tsvector_concat` silently clamps positions at
  `MAXENTRYPOS - 1` instead of erroring. Concatenating
  document-length tsvectors yields a degenerate result where all
  far positions collapse. Documented as expected behavior but is a
  user footgun. (low)] — `tsvector_op.c:926+`
- [ISSUE-dos: `ts_stat` builds an in-memory binary tree of
  `StatEntry` (`:46-52`) keyed by lexeme. No tree balancing — worst
  case is a skewed sorted-lexeme input that produces a linear
  tree, making `ts_stat` O(N²) on adversarial inputs. (low, maybe)]
- [ISSUE-undocumented-invariant: `tsvector_update_trigger_*`
  identifies the text-search config via `regprocedureoid` lookup of
  a name argument — a renamed config breaks the trigger silently
  on next invocation rather than at ALTER time. Standard PG
  behaviour but worth noting. (low)]
- [ISSUE-dead-code: None obvious in 2896 lines, but a closer pass
  would be useful — file is large and historically organic.]
