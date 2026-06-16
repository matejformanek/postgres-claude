# gucs-config — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/gucs-config/SKILL.md`.

## Score progression

| Run | with_skill | baseline | delta (skill - baseline) |
|---|---|---|---|
| Iteration 1 | 30 / 30 = 1.000 | 18 / 30 = 0.600 | +0.400 |
| Iteration 2 | 30 / 30 = 1.000 | 19 / 30 = 0.633 | +0.367 |

The skill saturates the assertion bar at 100% both runs. The absolute
lift over baseline sits in the +0.37–0.40 range; baseline variance
accounts for the small +1 baseline shift between iterations (in iter-2,
"AFTER all DefineCustom* calls" landed where iter-1 missed it).

## What changed between iter-1 and iter-2

Seven edits from `iteration-1/proposed-edits.md` were applied to
SKILL.md (none dropped, two merged into a single diff block):

1. **Edit #1** — `MarkGUCPrefixReserved` cite tightened from
   `guc.c:5178-5228` to `guc.c:5185-5228` (function definition starts
   at line 5185; previous cite straddled the header comment).
2. **Edit #2 + #4** (merged) — `guc_malloc` README cite tightened from
   `README:51-60` to `README:50-62`; `guc_realloc` added to the §5
   list alongside `guc_malloc` / `guc_strdup` / `guc_free`; inline cite
   `source/src/include/utils/guc.h:473-476` for all four allocator
   declarations.
3. **Edit #3** — `SplitIdentifierString` / `SplitGUCList` added as the
   canonical parsers for `GUC_LIST_INPUT` GUCs inside the check_hook,
   cited to `source/src/include/utils/varlena.h:33-37`. This was the
   one real operational omission in the previous draft.
4. **Edit #5** — One-line gloss on `GUC_check_errcode` clarifying that
   it overrides the default rejection SQLSTATE
   (`ERRCODE_INVALID_PARAMETER_VALUE`, 22023).
5. **Edit #6** — Per-type check_hook signature table inserted at the
   top of §6, spelling out the first-argument pointer type for bool /
   int / real / string / enum GUCs. Cited to README:25-30.
6. **Edit #7** — Finer-grained README sub-cites added for the
   assign_hook contract (README:78-109) and the show_hook contract
   (README:112-117); the umbrella check_hook cite tightened from
   25-109 to 25-75.

## Source-value verifications performed

Before applying, every cite in `proposed-edits.md` was verified
against `source/`:

- `MarkGUCPrefixReserved` function body at
  `source/src/backend/utils/misc/guc.c:5185-5228`. Header comment at
  5178-5183 (which the previous cite straddled).
- `guc_malloc` / `guc_realloc` / `guc_strdup` / `guc_free` declarations
  at `source/src/include/utils/guc.h:473-476`. Each on its own line,
  exact order: malloc (473), realloc (474), strdup (475), free (476).
- README's guc_malloc / extra-pointer rules at
  `source/src/backend/utils/misc/README:50-62` (string-replacement at
  50-55; extra-pointer at 57-62).
- README's check_hook signature enumeration at
  `source/src/backend/utils/misc/README:25-30`.
- README's assign_hook contract at
  `source/src/backend/utils/misc/README:78-109`.
- README's show_hook contract at
  `source/src/backend/utils/misc/README:112-117`.
- `SplitIdentifierString` / `SplitGUCList` declarations at
  `source/src/include/utils/varlena.h:33-37`.
- GucContext enum at `source/src/include/utils/guc.h:71-80` (already
  correct in SKILL.md, no change).
- DefineCustom*Variable signatures at
  `source/src/include/utils/guc.h:358-416` (already correct, no
  change).
- Flag bit values at `source/src/include/utils/guc.h:214-242` (already
  correct, no change; spot-checked `GUC_LIST_INPUT=0x000001`,
  `GUC_LIST_QUOTE=0x000002`).
- worker_spi `_PG_init` skeleton at
  `source/src/test/modules/worker_spi/worker_spi.c:303-360` (already
  correct, no change).
- `EmitWarningsOnPlaceholders` alias at
  `source/src/include/utils/guc.h:421` (already correct, no change).

All values used in the edits match source exactly. No off-by-one
errors caught this round (one cite-range tightening was for precision,
not correctness — the original 5178-5228 was technically honest about
the surrounding region, just less direct than 5185-5228).

## Verdict

`gucs-config` is **ready**. The skill provides a solid absolute lift
over baseline (~+0.37) on a rubric the baseline already partially
knows (PG admin GUC docs cover the high-level shape); it consistently
lifts on the operational nuances (MarkGUCPrefixReserved two-roles,
`guc_malloc` storage rule, `GUC_check_err*` family vs `ereport`,
`GUC_LIST_QUOTE` for identifier lists). Iter-2 with-skill held 100%
with the new content active in the answers, confirming no regression
from the seven edits.

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2/.claude/skills/gucs-config/SKILL.md`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2/skill-evals/gucs-config/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2/skill-evals/gucs-config/iteration-2/`

Verified diff:
```
.claude/skills/gucs-config/SKILL.md | 39 ++++++++++++++++++++++++++++++++-----
 1 file changed, 34 insertions(+), 5 deletions(-)
```
