# Handoff — pg-claude session 2026-07-07

> **Read this first if you're picking up the pg-claude project cold or resuming after a break.**
> It's the durable summary of what state the project is in, what's on rails, and what needs a decision.

Last active: 2026-07-07 (interactive, 52-PR run).
Last commit before hand-off: PR #543 (`planner-cost-model` skill).

---

## What pg-claude IS, at a glance

A meta-repo that turns Claude Code into a deep collaborator on PostgreSQL internals. Two upstream PG clones mounted via symlinks:

- `source/` → `../postgresql/` — read-only reference, kept in sync with upstream master.
- `dev/` → `../postgresql-dev/` — mutable test field; all builds + patches happen here.

The corpus (`knowledge/`) is a **queryable knowledge graph** as of this handoff. Nothing here is speculative anymore — every layer is materialized as auto-populated markdown blocks that scripts refresh nightly. See §"Graph shape" below.

---

## 5-minute orientation

1. **Read `progress/STATE.md`** — the top entry is 2026-07-07 and describes the full 52-PR sweep. Everything above the `---` in that entry supersedes the older Phase A / B / C / D roadmap in the body.
2. **Read `sessions/2026-07-07-corpus-graph-interconnection.md`** — the 3-phase retro.
3. **Run `python3 scripts/corpus-chain.py --keywords "<your feature idea>"`** — this is the entry point for any new feature planning. It queries the whole graph.

---

## Graph shape (7 edges, all machine-refreshable)

```
scenario (34) ──files──> file (2594) ──backlinks:auto──> subsystem (65)
    │                                                        ▲
    │                                                        │
    │        idioms invoked                                   │
    │────────────────────────> idiom (161) ──callsites──> file
    │                              ▲                          │
    │                              │                          │
    │        scenarios that use me │                          │
    │◀─────────────────────────────                           │
    │                                                         │
    │        likely reviewers                                 │
    ▼                                                         │
persona (22)                          data-structure (35)─────┘
                                          (callsites)
```

Every edge is a bracketed `<!-- ...:auto -->` block in a doc, populated by one of the 6 refresh scripts:

1. `scripts/populate-idiom-callsites.py` — idiom → files (primary)
2. `scripts/populate-idiom-callsites.py --layer data-structures` — DS → files
3. `scripts/populate-idiom-callsites-v2.py` — 4 identifier-only idioms via glossary cross-ref
4. `scripts/populate-subsystem-files.py` — subsystem → files owned
5. `scripts/build-scenario-idiom-matrix.py` — scenario ↔ idiom bidirectional
6. `scripts/build-persona-scenario-matrix.py` — persona ↔ scenario/subsystem

All 6 chained by `pg-corpus-graph-refresh` cloud routine (04:17 nightly, roster now 12 sibs including this).

Query engine: `scripts/corpus-chain.py --scenario|--idiom|--file|--keywords [--depth 2]`. Wired into `pg-feature-brainstorm §2.5` (keyword discovery) + `pg-feature-plan §0.4` (scenario expansion). Slash command: `/pg-chain`.

---

## Skill inventory (61 total, +27 this session)

Master nav at `.claude/skills/pg-claude/SKILL.md` — the definitive per-topic index.

**Newly added subsystem skills, grouped by concern:**

| Concern | Skills |
|---|---|
| Bulk data ops | copy-family, toast-storage, backup-and-recovery |
| Statistics + planner | pgstat-framework, extended-statistics, planner-cost-model |
| Process model + resources | process-lifecycle, resource-owners |
| I/O + storage | aio-readstream, buffer-manager, free-space-map, slru-infrastructure |
| Transactions + visibility | vacuum-autovacuum, multixact, snapshot-management |
| Replication | logical-replication, physical-replication |
| Security + privileges | row-level-security |
| Extensibility | fdw-development, custom-scan-api |
| Language + protocol | plpgsql-internals, wire-protocol, collation-provider |
| Type system | type-cache, node-infrastructure |
| Data types | jsonpath-and-jsonb |
| Ops | pg-upgrade-internals |

Every skill dogfoods the corpus graph in its footer (`corpus-chain --file/idiom/scenario`).

---

## Cloud routine roster (12 siblings)

