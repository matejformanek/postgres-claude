---
name: corpus-chain
description: Traverse the pg-claude knowledge graph to answer "what does this feature/file/pattern touch across the corpus?" — pulls scenarios, idioms, call-site file examples, sibling patterns, subsystem ownership, and analogous past features from planning/ + sessions/ into a single chain map. Uses the graph edges built by `scripts/populate-idiom-callsites.py` (idiom → files) and `scripts/build-scenario-idiom-matrix.py` (scenario ↔ idiom bidirectional). Use proactively when brainstorming a new PG feature, planning §3 file table, investigating an unfamiliar subsystem, or trying to find "have we touched something like this before?". Also use inside `pg-feature-brainstorm` step 1 (subsystem framing) and `pg-feature-plan` before §3 to seed the file list from existing evidence rather than pure grep. Skip when you already have the anchor's downstream chain memorized, when the task is a one-file bug fix, or when the ask is about non-PG code.
when_to_load: Investigate what the corpus already knows about a feature area before doing a heavy pg-feature-plan §3; find analogous past work; expand a starting scenario/idiom/file into its full neighborhood.
companion_skills:
  - pg-feature-brainstorm
  - pg-feature-plan
  - pg-claude
---

# corpus-chain — walk the knowledge graph

The pg-claude corpus is a graph. **This skill is the query engine.**

```
scenario ──(§Files)──> file ──(backlinks:auto)──> subsystem
   │                    │
   │  (§Idioms invoked) │  (idiom Call sites)
   ▼                    ▼
 idiom ──(Call sites)──> file
   ▲
   └──(Scenarios that use me)── scenario
```

## When to use

- **Before a brainstorm** — resolve keywords into candidate scenarios + idioms + past runs before framing.
- **Before `pg-feature-plan` §3** — a scenario chain gives you the initial file list, invoked idioms, adjacent scenarios (things you might also need), and past features with analogous file footprints.
- **When you land on an unfamiliar file** — see which idioms apply, which scenarios touch it, which subsystems own it.
- **When investigating a pattern** — start from an idiom, see its call sites + which scenarios invoke it + sibling idioms sharing files.
- **When the user asks "have we done anything like this before?"** — keyword mode surfaces past planning + sessions.

## Skip when

- The task is a one-file bug fix at a known location.
- You've already loaded and internalized the chain for this area in the current session.
- The task is non-PG (frontend, DevOps, other databases).

## How to invoke

```
scripts/corpus-chain.py --scenario <slug>     # e.g. add-new-wal-record
scripts/corpus-chain.py --idiom <slug>         # e.g. memory-contexts
scripts/corpus-chain.py --file <src-path>      # e.g. src/backend/access/heap/heapam.c
scripts/corpus-chain.py --keywords "..."       # free-text search
```

Output is markdown to stdout — read it, don't dump it wholesale into a plan.

## What the output tells you

### For a `--scenario` chain:

- **Files touched** — the initial §3 seed for `pg-feature-plan`.
- **Idioms invoked** — for each, tagged *direct* (named in scenario prose) or *transitive* (found because of file overlap). Direct-only for pure evidence; use transitive as "you'll probably also touch these patterns".
- **Adjacent scenarios** — related_scenarios frontmatter + scenarios sharing many files. If a scenario shares 5+ files, expect the two changes to conflict at review time; either bundle or sequence.
- **Subsystems** — which subsystem docs already cite these files. Cross-cutting features hit ≥ 2 subsystems.
- **Analogous past features** — planning slugs + session logs with keyword or file overlap. Read the top-2 before starting; they carry the design decisions you'll re-litigate.

### For an `--idiom` chain:

- **Call sites** — files that already apply this pattern. Pick 1-2 as your reference implementations.
- **Sibling idioms** — patterns co-located with yours. If both apply, cite both in the plan.
- **Scenarios that use me** — reverse index; which change-classes need this idiom.

### For a `--file` chain:

- **Idioms applying here** — before touching the file, know which patterns already live in it.
- **Scenarios touching this file** — if a scenario touches it, your feature might trigger the scenario's downstream effects.

### For `--keywords`:

- A shallow scan of scenario titles + idiom titles + planning + sessions.
- Use to *discover the anchor*, then re-run with `--scenario` / `--idiom` / `--file` for the full chain.

## Integration with the planner suite

### In `pg-feature-brainstorm` §0 / §5:

Run `--keywords` with the user's language first to find candidate scenarios and past work. Read the top-2 past-feature docs before writing §0's usage surface — they encode what worked and what got rejected. Then run `--scenario <picked>` to see the file scope you're inheriting.

### In `pg-feature-plan` before §3:

Run `--scenario <slug>` for the picked scenario. The output is the DRAFT §3 file table. Cite each file with `[via knowledge/files/<path>.md]` when the file doc exists. Idioms in the chain populate §8's per-phase "≥1 idiom" requirement automatically.

### In `pg-implement` per-phase:

For each phase's staged files, run `--file <path>` to see which idioms should be respected. If a phase touches a file where `memory-contexts` applies but the phase's edit doesn't use MemoryContexts, that's a smell — R7 escalate or reconsider.

## What the tool does NOT do

- **It does not invent claims.** Every edge is derived from an already-written link in the corpus (idiom's Call sites table, scenario's Files section, scenario's Idioms-invoked block, frontmatter references). If the graph is thin in some area, so is the answer.
- **It does not verify the anchor at the current commit.** Cite drift is possible if the corpus hasn't refreshed since the last upstream anchor bump — check the `last_verified_commit` in the target doc's frontmatter if the edge feels stale.
- **It does not rank quality.** Ordering is by shared-file count / hit count, not by prose quality. Read the source doc, don't rely on ranks alone.

## Refresh cadence

Chain results are only as good as the graph edges. Refresh order after any bulk corpus change:

1. `scripts/populate-idiom-callsites.py` — updates idiom → file edges.
2. `scripts/build-scenario-idiom-matrix.py` — rebuilds the scenario ↔ idiom join.
3. `scripts/corpus-chain.py --scenario/--idiom/--file/--keywords` — query.

Steps 1 and 2 are idempotent and safe to schedule from a cloud routine on anchor bumps.

## Examples

**"I want to add a new WAL record type."**

```
scripts/corpus-chain.py --scenario add-new-wal-record
```

Returns: 16 files, 9 idioms (5 direct + 4 transitive via `xlog.c`), 3 adjacent scenarios (add-new-index-am, bump-catversion, add-new-table-am), 2 subsystems, 1 past session.

**"Where is the memory-contexts pattern already applied?"**

```
scripts/corpus-chain.py --idiom memory-contexts
```

Returns: 4 canonical call sites, 8 scenarios that invoke it, 2 sibling idioms, past planning: jsonpath_leak / memory-hunt / sp2-pgstr-maxalloc.

**"Have we done anything with jsonpath before?"**

```
scripts/corpus-chain.py --keywords "jsonpath memory"
```

Returns: matching scenarios (fix-memory-leak), matching idioms, planning: jsonpath_leak (score 4), pgstat_progress_leak, session: 2026-06-23-memory-hunt-calibration.

## Failure modes

- **"anchor not found"** — the slug doesn't exist. Check `ls knowledge/scenarios/` or `ls knowledge/idioms/`.
- **Empty "Subsystems" section on a file** — the file's owner subsystem doc doesn't cite it with `source/<path>` inline. Path-prefix inference (owner = `<top-dir>/<second-dir>`) is a v2 improvement.
- **Fewer idioms than expected** — the scenario's `## Idioms invoked` block is stale; re-run `scripts/build-scenario-idiom-matrix.py` first.
