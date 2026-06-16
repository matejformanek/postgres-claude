# jsonfuncs.c — JSON/JSONB manipulation functions

## Purpose

The catch-all for SQL-callable JSON/JSONB functions: keyset/value extraction, path lookup, populate/`jsonb_to_record`, `jsonb_set`/`jsonb_insert`/`jsonb_delete`, `json_strip_nulls`, plus the `json_each`, `json_object_keys`, `json_array_elements`, `jsonb_each_text` family of SRFs. Almost every public json/jsonb function except basic I/O lives here.

Source: `source/src/backend/utils/adt/jsonfuncs.c` (6170 lines — largest file in the batch).

## Indexed surface (high-yield entries)

| Function | Line | Notes |
|---|---|---|
| `jsonb_object_keys` | 571 | SRF |
| `json_object_keys` | 735 | SRF, parses JSON text into SAX events |
| `json_object_field` / `_text` | 849, 887 | path-of-1 |
| `jsonb_object_field` / `_text` | 865, 903 | path-of-1 |
| `json_array_element` / `_text` | 925, 968 | path-of-1 |
| `jsonb_array_element` / `_text` | 940, 983 | path-of-1 |
| `json_extract_path` / `_text` | 1012, 1018 | variadic; calls `get_path_all` |
| `populate_array_dim_jsonb` | 2818 | recursive multi-dim ; `check_stack_depth` at 2835 |
| `populate_record_field` | 3404 | recursive; `check_stack_depth` at 3419 |
| `jsonb_set` / `jsonb_insert` / `jsonb_delete` | -- | rebuild jsonb via `setPath` |
| `iterate_jsonb_values` | 5183 area | recursive; `check_stack_depth` at 5183 |
| `transform_jsonb_string_values` | 6085 area | recursive; `check_stack_depth` at 6085 |

## Key recursion gates

`check_stack_depth()` is called at lines 2835, 3419, 5183, 6085. These are the ones found by ripgrep. All paths that recurse on jsonb structure either iterate (via `JsonbIterator`) or check stack depth. [verified-by-code]

## Phase D notes

- **Stack-depth discipline holds.** Every recursive descent into jsonb structure is bounded. No path was found that recursed without a guard. [verified-by-code]
- **`populate_record_field` is the polymorphic-record path** — used by `jsonb_to_record` and friends. It type-coerces via the destination tupdesc and ultimately invokes typinput functions, which themselves may ereport(ERROR). This is the trust-boundary for malformed-input-from-jsonb attacks. [inferred]
- **`jsonb_set`/`_insert` rebuild via `setPath`**, which is iterative and uses temporary StringInfo via the binary jsonb format. No COW; each call returns a new datum.
- **`jsonb_path_query_first` / `_array` (in jsonpath_exec.c, not here) consult `check_stack_depth` indirectly via the jsonpath engine. This file's bridge into jsonpath is via thin wrappers around `executeJsonPath`. [inferred]
- **Populate-from-jsonb honors strict-vs-lax** for missing fields via `json_populate_type` (sets default vs NULL). Documented in comments at line 3380-3410.

## Potential issues

- `[ISSUE-dos: a many-key jsonb fed to populate_record builds an O(n) field-lookup hash; populate_record_worker caches the hash per call site, so amortized cost is low (low)]`.
- `[ISSUE-correctness: jsonb_set with create_missing=true and an integer path key on an object inserts a stringified integer as the key. Standard PG behavior, but a known footgun (low; documented)]`.
- `[ISSUE-undocumented-invariant: populate_record passes raw jsonb scalar bytes to the destination type's input function; a type whose input function has different semantics from the JSON representation can silently round-trip wrong values (maybe)]` E.g. numeric overflow into int4.
- `[ISSUE-dos: json_each / json_object_keys on a json (text) column reparses the text every call; no caching (low — design tradeoff)]`.

Confidence: file is enormous, so claims are indexed-surface level. Cited line numbers are `[verified-by-code]`; behaviors are `[inferred]` from comments and standard PG patterns.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
