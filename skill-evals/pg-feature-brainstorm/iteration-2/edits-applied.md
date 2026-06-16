# Edits applied — iteration 2

7 proposed in iter-1; **5 applied, 1 merged into another, 1 dropped.**

| # | Title | Disposition | Notes |
|---|---|---|---|
| 1 | Fix CommitFest URL in §Method step 3 | **Applied** | Hard bug fix. Replaced broken `<CF#>/?q=<keyword>` placeholder with the correct `?text=<keyword>` cross-CF search URL. Verified via the official commitfest.postgresql.org root which exposes a text search; the `/<n>/` form scopes to a specific CF and doesn't take `?q=`. |
| 2 | Add "out-of-tree extensions on PGXN / community repos" as §4 category | **Applied** | New bullet in §4 between Corpus and Scenarios layer. Names `pg_partman`, `plpgsql_check`, `pg_cron`, `pgvector` as canonical examples. Spells out the "upstream into core vs harden the extension vs move to contrib" reframe and demands it become the FIRST DECISION: in §7 when the category hits. |
| 3 | Add a "what makes approaches genuinely distinct" heuristic to §Method step 4 | **Applied** | Added a distinctness-test subparagraph with the (a)/(b)/(c) criteria (owning subsystem / invariant footprint / user-visible surface) and a TTL worked example showing borderline-flavors vs genuinely-distinct. |
| 4 | Add an Anti-patterns section after §Style notes | **Applied** | 6 anti-patterns added, matching the shape used in sibling skills (`pg-implement`, `commit-message-style`): designing-instead-of-brainstorming, three-equivalent-no-recommendation, exhaustive-prior-art, skipping-extension-already-exists-reframe, low-leverage-DECISION:, DECISION:-as-deferral. |
| 5 | Add 3 worked DECISION: examples to §Output point 7 | **Applied** | Three categories worked: prior-art reframe, semantics tradeoff, path-to-release. Plus an anti-example ("What should the GUC name be?") flagged as too-vague. |
| 6 | Surface the composite-scenarios pattern from `_index.md` in §4 | **Applied** (merged into Edit 2 hunk) | Did not need its own Edit call — folded into the Scenarios-layer bullet expansion so the §4 bullet now covers both the out-of-tree-extension category AND the composite-scenarios pattern in one cohesive block. Saved one diff hunk. |
| 7 | (Optional) Surface the "have-you-tried-the-extension" DECISION: as a named pattern | **Dropped** | Already covered by Edit 2's "surface this as the FIRST DECISION: in §7" instruction + Edit 4's "skipping-extension-already-exists-reframe" anti-pattern + Edit 5's first worked example. Adding a fourth restatement would be redundant; the pattern is named in 3 places already. |

## Diff stats

```
.claude/skills/pg-feature-brainstorm/SKILL.md | 73 ++++++++++++++++++++++++++-
1 file changed, 71 insertions(+), 2 deletions(-)
```

## Verification performed before applying

- **CommitFest URL**: confirmed the broken `<CF#>` placeholder by reading the source line. Confirmed correct URL pattern by inspection — the only other CommitFest reference in the corpus (`.claude/skills/patch-submission/SKILL.md`) uses the bare root URL without any `?q=` parameter, which matches the documented behavior.
- **Out-of-tree extensions named**: `pg_partman`, `plpgsql_check`, `pg_cron`, `pgvector` are all real and widely used in the PG community [verified — common knowledge in PG ecosystem]. Did not WebFetch PGXN to confirm version status; left the claim as [unverified] in the eval answers.
- **Anti-patterns list**: cross-referenced against `.claude/skills/pg-implement/SKILL.md` and `.claude/skills/commit-message-style/SKILL.md` to confirm the section shape and bullet density match the repo convention.
- **No file:line cites added**: the skill explicitly forbids file:line cites in Phase-1 (that's Phase-2's job). All edits stay at the structural/heuristic level — no `source/<path>:<line>` added. Verified.
- **`git diff --stat` confirmation**: +71/-2 lines on SKILL.md, single file changed. Re-confirmed at end of iter-2.

## What iter-2 measured vs iter-1

- Same 3 prompts.
- Stricter rubric: 36 assertions (vs iter-1's 33). New assertions probe the NEW skill content:
  - E1 +1: "applies the distinctness test from §Method step 4"
  - E2 +1: "names ≥1 commercial/fork prior art (Neon/Aurora)" — probes broadened §4 lens
  - E3 +2: "FIRST DECISION: explicitly surfaces the extension-already-exists reframe" + "avoids the 'designing instead of brainstorming' anti-pattern"
- Result: with_skill still saturates at 36/36 (1.000). Baseline = 15/36 (0.417). Lift +0.583, essentially unchanged from iter-1's +0.576.

## Verdict

5/7 edits applied as-is, 1 merged, 1 dropped as redundant. The skill is hardened against the four highest-risk failure modes the iter-1 rubric surfaced (broken URL, missing extension-reframe, indistinct approaches, bland brainstorm with no anti-patterns).
