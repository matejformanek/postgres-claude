# `src/backend/utils/adt/tsquery.c`

## Purpose

Text/binary I/O for `tsquery`. Implements a Pratt-style precedence
parser over the operators `!` (NOT, prio 4), `<N>` / `<->` (PHRASE,
prio 3), `&` (AND, prio 2), `|` (OR, prio 1). Output representation
is a polish-notation array of `QueryItem` (`QI_VAL` operands and
`QI_OPR` operators). Lexeme text is appended after the QueryItem
array. The lexeme tokenizer is borrowed from
`tsvector_parser.c::gettoken_tsvector`. 1398 lines.

## Key functions

- `tsearch_op_priority[]` — `tsquery.c:29`. Operator-priority table.
- `get_modifiers` — `:113`. Parses `:ABCDabcd*` suffix into weight
  bitmap and prefix-flag.
- `parse_phrase_operator` — `:164`. Parses `<N>` and `<->`. Uses
  `strtol`; bounds-check at `:551` rejects distance > `MAXENTRYPOS`
  / `MAXSTRPOS`. `[verified-by-code]`
- `gettoken_query_standard` — `:285`. Standard-syntax tokenizer.
- `gettoken_query_websearch` — `:397`. Websearch tokenizer.
- `pushOperator`, `pushValue`, `pushStop` — `:635-725`. Polish-notation
  emitter.
- `makepol` — `:725`. Shunting-yard loop; calls `check_stack_depth`
  at `:729`. `[verified-by-code]`
- `parse_tsquery` — `:783`. Driver; orchestrates the tokenizer +
  shunting-yard + cleanup pipeline.
- `pushval_asis`, `pushval_morph` — operand emission with lexeme
  validation. `MAXSTRLEN` cap at `:556`, `:584`.
- `tsqueryin` — `:951`. SQL entry point.
- `tsqueryout` — `:1145`. Uses `infix()` (`:990`, also recursive with
  `check_stack_depth` at `:994`).
- `tsquerysend` — `:1187`. Binary out.
- `tsqueryrecv` — `:1225`. Binary in. Sanity: `size > MaxAllocSize /
  sizeof(QueryItem)` (`:1240`), per-operand `val_len > MAXSTRLEN`
  (`:1276`), running `datalen > MAXSTRPOS` (`:1279`), weight bitmap
  `> 0xF` (`:1273`), operator type one-of `OP_{NOT,OR,AND,PHRASE}`
  (`:1307`).
- `tsquerytree` — `:1361`. Debug formatter via `infix()`.

## Phase D notes

Recursion is **two-way protected**: `makepol` (parser) and `infix`
(output formatter) both call `check_stack_depth` at the recursive
entry. So deep parens like `(((((a)))))` and deep nested operators
like `a&b&c&...` are bounded by `max_stack_depth` GUC, not by C
stack. `[verified-by-code]`

Binary recv `findoprnd` builds left-pointers and validates
well-formedness side-effectfully — comment "Checks that the tree is
well-formed as a side-effect" (`:1329-1331`). Malformed binary
gives a clean `elog(ERROR)`.

The lexeme-storage block follows the QueryItem array and is built
in a two-pass copy (`:1338-1346`). The pre-loop check `datalen >
MAXSTRPOS` is per-iteration so each operand is bounded but the
total has already been accumulated.

## Potential issues

- [ISSUE-dos: `tsqueryrecv` permits up to `MaxAllocSize /
  sizeof(QueryItem)` ≈ 64M QueryItems per tsquery (`:1240`). Each
  parsed operand triggers a CRC over its lexeme bytes (`:1284-1286`)
  and a `findoprnd` walk. A 1GB tsquery wire payload would consume
  significant CPU before any caller-side validation. (medium)] —
  `tsquery.c:1240`
- [ISSUE-undocumented-invariant: `findoprnd` is described as
  validating well-formedness "as a side-effect" but the validation
  it actually performs is in `findoprnd_recurse` (in tsquery_util.c
  or similar). The phrase "as a side-effect" hides the fact that
  the call is required for safety — easy to elide in a refactor.
  (low)] — `:1329-1331`
- [ISSUE-correctness: `parse_phrase_operator` uses `strtol` and
  silently allows `<0>` distance, which is then accepted by the
  upper validation. PHRASE distance 0 is semantically odd. Worth
  re-checking the upstream behavior. (low, maybe)] — `:200+`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
