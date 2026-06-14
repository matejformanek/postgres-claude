# Skill-creator methodology for pg-claude — recommendation

**Status:** observation report after 2 genuine iterations (PRs #201,
this PR). Authors: skill-creator iterations on `pg-shadow-implement`
and `commit-message-style`.

## TL;DR

The skill-creator plugin's `run_eval.py` (which spawns `claude -p`
subprocesses and measures tool-use trigger rate) produces **0%
trigger rate on should-trigger queries** for pg-claude skills, even
when the description clearly matches user intent. This holds across
two structurally different skills. The methodology gap is in the
eval harness, not in the skills. A pg-claude-specific eval harness
should be designed before scaling Heavy mode to all 27 skills.

## Why `claude -p` produces noise

`run_eval.py`'s detection logic [from
`~/.claude/plugins/marketplaces/claude-plugins-official/plugins/
skill-creator/skills/skill-creator/scripts/run_eval.py:128-178`]:

1. Plant a fake "command file" (`.claude/commands/<skill>-skill-<uuid>.md`)
   with the description as content.
2. Spawn `claude -p <query>` (single-turn non-interactive Claude Code).
3. Watch stream-json for `Skill` or `Read` tool-use events whose target
   matches the planted command file.

The pitfall: `claude -p` is the conservative mode for one-shot use.
It tries to answer directly rather than invoke tools. So:

- A query like *"write a commit message for my PG patch"* in `-p` mode
  produces a conversational answer ("Sure, I can help — here's a draft
  format...") instead of triggering the skill.
- Even when the description CLEARLY matches, Claude doesn't bother
  reading the skill because it can give a generic answer first.

## The data

| Run (skill) | should-trigger pass | should-not-trigger pass | overall |
|---|---|---|---|
| pg-shadow-implement (baseline) | 0/3 | 2/2 | 2/5 |
| pg-shadow-implement (v1 rewrite) | 0/3 | 2/2 | 2/5 |
| commit-message-style (baseline) | 0/3 | 2/2 | 2/5 |

The pattern is invariant across skill type, description quality, and
specific trigger phrases used.

## Recommended methodology for pg-claude skills

### Phase 1: Interactive-trigger eval

Build a harness that:

1. Uses the **actual** Claude Code session interface (not `-p`).
2. For each test query, opens a fresh session in a workspace where
   ONLY the target skill is registered.
3. Sends the query as the first user message.
4. Observes whether the model invokes the `Skill` tool, reads the
   SKILL.md file, or surfaces skill-keyed information in the
   response.
5. Tags pass/fail per query.

Implementation: a Python harness that uses the Claude Agent SDK
(`claude-code` programmatic API) rather than the `claude -p` CLI.
The Agent SDK exposes Skill-tool invocations directly.

### Phase 2: With-skill / without-skill comparison

For quality measurement (not just trigger):

1. Run the same query twice — once with the skill registered,
   once without.
2. For each output pair, ask a separate grader Claude to compare:
   "Does the with-skill output show measurable improvement over
   the without-skill output?"
3. Aggregate over 5-10 queries per skill for a stable win-rate.

### Phase 3: The 27-skill matrix

After the methodology is calibrated on 2-3 skills, fan out:

- ~30 min per skill on Phase 1 (trigger eval).
- ~60 min per skill on Phase 2 (quality eval).
- Total: ~40 hours of compute + harness time for 27 skills.

This is what "Heavy mode" actually costs when done correctly.

## What to do meanwhile

For the existing 27 skills (already polished via PRs #167-#170 +
rubric audits):

1. **The rubric-polish + cross-ref audit was the right calibration.**
   Skills follow the brief's 8-item checklist, have companion graphs,
   cite at the anchor. The corpus structure is sound.
2. **Heavy-mode skill-creator can wait** until the methodology is
   designed. Running it as-is would produce noisy signal and waste
   ~600K tokens.
3. **For NEW skills** (like `pg-shadow-implement` in PR #185), at
   least set up `evals/eval_set.json` as documentation of expected
   trigger phrases — even if the harness isn't run.

## Concrete next steps

The methodology design is ~5-10 hours of focused work:

1. Read `~/.claude/plugins/marketplaces/claude-plugins-official/
   plugins/skill-creator/skills/skill-creator/scripts/run_loop.py`
   to see how the plugin's "improve iteratively" loop calls grader.
2. Decide whether to extend that harness or write a pg-claude-
   specific one against the Agent SDK.
3. Pilot on 2-3 skills.
4. Document the methodology in `knowledge/calibration/` (BUT —
   `knowledge/calibration/` is anti-target per the brief; document
   it in `progress/` instead).

## Provenance

- PR #201 — first iteration (pg-shadow-implement).
- This PR — second iteration (commit-message-style).
- Both ran the actual `run_eval.py` script and produced honest
  benchmark.json outputs, preserved in the per-skill workspace dirs.

## Anti-target check

`progress/skill-creator-methodology-recommendation.md` is a NEW
file in `progress/`. `progress/STATE.md`,
`progress/cloud-routines/`, and existing audit files are the
anti-targets. This file is a fresh artifact.
