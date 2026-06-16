# `src/include/tsearch/ts_utils.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~282
- **Source:** `source/src/include/tsearch/ts_utils.h`

Shared tsearch helpers: tsvector/tsquery parsing, plain-text → lexeme
parsing, headline framework, TS_execute() interpreter for TSQuery
against arbitrary data via a `TSExecuteCallback`. [verified-by-code]

## API / declarations

- **tsvector parser** (opaque `TSVectorParseState`):
  `init_tsvector_parser(input, flags, escontext)`,
  `gettoken_tsvector`, `reset_tsvector_parser`,
  `close_tsvector_parser`. Flags: `P_TSV_OPR_IS_DELIM`,
  `P_TSV_IS_TSQUERY`, `P_TSV_IS_WEB`. [verified-by-code]
- **tsquery parser** (opaque `TSQueryParserState` + `PushFunction`
  callback): `parse_tsquery(buf, pushval, opaque, flags, escontext)`
  with flags `P_TSQ_PLAIN`, `P_TSQ_WEB`. Helpers for the callback:
  `pushValue`, `pushStop`, `pushOperator`. [verified-by-code]
- **Plain-text → lexemes**: `ParsedWord` (uses union of inline
  `uint16 pos` vs `uint16 *apos`; `apos[0]` holds the array element
  count, and we cap at `MAXNUMPOS=256` entries),
  `ParsedText { words, lenwords, curwords, pos }`,
  `parsetext(cfgId, prs, buf, buflen)`. [verified-by-code]
- **Headline framework**: `hlparsetext`, `generateHeadline`.
- **TS_execute**: `TSTernaryValue { TS_NO, TS_YES, TS_MAYBE }`,
  `ExecPhraseData { npos, allocated, negate, pos, width }`,
  `TSExecuteCallback`, `TS_execute`/`TS_execute_ternary`/
  `TS_execute_locations`, `tsquery_requires_match`. Flags
  `TS_EXEC_SKIP_NOT` (deprecated default — "silly answers") and
  `TS_EXEC_PHRASE_NO_POS`. [verified-by-code] [from-comment]
- **TSQuery utilities**: `clean_NOT`, `cleanup_tsquery_stopwords`,
  the `QTNode` tree (`QTN_NEEDFREE`/`QTN_NOCHANGE`/`QTN_WORDFREE`),
  `QTNSort`/`QTNTernary`/`QTNBinary`/`QTNCopy`/`QTNEq`/
  `QTNodeCompare`/`findsubquery`.
- **TSQuerySign** (`uint64` bloom-style signature), indexed via
  `TSQS_SIGLEN = sizeof(uint64)*BITS_PER_BYTE = 64`. Macros
  `PG_GETARG_TSQUERYSIGN(n)` / `PG_RETURN_TSQUERYSIGN(X)` round-trip
  through Int64 Datum (fmgr). [verified-by-code]
- Strategy numbers: `TSearchStrategyNumber=1`,
  `TSearchWithClassStrategyNumber=2`.
- `ISOPERATOR(x)` macro: `! & | ( ) <`. [verified-by-code]

## Notable invariants / details

- `TSExecuteCallback` ternary contract: must return `TS_MAYBE` (not
  `TS_YES`) if it lacks position data. Returning `TS_YES` without
  filling pos[] when pos was requested breaks phrase matching.
  [from-comment]
- ExecPhraseData.pos[] must be sorted, unique, and contain only
  position bits — callers must use `WEP_GETPOS()`. This lets the
  callback hand back a direct pointer into the tsvector's
  `WordEntryPos` array. [from-comment]
- `TS_EXEC_SKIP_NOT` is "deprecated because it tends to give silly
  answers" but kept for backward-compatible callers. [from-comment]

## Potential issues

- `clean_NOT` returns `QueryItem *` and mutates `*len`; callers must
  notice that the returned pointer may equal the input or be NULL on
  full-elimination. The header does not say which. [ISSUE-doc-drift:
  clean_NOT return semantics under-documented (nit)]
- `ParsedWord.alen` documents `apos[0]` as the count "excluding
  apos[0]" — easy to off-by-one. [ISSUE-undocumented-invariant:
  apos[0] vs apos[1..] convention (maybe)]
- `MAXNUMPOS=256` is a tsearch-wide cap on positions per lexeme; the
  number is fixed at compile time and not exposed as a GUC. [ISSUE-question:
  whether MAXNUMPOS should be tunable for very long documents (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-tsearch`](../../../../issues/include-tsearch.md)
<!-- issues:auto:end -->
