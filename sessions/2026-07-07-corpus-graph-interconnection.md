# Session — corpus-graph interconnection sweep

**Date:** 2026-07-07
**Mode:** interactive, user prompt: "focus on the ctx of the files & mainly some useful skills that should be baked into it so that we have good understanding and interconnections between different parts of the system which should allow us to easily create new parts as we will get the whole chained link connection when adding some feature"

## Ship list (9 PRs, all merged)

| # | PR | Landed |
|---|---|---|
| 492 | corpus(idioms): populate Call sites tables across 157 idioms | 2,096 rows across 157/161 idioms |
| 493 | corpus: build scenario ↔ idiom bidirectional matrix | 181 edges across 34 × 161 |
| 494 | corpus: add corpus-chain skill + /pg-chain command | Query engine on top of the graph |
| 495 | corpus(idioms): v2 extractor for the 4 identifier-only idioms | Glossary-based; all 161 idioms now covered |
| 496 | corpus(subsystems): populate Files owned tables across 64 subsystems | Path-prefix + include-filter derivation |
| 497 | skills: wire corpus-chain into brainstorm and plan | §2.5 (brainstorm) + §0.4 (plan) |
| 498 | cloud: add pg-corpus-graph-refresh routine (04:17 nightly) | Chains all 4/5 scripts, roster now 11 |
| 499 | corpus(data-structures): populate Call sites across 35 struct docs | Generalized primary script with `--layer` |
| 500 | corpus(chain): traverse data-structures layer too | Chain surfaces DS docs in file/scenario queries |