The daily automation is unchanged except this session added `pg-corpus-graph-refresh` at 04:17.

Full list in `.claude/cloud/pg-state-keeper.md` "Routine roster". Watchdog fires each morning at 05:43 with per-routine verdict.

---

## Untracked / open items (pick up here)

### High-value

- **STATE.md structural refactor** — the top prepend is fresh (07-07 covers everything), but the body from line ~200 onward still describes Phase A queue work that closed 2026-06-15. Someone should rewrite the "Phase A active work queue" section to reflect Phase A closed + Phase B/C/D (personas / calibration / data-leak hardening) status. Not urgent — new sessions read the top entry first — but noisy for humans.

- **Real feature attempt through the trilogy** — the graph + skills + planner integration have never been dogfooded on an actual feature-in-flight. Suggested test: pick a small PG bug or a `gap:*` that a skill flagged, run `/pg-brainstorm` → `/pg-plan` → `/pg-implement` and see whether the graph pulls in the right context or leaves gaps. This is the empirical validation Phase 1-3 were preparing for.

### Medium-value

- **`headers-wave3` subsystem** — currently the only subsystem with an empty `## Files owned` block (see `scripts/populate-subsystem-files.py` empty list). Either retire the doc, extend `CUSTOM_PATHS`, or explicitly document that it's a meta-doc that owns no directory. Semantic decision only, ~30-min task.

- **Skills you might add** (list from harvester gaps + adjacent areas):
  - `expression-evaluator` — ExecEvalExpr + ExecInterpExpr + EEOP_* interpreter steps + JIT mirror
  - `executor-node-lifecycle` — the Init/Exec/End/Rescan/Shutdown pattern per node
  - `full-text-search` — tsvector/tsquery/tsearch dictionaries
  - `range-types` — rangetypes.c + multirange
  - `regex-engine` — regexp.c (imported from Henry Spencer) — has been a security-audit target
  - `polymorphism` — anyelement / anyarray / anycompatible resolution
  - `advisory-locks` — pg_advisory_lock family, session vs transaction scope

None of these were flagged by harvester recently; they're nice-to-haves.

### Low-value

- **Persona ↔ idiom edges** — currently persona→scenario and persona→subsystem exist. persona→idiom would be a natural 8th edge (transitively via files) but the ROI feels lower than the existing 7 edges.

---

## Findings that need triage

These are things I noted while working but didn't stop to resolve. Some may not survive scrutiny — they should be debated before treating as canonical:

**T1. Depth-2 threshold is arbitrary.** `--depth 2` uses "≥2 shared files" as the sibling-idiom cutoff. Picked because "1 hit is too noisy across 161 idioms". No empirical basis for 2 vs 3 vs 5. On `add-new-wal-record` it produces 1 hit (`heaptuple-update-chain`), which felt reasonable. But on other scenarios it may over-produce or miss real patterns. Needs validation via 3-5 real queries.

**T2. Subsystem `## Files owned` uses path prefix + filename-filter heuristics for shared include dirs (storage/, utils/).** The filter lists (in `populate-subsystem-files.py` `INCLUDE_FILTERS`) are hand-authored per subsystem. May miss or over-claim files. Manual spot-check needed.

