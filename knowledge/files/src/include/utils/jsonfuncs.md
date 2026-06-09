# utils/jsonfuncs.h — JSON(B) processing higher-level functions

Source: `source/src/include/utils/jsonfuncs.h` (101 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Bridges raw `common/jsonapi.h` parser to backend-specific JSON(B) processing: iterate/transform values, categorize SQL types for JSON output, populate composite types from JSON.

## Public API

- `JsonToIndex` flags: `jtiKey | jtiString | jtiNumeric | jtiBool` (`jsonfuncs.h:25-32`) for selecting what `iterate_json(b)_values` visits.
- `JsonIterateStringValuesAction`/`JsonTransformStringValuesAction` callbacks (`jsonfuncs.h:35, 38`).
- `makeJsonLexContext(lex, text *json, need_escapes)` (`jsonfuncs.h:41`) — build a JsonLexContext for backend use.
- `pg_parse_json_or_errsave(lex, sem, escontext)` (`jsonfuncs.h:44-45`) and the convenience `pg_parse_json_or_ereport(lex, sem)` macro.
- `json_errsave_error` (`jsonfuncs.h:51-52`).
- `json_get_first_token(json, throw_error)` (`jsonfuncs.h:55`).
- `iterate_jsonb_values` / `iterate_json_values` (`jsonfuncs.h:58-61`).
- `transform_jsonb_string_values` / `transform_json_string_values` (`jsonfuncs.h:62-65`).
- `JsonTypeCategory` enum (`jsonfuncs.h:68-82`): NULL / BOOL / NUMERIC / DATE / TIMESTAMP / TIMESTAMPTZ / JSON / JSONB / ARRAY / COMPOSITE / CAST / OTHER.
- `json_categorize_type`, `json_check_mutability`, `datum_to_json`, `datum_to_jsonb`, `jsonb_from_text` (`jsonfuncs.h:84-92`).
- `json_populate_type(json_val, json_type, typid, typmod, cache, mcxt, isnull, omit_quotes, escontext)` (`jsonfuncs.h:94-99`).

## Invariants

- **INV-jsonfuncs-soft-error-preferred** [verified-by-code, `jsonfuncs.h:44-52, 94-99`]: most newer entry points take `Node *escontext` — pass non-NULL on user-input paths to avoid hard ereport.
- **INV-jsonfuncs-cache-pointer** [verified-by-code, `jsonfuncs.h:96`]: `json_populate_type` takes `void **cache` so callers can amortize the type-resolution across many tuples.
- **INV-jsonfuncs-jtiAll-mask** [verified-by-code, `jsonfuncs.h:31`]: `jtiAll = jtiKey | jtiString | jtiNumeric | jtiBool` — does NOT include compound values (objects, arrays); only leaves.

## Trust-boundary / Phase-D surface

- **`makeJsonLexContext(... need_escapes=true ...)`** allocates an unescape buffer (`jsonfuncs.h:41`). Without it, string callbacks see still-escaped bytes — a subtle correctness foot-gun.
- **Recursive parser stack depth** is inherited from `common/jsonapi.h`. Backend callers don't add an extra check; deeply-nested user input flows directly into the parser stack. A8 anchor.
- `JsonTransformStringValuesAction` returns a new text — callers must avoid modifying the input in place (header doesn't forbid it but implementations assume it).

## Cross-refs

- `source/src/common/jsonapi.h` — the recursive parser these wrappers drive.
- `knowledge/files/src/include/utils/json.md` — companion (text-form JSON).
- `source/src/include/utils/jsonb.h` — binary JSONB format.

## Issues

- `[ISSUE-DOC: pg_parse_json_or_ereport macro hides escontext-NULL hard-error (low)]` — at `jsonfuncs.h:47-48`, the convenience macro passes NULL; on user-input paths callers should NEVER use this macro.
