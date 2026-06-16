# jsonbsubs.c — Subscripting handler for `jsonb`

## Purpose

Implements PG14+ subscript syntax for `jsonb`: `myjsonb['key']`, `myjsonb[0]`, `myjsonb['a']['b'][2]` for both read and assign. Registered through `pg_type.typsubscript = jsonb_subscript_handler`.

Source: `source/src/backend/utils/adt/jsonbsubs.c` (414 lines).

## Key functions

- `jsonb_subscript_handler` — entry point; returns a `SubscriptRoutines` vtable. [verified-by-code jsonbsubs.c:403]
- `jsonb_subscript_transform` — parse-analysis step; coerces each `SubscriptingRef` index to `text` (jsonbs are dual-natured: integer subscripts coerce to text in parse, then interpret as int at runtime). [verified-by-code jsonbsubs.c:44]
- `jsonb_subscript_check_subscripts` — executor-time check; iterates `args` and validates each subscript datum. [verified-by-code jsonbsubs.c:176]
- `jsonb_subscript_fetch` — read: descends the jsonb tree via `jsonb_get_element`. [verified-by-code jsonbsubs.c:236]
- `jsonb_subscript_assign` — write: builds a fresh jsonb with the modified path via `setPath`. [verified-by-code jsonbsubs.c:262]
- `jsonb_subscript_fetch_old` — read-modify-write helper used by UPDATE …  SET col['x'] = expr. [verified-by-code jsonbsubs.c:324]
- `jsonb_exec_setup` — initializes per-row execution state cached in `ExprState`. [verified-by-code jsonbsubs.c:354]

## Phase D notes

- **Subscript type coercion** is determined at parse time by `jsonb_subscript_transform`; this is what lets `mycol[3]` work even when 3 is an integer literal — coerce to `text` then to int at runtime. Important security boundary: subscript datum never crosses through string-eval.
- **Assignment creates a new jsonb each time** via `setPath`; no in-place mutation of the original Datum. Standard PG immutability.
- **NULL handling**: NULLs in the subscript propagate to a NULL result (read) or no-op (assign). [from-comment]

## Potential issues

- `[ISSUE-dos: a very long subscript chain forces O(n) jsonb copies on assign because setPath rebuilds the whole tree (maybe)]` By design.
- `[ISSUE-undocumented-invariant: integer subscripts on a jsonb object (non-array) silently no-op; lookup by text "0" on an object returns the value for key "0" if it exists, otherwise NULL (verified)]`.

Confidence: `[verified-by-code]` for function map.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