**T3. Persona-scenario edges use naive `path_is_under` matching.** A persona claiming `src/backend/executor/` gets matched against every scenario whose §Files includes anything under it. But some personas own a large directory nominally without actually reviewing everything under it (e.g. tom-lane owns `src/backend/utils/` as co-lead but doesn't review every utils patch). The 181-edge number might be inflated. Consider a "primary reviewer vs domain-expert" split.

**T4. Idiom v2 extractor (glossary-based, PR #495) picks up USE sites, not necessarily DEFINITION sites.** E.g. `SPI_connect` links to `contrib/spi/refint.c` (a caller) instead of `src/backend/executor/spi.c` (the definer). Users querying "where does SPI_connect live?" get misled. Fix would require a source-tree grep for the definition-line pattern, deferred to a v3.

**T5. `corpus-chain --keywords` scoring is coarse.** Matches by substring on slug + title. A search for "vacuum" matches everything with "vacuum" in it, un-weighted. Real relevance scoring would weight by recency + past-planning-hits + file-scope-size. Currently good enough for discovery; not great for precision.

**T6. 27 new skills, ~150-200 lines each, all written in one session.** Consistency across them is unaudited. Some may have overlapping content (e.g. `vacuum-autovacuum` mentions HOT prune which is fully covered in an idiom; `multixact` mentions tuple locking which overlaps `access-heap` subsystem). May or may not be a real problem.

**T7. Every new skill has a "Pitfalls" section (usually 8-10 items).** These are my synthesis + guesses at what trips people up. Some are true (backed by mailing-list threads I'd read); some are inferred (didn't verify against actual bug reports). Should be triaged against `knowledge/community/` archive for confirmation.

**T8. Wire-protocol skill (#515) claims PG 18 protocol 3.2 adds ParameterStatus subscription.** I believe this from harvester `#488` mentions but haven't verified against actual PG 18 code. Needs a source cite check.

**T9. Extended-statistics skill mentions "row estimate hints (PG 18+)".** Also from harvester; haven't verified.

**T10. AIO-readstream skill (#507) says "PG 18 promoted the underlying AIO layer to a first-class subsystem".** Verified against `source/src/backend/storage/aio/` existing (it does). But the specific claim of "read_stream introduced PG 17" vs "matured PG 18" — the exact version bounds may be off.

Together these are things a critical read of the shipped work should look at. Some are speculative; some are real; the point is I noted them under my breath and didn't stop to check.

---

## Refresh procedures

**After ANY change to `knowledge/idioms/`, `knowledge/scenarios/`, `knowledge/subsystems/`, `knowledge/data-structures/`, `knowledge/personas/`:**

```bash
python3 scripts/populate-idiom-callsites.py
python3 scripts/populate-idiom-callsites.py --layer data-structures
python3 scripts/populate-idiom-callsites-v2.py
python3 scripts/populate-subsystem-files.py
python3 scripts/build-scenario-idiom-matrix.py
python3 scripts/build-persona-scenario-matrix.py
```

All idempotent. Run order matters: matrices (last two) read the callsites/files-owned blocks that the first 4 write.

**Nightly:** `pg-corpus-graph-refresh` cloud routine does all 6 automatically at 04:17.

---

## Where to find things

| Question | Answer |
|---|---|
| What's the current corpus state? | `progress/STATE.md` (top entry) |
| What was done this session? | `sessions/2026-07-07-corpus-graph-interconnection.md` |
| What skill do I use for X? | `.claude/skills/pg-claude/SKILL.md` — the nav |
| What does the graph know about X? | `python3 scripts/corpus-chain.py --keywords "X"` |
| What's a good planning target? | `knowledge/scenarios/_index.md` decision tree |
| Who might review a patch on X? | `progress/persona-scenario-matrix.md` |
| Where does idiom Y apply in the tree? | idiom doc's `## Call sites` section |
| Where does file Z appear in the corpus? | `python3 scripts/corpus-chain.py --file <path>` |
| What are the open cloud PRs? | `gh pr list` |
| What's the graph refresh schedule? | `.claude/cloud/pg-corpus-graph-refresh.md` |

---

## Explicit non-goals (things this session did NOT do)

- No changes to `dev/` or `source/`. Zero PG patches. All work was in the meta-repo (`postgres-claude/`) and its knowledge / skills / scripts.
- No upstream submission. Nothing here is CommitFest-bound.
- No modifications to existing skills' semantics (only ADDITIVE — new skills only, plus 4 nav updates).
- No `pg-implement` invocation. Trilogy setup improved but not exercised end-to-end.

---

## Verified working (spot-checks)

- `scripts/corpus-chain.py --scenario add-new-wal-record` — full output including personas + depth-2 verified once.
- `scripts/corpus-chain.py --idiom memory-contexts` — full output verified once.
- All 6 refresh scripts idempotent (2nd run is 0-diff) — verified via PR #508 test.
- Master nav / master session log / STATE.md all consistent — verified by manual review.

## NOT verified (fresh state, could be issue)

- Any of T1-T10 above.
- Full end-to-end brainstorm→plan→implement using the graph. The individual pieces work; the composition wasn't dogfooded.
- The 27 new skills' auto-load descriptions actually route correctly for the queries Claude receives. Description-based routing is heuristic; a bad description means Claude misses the skill entirely.
