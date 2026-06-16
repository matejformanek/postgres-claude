# `src/backend/utils/adt/tsvector_parser.c`

## Purpose

Token-extractor used by both `tsvector` and `tsquery` text-input
functions. Reusable state machine that walks an input C-string,
honouring quoted-lexeme syntax `'word'`, escape `\`, and (for
tsquery) operator chars `! | & ( )`. Also parses the position-info
suffix `:1A,2B,…`. The `is_web` flag tweaks behaviour for
`websearch_to_tsquery`. Soft-error capable via `escontext`. 383 lines.

## Key functions

- `init_tsvector_parser` — `tsvector_parser.c:57`. Allocates state
  with initial 32-byte word buffer; reads `pg_database_encoding_max_length`.
- `reset_tsvector_parser`, `close_tsvector_parser` — `:81`, `:90`.
- `gettoken_tsvector` — `:176`. The state machine. States:
  `WAITWORD`, `WAITENDWORD`, `WAITNEXTCHAR` (after `\`),
  `WAITENDCMPLX` (inside `'…'`), `WAITPOSINFO`, `INPOSINFO`,
  `WAITPOSDELIM`, `WAITCHARCMPLX`. Returns `true` on token, `false`
  on EOF or soft error. Position array auto-grows by doubling
  starting at 4. Word buffer auto-grows by doubling starting at 32
  via `RESIZEPRSBUF` macro (`:97`).
- `prssyntaxerror` — `:142`. Emits "syntax error in tsvector/tsquery"
  via `errsave` (soft-error aware).

## Phase D notes

This is the **user-input parsing surface** for both `tsvector` and
`tsquery` text input — heavily exposed. Findings:

1. **No lexeme-count cap in the parser itself.** Token count is
   bounded only by the caller; `tsvectorin` (in `tsvector.c`) caps
   at `MAXSTRLEN` per lexeme (`tsvector.c:210`) and total at
   `MAXSTRPOS` (`:217`). The parser itself happily yields unbounded
   tokens. `[verified-by-code]`
2. **Word buffer doubles indefinitely.** `RESIZEPRSBUF` doubles
   `state->len` each grow; for a single super-long lexeme this is
   bounded by available memory and per-token caller checks.
3. **Position info parsing uses `atoi`** (`:329`), which silently
   saturates at INT_MAX. Position is then `LIMITPOS()`-clipped (limit
   from `ts_type.h`). A position of 0 is rejected at `:331`.
4. **Per-lexeme position array** allocated only when positions
   appear; grows by doubling from 4. No cap here either — the cap
   `MAXNUMPOS` is enforced by `uniquePos` in `tsvector.c:70`.

## Potential issues

- [ISSUE-dos: Parser itself does not cap lexeme count or position
  count — all caps are enforced by callers (`tsvectorin`,
  `pushval_asis`). An extension or new caller that forgets the cap
  could OOM the backend. (low, defense-in-depth)] —
  `tsvector_parser.c` has no `MAX*` checks
- [ISSUE-undocumented-invariant: The `is_web` flag changes parsing
  in `gettoken_tsvector` (skips `'` quote handling, treats `"` as
  delimiter) — but only the websearch caller knows the rules. Easy
  to misuse from a new caller. (low)] — `:199`, `:207`, `:239`
- [ISSUE-correctness: `atoi(state->prsbuf)` at `:329` reads from a
  position string that may have leading characters skipped — but
  here the state machine guarantees we're at a digit, so it's safe.
  `[verified-by-code]` (n/a)]
- [ISSUE-stale-todo: Commented-out `state->prsbuf += pg_mblen_cstr`
  at `:298` — looks like a debugging artifact, not a real TODO. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
