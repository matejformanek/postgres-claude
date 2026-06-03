# src/include/common/jsonapi.h

## Purpose

Public surface for the shared JSON parser in `src/common/jsonapi.c`.
Declares the lexer-context type, the token / error / parse-error
enums, the SAX-style semantic-action struct, and the public lex /
parse entry points (both batch and incremental).

## Role in PG

Shared **frontend + backend**. Frontend libpq builds define
`JSONAPI_USE_PQEXPBUFFER` to substitute PQExpBuffer for StringInfo
inside the API struct.

## Key types

- `enum JsonTokenType` — 13 token kinds (`STRING`, `NUMBER`,
  `OBJECT_START/END`, `ARRAY_START/END`, `COMMA`, `COLON`, `TRUE`,
  `FALSE`, `NULL`, `END`, plus `INVALID`).
  (`jsonapi.h:17-32`)
- `enum JsonParseErrorType` — 22 error codes including
  `JSON_SUCCESS`, `JSON_INCOMPLETE` (for the incremental parser),
  `JSON_NESTING_TOO_DEEP`, `JSON_ESCAPING_INVALID`,
  `JSON_OUT_OF_MEMORY`, the six `JSON_UNICODE_*` codes, and
  `JSON_SEM_ACTION_FAILED` (the action already reported it).
  (`jsonapi.h:34-60`)
- `struct JsonLexContext` — input slice + encoding + cursor +
  line tracking + parser-stack handle + unescape StringInfo
  (`strval`) + error StringInfo (`errormsg`) + flag bits.
  Documented as treat-as-read-only by the caller.
  (`jsonapi.h:100-119`)
- Flag bits `JSONLEX_FREE_STRUCT`, `JSONLEX_FREE_STRVAL`,
  `JSONLEX_CTX_OWNS_TOKENS` — drive cleanup and token-ownership
  semantics. (`jsonapi.h:97-99`)
- Action-callback typedefs: `json_struct_action`,
  `json_ofield_action`, `json_aelem_action`, `json_scalar_action`
  — all return `JsonParseErrorType`; returning anything other
  than `JSON_SUCCESS` aborts the parse.
  (`jsonapi.h:127-130`)
- `struct JsonSemAction` — the SAX-style action bag: nine optional
  callbacks plus `semstate`. All-NULL is the pure-validation use
  case. (`jsonapi.h:151-163`)

## Key declarations

- `JsonParseErrorType pg_parse_json(JsonLexContext *,
  const JsonSemAction *)` — batch parse. (`jsonapi.h:174-175`)
- `JsonParseErrorType pg_parse_json_incremental(...)` — feed
  chunks; final chunk is signalled by `is_last=true`. Returns
  `JSON_INCOMPLETE` if more input is needed.
  (`jsonapi.h:177-181`)
- `const JsonSemAction nullSemAction` — the all-NULL action set.
  (`jsonapi.h:184`)
- `json_count_array_elements(lex, *elements)` — secondary parse,
  meant to be called from an `array_start` action.
  (`jsonapi.h:195-196`)
- `makeJsonLexContextCstringLen(...)` and
  `makeJsonLexContextIncremental(...)` — constructors. Both can
  init an existing struct or palloc/malloc one; the
  `need_escapes` flag is the perf knob.
  (`jsonapi.h:218-231`)
- `setJsonLexContextOwnsTokens(lex, bool)` — token-ownership
  policy: needed by libpq to avoid leaking on parse failure.
  Long comment block (`:233-248`) spells out the leak window.
  (`jsonapi.h:249-250`)
- `freeJsonLexContext(lex)` — destructor; flag bits decide what
  is actually freed. (`jsonapi.h:252`)
- `json_lex(lex)` — one-token-at-a-time lexer call.
  (`jsonapi.h:255`)
- `json_errdetail(error, lex)` — human-readable error detail
  string. (`jsonapi.h:258`)
- `IsValidJsonNumber(str, len)` — utility validator for a
  candidate JSON number; does NOT require nul termination.
  (`jsonapi.h:265`)

## Phase D notes

- The `setJsonLexContextOwnsTokens` machinery exists *because*
  libpq must not leak on parse failure — the header comment
  explicitly cites this as a long-lived-client concern.
  Backend memcontext cleanup makes the same machinery less
  critical for backend callers.
- `JsonLexContext.strval` is the unescape buffer; setting
  `need_escapes=false` skips the buffer allocation but means
  field names / scalar string values are NOT available to
  callbacks. Used by `json_count_array_elements` to fast-skip.
- `JSON_INCOMPLETE` is only returned by the incremental parser,
  never by `pg_parse_json` — but the same enum is shared, so
  callers must know which entry they invoked.

## Potential issues

None at the header level.
