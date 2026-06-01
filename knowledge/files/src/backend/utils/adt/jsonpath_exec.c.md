# `src/backend/utils/adt/jsonpath_exec.c`

- **File:** `source/src/backend/utils/adt/jsonpath_exec.c` (4816 lines)
- **Header:** `source/src/include/utils/jsonpath.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Executes a binary `JsonPath` against a `jsonb` document. Implements the
SQL/JSON path language semantics (lax vs strict mode, array
unwrapping, filter predicates, item methods, arithmetic, `LIKE_REGEX`,
`.datetime()`, `JSON_TABLE`). Top-of-file comment (`:1-58`) is the
authoritative architectural overview; read it before diving in.

## Top of file (verbatim, abridged)

```
 * jsonpath_exec.c
 *   Routines for SQL/JSON path execution.
 *
 * Jsonpath is executed in the global context stored in JsonPathExecContext,
 * which is passed to almost every function involved into execution. Entry
 * point for jsonpath execution is executeJsonPath() function ...
 *
 * The result of jsonpath query execution is enum JsonPathExecResult and
 * if succeeded sequence of JsonbValue, written to JsonValueList *found ...
 *   - jperOk        -- result sequence is not empty
 *   - jperNotFound  -- result sequence is empty
 *   - jperError     -- error occurred during execution
 *
 * Many of jsonpath operations require automatic unwrapping of arrays in lax
 * mode. ...
 *
 * All boolean expressions (predicates) are evaluated by executeBoolItem()
 * function, which returns tri-state JsonPathBool. When error is occurred
 * during predicate execution, it returns jpbUnknown.
```
(`:1-58` [from-comment])

## Public surface (SQL-facing)

- **Operator helpers / exists / match:**
  `jsonb_path_exists` (`:455`), `jsonb_path_exists_tz` (`:461`),
  `jsonb_path_exists_opr` (`:472`),
  `jsonb_path_match` (`:527`), `jsonb_path_match_tz` (`:533`),
  `jsonb_path_match_opr` (`:544`).
- **Query (SRF / array / first):** `jsonb_path_query` (`:606`),
  `jsonb_path_query_tz` (`:612`), `jsonb_path_query_array` (`:641`),
  `jsonb_path_query_first` (`:679`), with `_tz` variants.
- **C-level API used by SQL/JSON `JSON_EXISTS`, `JSON_QUERY`,
  `JSON_VALUE`:** `JsonPathExists`, `JsonPathQuery`, `JsonPathValue`
  (declared `jsonpath.h:307-313`).
- **JSON_TABLE plumbing:** `JsonbTableRoutine` exported via
  `JsonTableInitOpaque` / `JsonTableSetDocument` / `JsonTableFetchRow` /
  `JsonTableGetValue` / `JsonTableDestroyOpaque` plus
  `JsonTablePlanScanNextRow` / `JsonTablePlanJoinNextRow`
  / `JsonTablePlanNextRow` (`:383-398`).

## Key types (mostly file-private)

- **`JsonPathExecContext`** — per-evaluation state: root document,
  `vars` (variable list), stack for `@` (filter target),
  `useTz`, `strictly` flag (lax/strict), `lastGeneratedObjectId`.
  Threaded through every `execute*`.
- **`JsonValueList`** — append-only list of result `JsonbValue`s.
  When `found == NULL`, executor is in EXISTS-mode and returns on
  first match (`:14-16` top comment [from-comment]).
- **`JsonPathBool`** = `{jpbFalse, jpbTrue, jpbUnknown}` — SQL/JSON
  three-valued predicate logic; jpbUnknown both on `null` operand
  and on caught arithmetic error.
- **`JsonPathExecResult`** = `{jperOk, jperNotFound, jperError}`.
- **`JsonBaseObjectInfo`** — tracks current `@@` outer object for
  filter base-relative paths.

## Key invariants and execution model

- **Recursive sequence-of-values model.** Every path item is fed one
  input `JsonbValue` and may emit zero, one, or many values. Items
  pass these to the next item one at a time; `JsonValueListAppend`
  is only called when the chain ends (`:25-30` [from-comment]).
- **Lax mode auto-unwraps arrays.** The `unwrap` flag in
  `executeItemOptUnwrapTarget` re-invokes the item per array element
  with `unwrap=false` to prevent double unwrap (`:33-38`
  [from-comment]).
- **Predicates only inside filters per spec; PG allows top-level.**
  Used to implement `@@` operator semantics (`:42-45`
  [from-comment]).
- **Arithmetic is top-down.** Binary ops first execute both operands
  to ensure each is a numeric singleton list, then compute
  (`:46-50` [from-comment]).
- **`.datetime()` requires a timezone-aware variant** when the format
  string can produce TZ output; `checkTimezoneIsUsedForCast`
  (`:380`) raises `cannot_cast_jsonb_value` when called via the
  non-`_tz` SQL entry point.

## Functions of note

- **`executeJsonPath`** (`:285`) — entry. Pulls `JsonPathItem` from
  the binary form via `jspInit`, sets up `JsonPathExecContext`, calls
  `executeItem` (`:290`).
- **`executeItem`** / **`executeItemOptUnwrapTarget`** / **`…ResultNoThrow`**
  (`:290, 292, 303`) — the three-layer dispatch. The "NoThrow"
  variant catches errors and converts them to `jperError` instead of
  raising, used inside predicates to satisfy SQL/JSON's "errors are
  Unknown" rule.
- **`executeAnyItem`** (`:309`) — recursive descent for `.**`
  (jpiAny), respecting `anybounds.first/last` depth window.
- **`executeBoolItem`** / **`executePredicate`** (`:305, 313`) — drive
  comparisons and `&&`/`||`/`!` with three-valued logic.
- **`executeLikeRegex`** (`:325`) — uses PG's internal regex engine
  (regex/regex.h) with flags from `jsp_like_regex` payload; caches
  the compiled regex on the `JsonPathItem` between rows.
- **`executeDateTimeMethod`** (`:330`) — `.datetime()` /
  `.date()` / `.time()` / `.timestamp()` and `_tz` variants;
  dispatches into `date_in` / `timestamp_in` / `timestamptz_in`.
- **`getJsonPathVariable`** (`:346`) — resolves `$varname` against
  the executor's `vars` list (`JsonPathVariable` records,
  `jsonpath.h:295`).
- **`JsonTable*`** callbacks (`:383-398`) — implement the
  `TableFuncRoutine` contract for SQL/JSON `JSON_TABLE`, including
  nested plans for `NESTED PATH` clauses and outer/cross-join
  semantics between sibling nested plans.

## Cross-references

- `source/src/backend/utils/adt/jsonpath.c` — binary tree walkers
  (`jspGet*`).
- `source/src/backend/utils/adt/jsonb_util.c` — `JsonbIteratorNext`
  drives input descent.
- `source/src/backend/executor/nodeTableFuncscan.c` — runs
  `JsonbTableRoutine` for `JSON_TABLE`.
- `source/src/backend/parser/parse_jsontable.c` — translates SQL
  `JSON_TABLE(...)` to a `TableFunc` node.

## Open questions

- Compiled-regex cache lifetime: stored where exactly across rows
  within one `executeJsonPath` invocation? `[unverified]`
- `JsonValueList` is a singly-linked list — does it ever swap to
  an array representation for large result sets? `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 0
- `[from-comment]` × 5
- `[unverified]` × 2
