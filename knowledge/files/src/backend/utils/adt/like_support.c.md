# `src/backend/utils/adt/like_support.c`

- **File:** `source/src/backend/utils/adt/like_support.c` (1837 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

**Planner support functions** for `LIKE`, `~~`, `~`, `regex`, and
`starts_with` — converts a pattern operator into one or more
index-scannable range conditions on the indexed column, so a B-tree (or
SP-GiST text) index can be exploited. (`like_support.c:1-33`
[from-comment])

Canonical transformation:
```
textfield LIKE 'abc%def'
→ textfield >= 'abc' AND textfield < 'abd'  (and recheck via original op)
```

## Key entry points (SQL-bound)

- `textlike_support` (`:112`), `texticlike_support` (`:120`) — planner
  support hooks for `text ~~ text` and `text ~~* text`.
- `textregexeq_support` (`:128`), `texticregexeq_support` (`:136`) —
  for `text ~ text` and `text ~* text`.
- `text_starts_with_support` (`:144`) — for `starts_with(text, text)`
  and the `^@` operator.

All five funnel into `like_regex_support(rawreq, Pattern_Type_*)`
(`:153`).

## Support-request dispatch

- `SupportRequestSelectivity` (`:158-189`) → `patternsel_common`
  produces a selectivity estimate, shared with operator restrictions
  via `like_selectivity` / `regex_selectivity`.
- `SupportRequestIndexCondition` (`:190-…`) → `match_pattern_prefix`
  generates the derived range quals (`>=`, `<`, `=`) on the
  fixed-prefix portion of the pattern.

## Pattern-prefix analysis

- `pattern_fixed_prefix` (`:87`) — given a `Const` pattern, returns:
  - `Pattern_Prefix_Exact` (no wildcards),
  - `Pattern_Prefix_Partial` (fixed prefix followed by wildcards), or
  - `Pattern_Prefix_None` (leading `%`/`.`/character class etc.).
- `prefix_selectivity` (`:92`) — given the fixed prefix, estimate
  fraction of column matching.
- `make_greater_string` (`:102`) — increments the last char of the
  prefix to build the upper-bound constant. The collation must agree
  with the index's `indexcollation`; for nondeterministic collations
  this transformation is skipped (the byte-`>=` / byte-`<` quals would
  not correspond to collation-`<`).

## Phase D notes

- **No untrusted I/O.** This is pure planner code; inputs are already-
  parsed `Const` patterns from the rewriter. No `errmsg` on user input.
- **Collation correctness**: the derived range quals are only sound if
  the index collation is `C`-like or matches the operator's collation
  in a deterministic way (`match_pattern_prefix` filters on this). If
  this guard were wrong, the rewriter could miss matching rows — a
  correctness bug, not a security one.
- **Selectivity estimates** are approximate; they govern plan choice
  but not result correctness.

## Potential issues

- [ISSUE-correctness: `make_greater_string` increments the last char of
  a prefix; for multi-byte encodings the increment logic is delicate.
  Documented to handle UTF-8 correctly, but ICU non-deterministic
  collations are bypassed via `pattern_fixed_prefix` returning None.
  Worth periodic verification against new ICU rules. (maybe)]
- [ISSUE-undocumented-invariant: `patternsel_common(req->join)` punts
  with `DEFAULT_MATCH_SEL` (`:173`) — bad selectivity estimates for
  pattern joins. Documented as a known TODO at `:170-172`. (low)]

## Cross-references

- `source/src/backend/utils/adt/like.c` — runtime LIKE evaluator.
- `source/src/backend/utils/adt/like_match.c` — match algorithm.
- `source/src/backend/utils/adt/selfuncs.c` — pattern selectivity
  helpers shared here.
- `source/src/include/nodes/supportnodes.h` — `SupportRequestSelectivity`,
  `SupportRequestIndexCondition` definitions.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 3
