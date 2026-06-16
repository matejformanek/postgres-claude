# json.c — `json` type I/O and constructors

## Purpose

Implements the SQL-level `json` type. Unlike `jsonb` (which is parsed-to-a-binary-form), `json` is stored as-is text after validation, preserving whitespace and key order. This file holds the type I/O entry points, the validation-only parse, plus the `array_to_json`/`row_to_json`/`to_json`/`json_agg`/`json_object_agg` constructors that build textual JSON via `StringInfo`.

Source: `source/src/backend/utils/adt/json.c` (1883 lines). Companion: `src/common/jsonapi.c` (lexer/parser) and `utils/adt/jsonb.c` (binary jsonb).

## Key functions

- `json_in` / `json_out` / `json_recv` / `json_send` — type I/O. `json_in` validates by running the SAX-style `pg_parse_json` and discards the result; the stored datum is the original cstring as `text`. [verified-by-code json.c:105-160]
- `json_validate` (header-exposed) — used by other call sites to validate without parsing into a tree.
- `array_to_json`, `row_to_json`, `to_json`, `to_json_pretty` — wrappers around `array_to_json_internal` / `composite_to_json` / `datum_to_json` that walk the value recursively. [verified-by-code json.c:629-731]
- `array_to_json_internal` — recursive multi-dim array walker; calls itself per dimension. Calls `check_stack_depth()` at line 185 in `array_dim_to_json`. [verified-by-code json.c:185]
- `json_agg_transfn` / `json_agg_finalfn`, `json_object_agg_transfn` / `json_object_agg_finalfn` — aggregate state via `StringInfo` accumulator. [verified-by-code json.c:830-1300]
- `json_build_object`, `json_build_array` — variadic builders; type-dispatch via `add_json` → `datum_to_json_internal`.
- `escape_json` — emits an RFC 8259 string literal with `\uXXXX` for control chars. Delegated to `src/common/jsonapi.c` `escape_json` family.

## Phase D notes

- **Stack depth on construction**: the recursion through nested arrays/composites in `composite_to_json` and `array_to_json_internal` is bounded by `check_stack_depth()`. This is the backend pairing for the A5 finding that `src/common/jsonapi.c` parsing uses the same gate.  [verified-by-code json.c:185]
- **Constructor non-validation surprise**: `array_to_json`, `row_to_json`, `to_json` always emit syntactically valid JSON because they go through `escape_json` for strings and `datum_to_json` per-type. There is no path that copies raw caller text into the buffer un-escaped. [verified-by-code]
- **`json_in` accepts any valid JSON text** including duplicates keys, NUL bytes (rejected by jsonapi for security), and trailing whitespace; preservation is by design.

## Potential issues

- `[ISSUE-dos: duplicate-key explosion — json_object_agg builds a StringInfo without de-duplicating, so a producer pushing many copies of the same key is O(n) in memory (maybe)]` Documented behavior; not actionable but worth noting for ingestion pipelines.
- `[ISSUE-undocumented-invariant: json_in returns the un-normalised input bytes; if a caller mutates the input cstring after json_in, the stored Datum changes (maybe)]` Standard varlena rule but easy to forget.
- `[ISSUE-correctness: composite_to_json relies on the OUT type's typoutput/typsend; a buggy user-defined output function can emit invalid JSON text and corrupt the surrounding StringInfo (maybe)]` Mitigated by `escape_json` for strings, but numeric/composite output bypasses escape.

Confidence: most claims `[verified-by-code]`; DoS surface `[inferred]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
