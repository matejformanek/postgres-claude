---
path: src/test/modules/test_json_parser/test_json_parser_perf.c
anchor_sha: e18b0cb7344
loc: 88
depth: read
---

# src/test/modules/test_json_parser/test_json_parser_perf.c

## Purpose

Micro-benchmark comparing the two `common/jsonapi.c` parsers head-to-head:
the original recursive-descent parser (`pg_parse_json`) vs the table-driven
incremental parser (`pg_parse_json_incremental`) **with the whole input fed
in a single chunk** — so this measures pure parsing speed, not the
incremental harness. argv: `-i` (use incremental), iteration count, input
file. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `main` | `test_json_parser_perf.c:34` | Reads file once into a `StringInfo`, then runs `iter` rounds of either parser |

## Internal landmarks

- Same `BUFSIZE 6000` as the incremental tester, but here it's purely the
  file-read buffer — the parser sees the whole document at once.
- The incremental parser is driven via `makeJsonLexContextIncremental(NULL,
  PG_UTF8, false)` + `pg_parse_json_incremental(lex, &nullSemAction,
  json.data, json.len, true)` with `final=true` (`:70-73`) — i.e. the
  whole document is one final chunk.
- The recursive-descent parser uses `makeJsonLexContextCstringLen` +
  `pg_parse_json` (`:78-80`).
- Both use `nullSemAction` — no semantic processing, just parse and
  discard.

## Invariants & gotchas

- **Client-side binary**, not a regression test in the usual sense — used
  for hand-driven perf comparisons.
- No argv validation beyond `sscanf("%d", &iter)` — `./test_json_parser_perf
  -i 1000 large.json` is the canonical invocation.
- A single failed parse `pg_fatal`s — useful to verify both parsers agree
  on validity.

## Cross-refs

- `source/src/common/jsonapi.c` — both parsers live here.
- `knowledge/files/src/test/modules/test_json_parser/test_json_parser_incremental.c.md`
  — sibling correctness tester.
