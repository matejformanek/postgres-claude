---
path: src/test/modules/test_json_parser/test_json_parser_incremental.c
anchor_sha: e18b0cb7344
loc: 410
depth: read
---

# src/test/modules/test_json_parser/test_json_parser_incremental.c

## Purpose

Standalone test binary (client-side, `postgres_fe.h`) that drives the
**incremental** (table-driven) flavor of `common/jsonapi.c`. Feeds JSON input
in deliberately tiny chunks (default 60 bytes, configurable; `-r SIZE` runs a
sweep from SIZE down to 1) to stress the lexer's state-resumption code path
where a token straddles a chunk boundary. With `-s` it does full semantic
processing via callbacks that mirror the JSON back; with `-o` it sets
`JSONLEX_CTX_OWNS_TOKENS` for use under leak sanitizers. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `main` | `test_json_parser_incremental.c:86` | argv parser; sets chunk size, semantic mode, ownership; drives `pg_parse_json_incremental` |
| `do_object_start` / `do_object_end` / `do_object_field_start` / `do_object_field_end` / `do_array_start` / `do_array_end` / `do_array_element_start` / `do_array_element_end` / `do_scalar` (static) | declared `:62-70` | Mirror-back semantic-action callbacks emitting JSON to a `StringInfo` |
| `escape_json` (static) | `:59` | Re-escape strings for the mirror output |
| `usage` (static) | `:58` | argv help |

## Internal landmarks

- Default chunk size 60 (`DEFAULT_CHUNK_SIZE`, `:49`) — small enough to
  split most tokens but large enough that the trace stays readable.
- The `JsonSemAction sem` table (`:72-82`) wires all nine callbacks. With
  `-s` it's swapped in; without `-s` the parser is driven against
  `nullSemAction` so only the lexer is exercised.
- `JSONLEX_CTX_OWNS_TOKENS` — when set, the lex context retains ownership
  of token strings and frees them on `freeJsonLexContext`; needed to make
  leak sanitizers happy when invalid JSON aborts mid-parse.
- The `-r SIZE` loop sweeps `chunk_size` from SIZE down to 1 with a null
  byte between iterations — a regression in chunk-boundary handling at
  any size shows up as a diff in the output.

## Invariants & gotchas

- **Client-side binary** — `postgres_fe.h`. Does not link against the
  backend.
- The reason 1-byte chunks must work: incremental JSON parsing is used by
  COPY / FE-BE protocol streaming, and there's no upper bound on TCP
  fragmentation.
- `BUFSIZE 6000` (`:48`) is the file read buffer; the chunking happens
  after the read.

## Cross-refs

- `source/src/common/jsonapi.c` — the parser under test.
- `source/src/include/common/jsonapi.h` — API.
- `knowledge/files/src/test/modules/test_json_parser/test_json_parser_perf.c.md`
  — sibling perf benchmark.