Plus the pg-claude master nav skill update (this session's tail commit).

## Before / after interconnection audit

| Edge | Before | After |
|---|---|---|
| Idiom → files (call sites) | 0 / 161 | **161 / 161** |
| Data-structure → files (call sites) | 0 / 35 | **35 / 35** |
| Subsystem → files owned | 13 / 65 (20%) | **64 / 65 (98%)** |
| Scenario ↔ idiom bidirectional | ad-hoc | **181 explicit edges** |
| Scenarios with zero linked idioms | 1 / 34 | **0 / 34** |
| Idioms with zero linked scenarios | 125 (ad-hoc infra) | 78 (still expected — cross-cutting) |
| File → subsystem/idiom (backlinks:auto) | 880 / 2594 (34%) | unchanged (routine's job) |

## Method

Evidence-preserving extraction. Every auto-block is derived from a link already present in the corpus:

- Idiom call sites: extracted from inline `source/<path>:<line>` cites in the idiom's prose (bullets + free text, with continuation-line support).
- Idiom v2: for the 4 conceptual idioms (fmgr, node-types-and-lists, parser-pipeline, spi) that use bare backticked identifiers instead of file:line cites, cross-referenced against `knowledge/glossary.md`'s "via `knowledge/files/…`" links.
- Subsystem files owned: derived from a small path-prefix map (slug → directories) with filename filters for shared include-dirs.
- Scenario ↔ idiom: union of direct references (frontmatter + prose links to `knowledge/idioms/<slug>.md`) plus transitive file-overlap (scenario cites `foo.c`, idiom's Call sites include `foo.c`).

No new claims invented. If the graph is thin in some area, so is the answer.

## New surface

**Scripts (all idempotent, safe to re-run nightly):**
- `scripts/populate-idiom-callsites.py [--layer idioms|data-structures]`
- `scripts/populate-idiom-callsites-v2.py`
- `scripts/populate-subsystem-files.py`
- `scripts/build-scenario-idiom-matrix.py`
- `scripts/corpus-chain.py --scenario/--idiom/--file/--keywords`

**Skill + slash command:**
- `.claude/skills/corpus-chain/SKILL.md`
- `.claude/commands/pg-chain.md` (`/pg-chain <args>`)

**Cloud routine:**
- `.claude/cloud/pg-corpus-graph-refresh.md` (04:17 nightly)

**Central artifact:**
- `progress/scenario-idiom-matrix.md`

**Skill integrations (call-sites for the graph):**
- `pg-feature-brainstorm/SKILL.md` step 2.5 → `--keywords` discovery before deep-load
- `pg-feature-plan/SKILL.md` step 0.4 → `--scenario` expansion before parallel fan-out
- `pg-claude/SKILL.md` — master nav gains a "Corpus graph" section documenting the 6 edge layers.

## F / L graduation

**F31 — Scenarios cite files two ways.** Scenarios reference source paths as both `source/src/…` (prefixed) and bare `src/…` / `contrib/…`. First implementation of the matrix builder only caught the prefixed form and produced 81 edges. Fixing the regex to accept both forms doubled to 181 edges. Lesson for future extractors: always confirm coverage by sampling a scenario that uses each format.

**F32 — Idiom template heterogeneity.** 161 idioms follow at least 4 different conventions:
- Full `Anchors:` block + inline `source/…:LINE` cites → primary extractor covers cleanly.
- No Anchors block but inline cites in prose bullets → primary extractor covers (with continuation-line support).
- File-level `source/…` refs without line numbers → emitted with `—` in Line column.
- Bare backticked C identifiers (no source paths at all) → primary extractor returns zero; v2 script needed.

The v2 fallback via glossary cross-reference is a good pattern for any "structured-prose" corpus that needs machine-readable joins.

**L6 — Materialize the graph edges rather than compute at query time.** Original alternative was a smart query engine that would parse idiom prose live to answer "which files does this idiom apply to?". Materializing the `## Call sites` block in each idiom instead gives:
- O(1) lookup at query time (just read the auto-block).
- Human-readable table in the doc itself — the graph is visible even without the query tool.
- Cheap idempotent refresh: 4 scripts, ~30 seconds total to regenerate all 6 layers.

Turning the graph into a stored artifact was worth the ~5,000 lines of auto-generated markdown across 195 files. The query engine (`corpus-chain.py`) is only ~600 lines because the work happens at write time, not read time.

**L7 — Wire the query engine into the happy path or it's dead weight.** After PR #494 the skill existed but nothing pulled it in. PR #497 fixed that: brainstorm §2.5 and plan §0.4 now MANDATE the query. Skills-without-invocation-points are just docs.

## Chain-link status (the user's ask)

The literal path a new feature planning session now traverses:

```
User asks: "add a new WAL record type"
    │
    ▼
brainstorm §2.5 runs:  scripts/corpus-chain.py --keywords "WAL record"
    │  → discovers scenario `add-new-wal-record` + past planning slugs
    ▼
brainstorm loads scenarios + subsystems named by the chain
    │
    ▼
plan §0.4 runs:  scripts/corpus-chain.py --scenario add-new-wal-record
    │  → returns 16 files, 9 idioms (5 direct + 4 transitive), 3 adjacent scenarios
    │  → each idiom's ## Call sites gives concrete pattern examples
    │  → each subsystem's ## Files owned lists the file scope
    ▼
plan §0.5 fan-out verifies + expands the chain's file list
    │
    ▼
plan §8 auto-satisfies "≥1 idiom per phase" from the chain
```

Every arrow is a materialized block in the corpus. No manual grepping in the middle. The user's "whole chained link connection" is now the default flow.

## Outstanding follow-ups

- Update `progress/STATE.md` with a Phase E entry documenting this sweep (memory-keeping pass — deferred to next session).
- Handle the 2 untracked skill workspaces (`pg-feature-brainstorm-workspace/`, `pg-feature-plan-workspace/`) from Jun-17 skill-creator runs — either `.gitignore` them or delete.
- The COPY-family skill gap flagged by `pg-user-question-harvester` (#434) — still open.
- `headers-wave3` subsystem: empty Files owned block; unclear what it should map to. Ask user or retire the doc.
- Depth-2 traversal in corpus-chain for cases where the 1-hop neighborhood is insufficient.

## References

- PRs: #492, #493, #494, #495, #496, #497, #498, #499, #500
- Prior interconnection audit: earlier this session (turn 3).
- Related past work: `sessions/2026-06-16-scenarios-layer.md` (built the scenarios layer that this sweep interconnects).
