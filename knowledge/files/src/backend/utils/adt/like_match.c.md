# `src/backend/utils/adt/like_match.c`

- **File:** `source/src/backend/utils/adt/like_match.c` (509 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

The LIKE / ILIKE pattern-matcher proper. **`#include`d four times by
`like.c`** to instantiate variants for (1) single-byte encodings,
(2) UTF-8, (3) other multi-byte encodings, (4) case-insensitive
single-byte. (`like_match.c:5-10` [from-comment])

Caller defines `NextChar`, `MatchText`, optionally `do_like_escape`,
and `MATCH_LOWER` (case 4) before including.

## Return values

- `LIKE_TRUE` — pattern matches.
- `LIKE_FALSE` — pattern doesn't match, but a longer text suffix
  might.
- `LIKE_ABORT` — pattern doesn't match AND text is too short for any
  suffix to succeed; the caller's outer `%` scan can stop early.
  (`:60-70` [from-comment])

## Matching strategy

- Wildcards: `%` (zero-or-more chars), `_` (exactly one char), `\`
  (escape — next byte is literal, even `%`/`_`).
- Linear scan over pattern; on `%`, **recursive call** to try matching
  the rest of the pattern at each candidate text position
  (`:115-197` [from-comment]).
- Wildcard collapse: a run of `%`s and `_`s is folded to one `%` plus
  the count of `_`s (`:124-130` [from-comment]) — prevents
  `MatchText("a", "%%%%%%%%%%b")`-style exponential recursion on long
  wildcard runs.
- `check_stack_depth()` at function entry (`:91`) catches pathological
  recursion depth.
- First-char fast-path: when looking for a `%`-anchor position, the
  inner scan only recurses when text[i] equals the pattern's first
  non-wildcard char (`:179-187`) — except for non-deterministic
  collations where bytes-equal is unsound (`:181`).

## Non-deterministic collation path (`:205-373`)

For ICU non-deterministic collations (`locale->deterministic == false`),
substring matching is done at the substring level using `pg_strncoll`
(`:282, :305`), not byte-by-byte. The pattern is partitioned by
wildcards; each non-wildcard substring is collation-compared against
candidate text substrings of varying lengths. This is per the SQL
standard.

This path can be **substantially slower** than the deterministic path —
each candidate position triggers a `pg_strncoll` call (via ICU
`ucol_strcollUTF8`).

## Phase D notes

- **Recursion depth** is the obvious DoS vector. Protected by:
  - `check_stack_depth()` at entry (`:91`).
  - Wildcard collapse (`:124-148`) — `%%%%%b` is collapsed to `%b`
    before recursion, so `MatchText` doesn't recurse on each `%`.
  - The first-char fast-path skips most candidate positions cheaply.
- **Backtracking complexity**: for a pattern like `%a%a%a%a%b` against
  text `aaaa...aaa`, the recursion would naively be exponential. The
  algorithm here is **not** linear; it's bounded by the recursion depth
  check and by `CHECK_FOR_INTERRUPTS` (`:303`) inside the
  non-deterministic loop.
- **No explicit pattern-length cap.** A multi-MB pattern is allowed; the
  cost is bounded by the recursion-depth check + CFI.
- The escape-at-end error (`:108-111`, `:170-173`, `:240-242`) is the
  only input-validation `ereport` — no fall-through.

## Potential issues

- [ISSUE-dos: deeply nested patterns like
  `"%a%a%a%...%b"` against a long text could provoke quadratic-to-cubic
  backtracking; only `check_stack_depth` + CFI bound it. Worst-case
  complexity not documented in the file. (maybe)]
- [ISSUE-dos: non-deterministic collation path does `pg_strncoll` in an
  inner loop (`:299-372`) — each candidate substring requires an ICU
  collation call. ILIKE on multi-MB text with a non-trivial pattern in
  non-deterministic collation could be quite slow; mitigated by CFI but
  not by an explicit bound. (maybe)]
- [ISSUE-undocumented-invariant: case-insensitive matching uses
  `pg_ascii_tolower` (`:78`) — only fully ASCII-correct. For non-ASCII
  case folding in ILIKE, the input must be casefolded **before** entry
  here. (from-comment, `:74-76`)]

## Cross-references

- `source/src/backend/utils/adt/like.c` — the four `#include` sites
  and the SQL bindings.
- `source/src/backend/utils/adt/like_support.c` — planner support for
  LIKE-on-index.
- `source/src/include/utils/pg_locale.h` — `pg_strncoll`, the
  collation-aware substring comparator.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 5
- `[from-comment]` × 6
