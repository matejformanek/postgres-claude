# jsonpath_internal.h — internal header for jsonpath scanner+parser

## Purpose

Private definitions shared between `jsonpath_scan.l` (flex) and `jsonpath_gram.y` (bison). Defines the string-accumulator `JsonPathString`, declares the `YY_DECL` reentrant scanner entry point, and forward-declares `jsonpath_yyparse` / `jsonpath_yyerror` for the bison-generated parser.

Source: `source/src/backend/utils/adt/jsonpath_internal.h` (43 lines).

## Contents

- `JsonPathString` — `{ char *val; int len; int total; }`. Used by the scanner to accumulate string literals byte-by-byte while interpreting escape sequences. [verified-by-code jsonpath_internal.h:18-23]
- `yyscan_t` — opaque pointer to the reentrant flex scanner state. [verified-by-code:25]
- `YY_DECL` — overrides the default flex prototype to include a result-out parameter and an `escontext` (for soft-error reporting from a scanner that runs inside a SQL function). [verified-by-code:30-34]
- Forward declarations for `jsonpath_yyparse` and `jsonpath_yyerror`. [verified-by-code:35-41]

## Phase D notes

- **Reentrant scanner with soft-error context** — the `escontext` plumbing means a jsonpath syntax error from a user-supplied text doesn't longjmp out of an expression that's running inside a larger query; it can be reported as a soft error instead. This is the same `Node *escontext` pattern as the rest of the backend. [verified-by-code]
- **No security surface of its own** — pure header.

## Potential issues

None. Pure header file with no logic.

Confidence: `[verified-by-code]`.
