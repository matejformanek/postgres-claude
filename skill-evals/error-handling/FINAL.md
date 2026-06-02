# error-handling skill — eval FINAL

## Scoreboard

| Iteration | with_skill | baseline | delta |
|---|---|---|---|
| 1 | 21/21 (100%) | 13/21 (61.9%) | +8 |
| 2 | 21/21 (100%) | 17/21 (81.0%) | +4 |

The with-skill score is saturated at 21/21 across both iterations. Baseline
variance between iterations (13 → 17) reflects re-answer non-determinism,
not a regression — the skill itself only gained content. The remaining
4-point gap is concentrated in the non-obvious mechanics the skill was
written to teach:

- `OpenTransientFile` for fd registration (eval 1).
- `PG_FINALLY` as the default over `PG_CATCH` (eval 2).
- `PG_ENSURE_ERROR_CLEANUP` for FATAL-safe cleanup (eval 2).
- `ERRORDATA_STACK_SIZE` 5-frame recursion limit (eval 2).

These are exactly the items Edits 2, 3, 4 of iteration 1 strengthened in
SKILL.md.

## Iteration 2 edits applied

All 5 proposed edits from `iteration-1/proposed-edits.md` applied verbatim:

1. `%m` format-specifier guidance under rule 2.
2. `OpenTransientFile()` callout in the "ereport(ERROR) does not return"
   section.
3. `PG_FINALLY` promoted from one bullet to a "Prefer" paragraph with
   rationale about auto-rethrow.
4. `ERRORDATA_STACK_SIZE` named with `src/backend/utils/error/elog.c:154`
   cite (verified — that file/line is the actual `#define`).
5. New rule 9: don't clobber `errno` between failing syscall and `ereport`.

No proposed values needed correction. Verification log in
`iteration-2/edits-applied.md`.

## What the skill is buying

The skill's value is **not** in basic message style (lowercase / no period /
quoted identifiers) — baseline gets those reliably from general training.
The lift is in:

- The right *named* helper (`errcode_for_file_access`, `OpenTransientFile`,
  `PG_ENSURE_ERROR_CLEANUP`) rather than general waffle.
- The default choice (`PG_FINALLY` over `PG_CATCH`) when both work.
- The magic constants (`ERRORDATA_STACK_SIZE = 5`) with file:line cites
  so claims are verifiable.
- The subtle traps (`errno` clobbering between syscall and `ereport`).

## Production-readiness

The skill is ready. Pass rate is saturated, the edits all point at
verifiable source locations, and the description triggers on the right
domain (C code under `source/src/backend/` that reports errors) while
explicitly excluding non-PG error idioms (Python try/except, Go errors,
Rust Result, etc.).

No further iteration needed unless real-world use surfaces a new gap.
