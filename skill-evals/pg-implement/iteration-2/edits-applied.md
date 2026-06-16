# Iteration 2 — edits applied

Applied to `.claude/skills/pg-implement/SKILL.md` from `iteration-1/proposed-edits.md`.

## Verification of cites and policy claims (before applying)

`pg-implement` is a *procedure + policy* skill — its claims are about the project's own R1–R12 rules and slug conventions, not about PG source internals. Verifications performed:

- **R-numbers and rule wording** — read `.claude/rules/pg-implement-discipline.md` end-to-end. Confirmed: R2 wording ("off by more than ~20 lines or naming a since-removed symbol"); R6 wording ("'addresses', 'fixes', or 'implements' claim ... must point to a file:line"); R7 three-path enumeration; R8 notes.md template fields (Status / Commit / Tests-run / What-changed / Surprises / What-this-phase-did-NOT-do); R10 two-repo separation; R12 end-of-implementation gate steps. All wording in the applied edits matches the rules file.
- **§Anti-patterns wording** — confirmed the five forbidden items: WIP commits / `--amend` across phases / commits without Plan: trailer / cherry-picking phases / mixing meta-repo + dev/ writes. Mirrored verbatim into new SKILL.md §"Forbidden patterns" block.
- **Slug-naming convention** — listed `planning/` and confirmed real slugs in repo: `cb1-pgcrypto-bomb`, `cb7-ltree-amplification`, `cb8-hstore-forge`, `sp2-pgstr-maxalloc`, `sp6-autoprewarm-revoke`, `sp7-tablefunc-quoting`. Branch-name example `feature_server_side_vars` is already in R1; used `feature_sp2_pgstr_maxalloc` (from `planning/sp2-pgstr-maxalloc/notes.md`) as a concrete second example.
- **Bisectability + per-commit-pass rationale (Edit 1)** — this is a project-policy claim, not a source-internals claim, so no `source/<path>:<line>` cite needed. Verified consistent with the rules file's anti-pattern list (which forbids WIP commits) and R5 (upstream PG style; commits may be format-patched). The bisectability framing is implicit in R4 + R12 (every commit must pass; final log must show N green commits) — the edit makes it explicit.

No `source/<path>:<line>` cites were proposed in this edit set (the skill governs procedure, not PG internals), so no source file reads were required beyond confirming the rules file.

## Edits applied (all 6)

1. **Edit 1 (HIGH) — added §"Why per-phase = per-commit + per-test" block** between §Strict rules item 6 and §Method. Inlines two operational rationales: bisectability and per-commit reviewability (upstream PG convention that every commit in a posted series compiles + passes on its own). Closes the only two iter-1 with_skill misses (Eval 3 assertions 7 + 8).

2. **Edit 2 (MED) — added Status field semantics** below the §Phase-end log template. Spells out `done` / `partial` / `deferred` meanings so a reader can pick the right value without re-reading R8.

3. **Edit 3 (MED) — promoted R2's drift definition** into §Strict rules item 2. Previously SKILL.md said only ">10%"; now spells out "citations off by more than ~20 lines, or naming a since-removed symbol" (verbatim from R2).

4. **Edit 4 (MED) — tightened §Style commit-message bullet** to import R6's exact "addresses / fixes / implements" verb list and the source/plan-section disjunction.

5. **Edit 5 (MED) — added §"Forbidden patterns" sub-block** to §Strict rules. Mirrors the five anti-patterns from the rules file verbatim. Keeps rules authoritative; makes the contract readable from SKILL.md alone.

6. **Edit 6 (LOW) — named slug-naming convention with examples** in §Inputs. Added `sp2-pgstr-maxalloc`, `cb1-pgcrypto-bomb`, `sp7-tablefunc-quoting` as in-repo examples, plus the branch-name mirror pattern.

## Edits NOT applied

None. All six proposed edits passed verification and were applied.

## Resulting structure of SKILL.md (post-edits)

Net structural change: §Strict rules grew from 6 numbered items + a method-block transition to 6 items + 2 new sub-blocks (§"Why per-phase = per-commit + per-test", §"Forbidden patterns"). Inputs gained a slug-example sub-bullet. §Phase-end log gained a Status-field semantics block. §Style commit-message bullet extended with R6 verb list. §Strict rules item 2 extended with the drift-signal definition.

Line count delta: +44 lines (rough estimate; new content is all additive — no existing content removed).

## Test rerun

Re-ran the same three prompts (iter-2 evals.json identical to iter-1's). Re-scored against the same 31 assertions:

- with_skill: 29 → 31 (93.5% → 100%, +2 hits).
- baseline: 12 → 12 (unchanged; identical answer).
- delta: +54.8pp → +61.3pp.

The two hits closed:
- Eval 3 assertion 7 (bisectability) — now cited verbatim from SKILL.md §"Why per-phase = per-commit + per-test".
- Eval 3 assertion 8 (per-commit reviewability) — now cited verbatim from same block.

No regressions.
