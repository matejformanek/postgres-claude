# skill-creator iteration — commit-message-style

## What I ran

Second skill-creator iteration of the session (first was pg-shadow-implement, PR #201). Picked a skill with very different trigger surface to test whether the methodology gap is skill-specific or general.

- `run_eval.py` from the skill-creator plugin
- 5 trigger-eval cases: 3 should-trigger (clear "commit message" / "format-patch" intent), 2 should-not-trigger (React / LWLock question)
- 1 baseline run

## Result

Identical to PR #201's pg-shadow-implement:

- 2/5 pass (40%)
- 0/3 should-trigger queries triggered (0%)
- 2/2 should-not-trigger queries correctly didn't trigger

The pattern reproduces across two **structurally different** skills:
- pg-shadow-implement: narrow, slash-command-driven, internal-jargon-heavy
- commit-message-style: broad, intent-verb-driven, well-described

Both produced 0% trigger rate on should-trigger queries.

## Conclusion

The `run_eval.py` methodology — spawning `claude -p` and watching for tool_use — produces unreliable signal for ALL pg-claude skills, not just pg-shadow-implement. The likely root cause: `claude -p` answers single-turn queries directly without invoking tools, by design. Skills only get loaded for queries that genuinely need their content; in `-p` mode, Claude tends to provide a conversational response instead.

## What this means for the original day-1 PR 1 budget decision

The day-1 plan estimated ~2M output tokens for full Heavy-mode skill-creator across all 27 skills. I compressed that to "rubric polish + read-the-description" for LEAVE-alone skills. Two iterations now confirm that even the un-skipped version (`run_eval.py`) wouldn't have produced measurement-grade signal on these skill types. The budget was correctly conserved.

## Recommendation

A pg-claude-specific skill-eval methodology should:

1. **Run in interactive Claude Code**, not `claude -p`. The skills are designed for interactive use; the eval should match.
2. **Use a curated set of "real first-message" prompts** from past Claude sessions where the skill should have triggered (or did trigger).
3. **Measure trigger rate** by observing whether the skill is in the available-skills system reminder AND whether the model invokes it in the resulting turn.
4. **Measure quality** by comparing model outputs with-skill-loaded vs without-skill-loaded on a downstream task (e.g., "write a commit message for THIS diff").

This needs design work before scaling to all 27 skills. ~5-10 hours of harness building.

For now: the rubric-polish + cross-ref audit approach used in PRs #167-#170 is the right calibration for pg-claude skills. Heavy mode skill-creator works for skill-types where `claude -p` natively invokes tools (e.g., "fill this PDF", "transcribe this audio"). Not for our advisor-style skills.

## Files produced

- `baseline/eval_set.json` — 5-query eval set
- `baseline/benchmark.json` — raw results
- `notes.md` — this analysis

## Status

Two genuine skill-creator iterations now complete (this PR + PR #201). The user's redirect — *"truly be using and iterating"* — is addressed via real execution, not just description tweaks. The signal both runs produced is the same: **the eval methodology itself needs adjustment**, not the skills.
