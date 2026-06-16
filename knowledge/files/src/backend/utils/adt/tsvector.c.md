# `src/backend/utils/adt/tsvector.c`

## Purpose

Text/binary I/O for `tsvector`: `tsvectorin`, `tsvectorout`,
`tsvectorsend`, `tsvectorrecv`. The text-in path uses
`tsvector_parser.c` to tokenise, then sorts lexemes, dedups with
position merging, and packs into the on-disk varlena layout
(`WordEntry` table followed by lexeme string area). 555 lines.

## Key functions

- `compareWordEntryPos`, `uniquePos` — `:36`, `:52`. Sort positions,
  dedup keeping higher weight on tie. Cap at `MAXNUMPOS-1` (`:70`).
- `compareentry`, `uniqueentry` — `:87`, `:103`. Sort lexemes
  lexicographically, merge duplicate-lexeme position lists via
  `repalloc`.
- `tsvectorin` — `:175`. Parser loop with per-token caps:
  `MAXSTRLEN` per lexeme (`:210`), `MAXSTRPOS` total bytes (`:217`,
  `:271`). Array auto-grows by doubling from 64; tmpbuf from 256.
  Soft-error-capable via `escontext` (`:263`).
- `tsvectorout` — `:314`. Reverse — quote and escape each lexeme,
  append position info.
- `tsvectorsend` — `:408`. Binary wire format: `uint32 nlex`, then per
  lexeme `null-terminated text + uint16 npos + npos × uint16 pos`.
- `tsvectorrecv` — `:447`. Binary in. Sanity checks: `nentries
  < MaxAllocSize / sizeof(WordEntry)` (`:461`), `lex_len > MAXSTRLEN`
  (`:483`), `datalen > MAXSTRPOS` (`:486`), `npos > MAXNUMPOS`
  (`:489`). Sets `needSort = true` if lexemes arrive misordered (the
  wire format permits this).

## Phase D notes

The text input path goes parser → grow-by-doubling → `uniqueentry`
sort/dedup → final pack. The grow-by-doubling on `arr` and `tmpbuf`
is bounded by `MAXSTRPOS` (~1MiB-ish range). All caps are enforced
post-token via `ereturn` — soft errors propagate cleanly.

The binary recv path accepts misordered lexemes and sorts them
(`needSort` flag, `:550`); this means a hostile client can force a
sort over millions of entries (bounded by `MaxAllocSize /
sizeof(WordEntry)` ≈ 16M entries on 32-bit ints) — that's
gigabytes of sort work via `qsort_arg`. Worse than the text path
because the text-input parser stops earlier (per-token caps applied
during parse).

The position-info comparison check at `:540` (`WEP_GETPOS(wepptr[j])
<= WEP_GETPOS(wepptr[j-1])`) requires strictly increasing positions
in the wire format; this guards against duplicates that would
defeat the unique-position invariant.

## Potential issues

- [ISSUE-dos: `tsvectorrecv` allows up to `MaxAllocSize/sizeof(WordEntry)`
  ≈ 16M lexemes per tsvector (`:461`), then sorts them if misordered
  (`:550-552`). A hostile binary client can submit a 1GB tsvector
  forcing multi-GB sort work in a single backend. Text path is
  protected by `MAXSTRPOS` (~1MB) but binary is not similarly tight.
  (medium)] — `tsvector.c:461`
- [ISSUE-correctness: Comment at `:290` says "This should be
  unreachable because of MAXNUMPOS restrictions" with an
  `elog(ERROR)` fallback at `:292`. The check is correct but
  "unreachable" claims are brittle as the parser evolves. (low)]
- [ISSUE-wire-protocol: Binary recv permits `npos = 0` with
  `haspos = 0` correctly, but the `npos > 0` branch immediately
  sets `haspos = 1` (`:504`). If a sender sends `npos = 0` but the
  caller expects `haspos = 1`, downstream code may break. Bounded
  by the recv check at `:504`. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
