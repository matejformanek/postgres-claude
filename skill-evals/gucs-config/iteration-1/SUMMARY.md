# Iteration 1 — summary

## Scores

| Condition | Passed | Total | Rate |
|---|---|---|---|
| with_skill | 30 | 30 | 1.00 |
| baseline   | 18 | 30 | 0.60 |
| Lift       |    |    | +0.40 (+12 assertions) |

## Where with-skill > baseline

The skill consistently lifts on:

- MarkGUCPrefixReserved ordering + two-roles explanation. Baseline knew
  the function name but not that it (a) deletes existing placeholders,
  (b) refuses future ones, or that placeholder leakage later trips
  parallel-worker startup.
- `guc_malloc` / `guc_strdup` / `guc_free` storage rule. Baseline
  vaguely remembered "special malloc" but couldn't name all three
  functions or state the never-`palloc` rule cleanly.
- `GUC_check_errdetail` / `errhint` / `errmsg` / `errcode` family vs.
  `ereport(ERROR)`. Baseline reached for `ereport` in the check_hook by
  default — the skill's explicit "never `ereport(ERROR)` except on OOM"
  rule is high-value.
- `GUC_LIST_QUOTE` for identifier lists. Baseline knew about
  `GUC_LIST_INPUT` but was hazy on the second flag and why both are
  required for `search_path`-style lists.
- `file:line` cites. Every with-skill answer ties claims back to
  `source/`, baseline doesn't.

## Where baseline matched skill

The unaided model already knew:

- `DefineCustomBoolVariable` / the basic _PG_init pattern.
- check_hook returns bool, false = reject.
- assign_hook has no return value → can't fail.
- string GUC uses `char **`.
- PGC_POSTMASTER vs. PGC_USERSET distinction at the high level.
- GUC_LIST_INPUT exists.
- Catalog lookups in a check_hook need IsTransactionState() guard.

## Proposed edits

7 edits proposed in `proposed-edits.md`. All small / regression-hardening
(no big structural changes). Two tighten existing source-cite ranges
(`MarkGUCPrefixReserved` 5178→5185 and the `guc_malloc` README cite
51-60→50-62); one adds `SplitIdentifierString` / `SplitGUCList` (the
one operational omission); one adds `guc_realloc`; one adds a
per-type signature table for check_hook; one adds a one-line gloss on
`GUC_check_errcode`; one adds finer-grained README sub-cites for the
assign + show hooks.

All seven cites pre-verified against `source/` before proposing — no
speculative edits.

## Note on rubric saturation

With-skill scores 100% on iter-1. Per the campaign SUMMARY.md this is
typical (17 of 21 prior skills did the same). The useful iter-2 signal
will be qualitative: did the applied edits hold up to a re-run? do they
introduce any new errors? are any cites still off after editing?
