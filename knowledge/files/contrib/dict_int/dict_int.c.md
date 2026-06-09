# contrib/dict_int/dict_int.c

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role

Implements `dict_int` — a text-search dictionary that truncates
integer lexemes to a maximum length (or rejects them). Used to tame
GIN/GiST tsvector indexes on text containing many distinct ID
numbers. No rules file. [verified-by-code]
`source/contrib/dict_int/dict_int.c:34-77` (init), `:80-119` (lexize).

## Public API (SQL-callable)

- `dintdict_init(internal) → internal` — dictionary template init
  hook (`:34-77`).
- `dintdict_lexize(internal, internal, int4, internal) → internal` —
  lexize hook (`:80-119`).

Options (`:50-73`):
- `maxlen` — int, default 6. Must be `>= 1`. [verified-by-code]
- `rejectlong` — bool, default false.
- `absval` — bool, default false (skip leading `+`/`-`).

Unrecognized parameter → `ERRCODE_INVALID_PARAMETER_VALUE`. [verified-by-code]

## Invariants

- `maxlen >= 1` enforced at init (`:54-57`).
- `maxlen` parsed via `atoi(defGetString(defel))` (`:52`) — silently
  accepts garbage like "abc" as 0, then errors at `:54-57`.
  [verified-by-code]
- Returned `TSLexeme` array is always 2-slot, NULL-terminated at
  index 1 (`:86,88`). Result `lexeme` may be NULL (= "reject this
  token") or a non-NULL truncated string. [verified-by-code]

## Notable internals

- The "trim integer" branch (`:108-111`) overwrites byte `maxlen` in
  the palloc'd copy with `\0`. Caller must not have passed
  `maxlen > len` here — and indeed the path is gated by `len >
  d->maxlen` (`:98`). [verified-by-code]
- When `absval` is set and input starts with `+`/`-`, `len--` (`:92`)
  but the original `len` is `PG_GETARG_INT32(2)`; reading `in[0]`
  before the length check assumes `len >= 1`. The tsearch parser
  should not pass zero-length tokens, but a defensive guard would
  be cheap. [ISSUE-robustness-low]
- `txt` is `pnstrdup`'d (`:93,96`), so the result is independent of
  the caller's buffer. [verified-by-code]

## Trust-boundary / Phase-D surface

- No file I/O, no parser, no network. Phase-D surface is trivial.
  Worst case is an unbounded `maxlen` (only constrained `>= 1`):
  a malicious dictionary creator with `maxlen = INT_MAX` would
  produce no truncation, but no allocation grows beyond the input
  token length. [verified-by-code]
- `atoi` for `maxlen` is sloppy: `atoi("999999999999999")` returns
  garbage on overflow, but the check at `:54-57` then accepts the
  garbage as positive. **Adversarial dict definition with `maxlen
  = 1e20` silently becomes `INT_MIN` and fails the `>= 1` check —
  acceptable.** [verified-by-code]

## Cross-refs

- `source/src/backend/tsearch/ts_public.c` — `TSLexeme` definition.
- `source/contrib/dict_xsyn/dict_xsyn.c` — sibling text-search dict.

## Issues

- `[ISSUE-robustness-low: dintdict_lexize reads in[0] before
  validating len >= 1 when absval is set] (low)` —
  `source/contrib/dict_int/dict_int.c:90`
- `[ISSUE-robustness-low: maxlen parsed via atoi() — garbage
  strings become 0 and fall through to the >=1 error, but no
  ERRCODE_INVALID_TEXT_REPRESENTATION distinguishes bad input from
  out-of-range] (very low)` —
  `source/contrib/dict_int/dict_int.c:52-57`
