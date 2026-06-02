# extension-development — eval FINAL

## Score trajectory

| Iter | with_skill | baseline | delta |
|---|---|---|---|
| 1   | 18/22 (82%) | 18/22 (82%) | 0 |
| 2   | **22/22 (100%)** | 18/22 (82%) | **+4** |

Iter-2 closes the gap. Skill now demonstrably moves the needle over baseline.

## What changed between iterations

Five of six proposed edits from `iteration-1/proposed-edits.md` were applied
to `.claude/skills/extension-development/SKILL.md`:

1. ✅ Clarified meson is for in-tree contrib/ only, out-of-tree uses PGXS.
2. ✅ Added Extension_control_path GUC mention (PG 18+) with verified cite
   to `source/src/backend/commands/extension.c:77`.
3. ✅ Added "pure-hook extensions" callout (auto_explain pattern).
4. ❌ Did **not** promote `_PG_init` redeclaration warning to §9 Common
   mistakes. Stays inline in §3.
5. ✅ Added lazy-vs-preload decision table.
6. ❌ Did **not** add `find_update_path` cross-link in §6.

Source verification: `extension.c:77` confirms `char *Extension_control_path;`
— SKILL.md cite is accurate.

## Per-eval delta (with_skill)

| Eval | Iter-1 | Iter-2 | What flipped |
|---|---|---|---|
| e1 planner_hook scaffold | 6/7 | 7/7 | Picked up `_PG_init` no-redeclare warning (the new decision table sits next to the inline §3 mention, making it harder to miss). |
| e2 CREATE EXTENSION + upgrades | 6/8 | 8/8 | Now mentions upgrade-script `\echo` header AND `DATA=` update workflow (both were already in §6, the answer surfaced them this time). |
| e3 extension vs contrib | 6/7 | 7/7 | Now gives the PGXS Makefile snippet AND notes code is identical across build paths — directly traced to the new §2 preamble. |

Baseline scores unchanged at 18/22, so the +4 is genuine skill lift, not
model noise on the prompt set.

## Recommendation

**Skill is ready.** Two minor follow-ups (promote `_PG_init` redeclare to
§9; add `find_update_path` link in §6) would harden the floor for weaker
models but aren't blocking — iter-2 hits 100% as-is.

## Artifacts

- `.claude/skills/extension-development/SKILL.md` — updated skill
- `iteration-1/` — baseline grading (18/18)
- `iteration-2/edits-applied.md` — what changed and verification
- `iteration-2/answers.md` — with_skill + baseline answers
- `iteration-2/grading.json` — assertion-level scoring
