---
name: review-checklist
description: Review a PostgreSQL patch using the wiki's seven-phase checklist — covers Phase 0 reviewer-reflex gates + REJECT-A/B/C grade rubric for design rejections, plus the wiki's Phases 1-7 (apply/build, regress + check-world, pgindent, design fit, docs, comments, committer-readiness). Applies to reviewing someone else's pgsql-hackers / CommitFest submission OR self-reviewing your own patch before mailing it. Use whenever the user says "review this patch", "is it ready to send to hackers", "CF entry NNNN review", "pre-submission review", "REJECT this patch", or pastes a pgsql-hackers thread asking for a structured review. Skip for generic GitHub PR code review (app code), Terraform / Helm chart review, Python / Ruby / Rust / Go application code review, security audit (use security-review), API design review on REST / GraphQL endpoints, and documentation-only review for non-PG projects.
when_to_load: Review a PG patch (others' or own) using the seven-phase scaffold; reach a REJECT-A/B/C verdict at Phase 0; produce per-phase findings for `pg-patch-review`'s critics to consume.
companion_skills:
  - pg-patch-review
  - patch-submission
  - pg-feature-plan
  - pg-implement
  - commit-message-style
  - coding-style
  - testing
  - wal-and-xlog
  - locking
  - error-handling
  - memory-contexts
  - catalog-conventions
---

# Review Checklist Skill

Reviewing in PostgreSQL is structured into **seven phases** per the wiki.
Run them in order — the cheap checks first, the deep ones last. The same
checklist applies pre-submission (review our own work) and post-submission
(review someone else's CF entry).

## Companion skills

This skill is the **orchestration layer**. When a phase points into a
specialist domain, hand off to the corresponding skill instead of
re-deriving the deep rules here:

- `wal-and-xlog` — WAL records, redo functions, RM registration, hint bits
- `locking` — lock primitive choice and acquisition order
- `error-handling` — `ereport`/`elog`/SQLSTATE/message-style choices
- `memory-contexts` — `palloc` placement, context lifetimes
- `coding-style` — pgindent survival, include order, C99 subset
- `catalog-conventions` — `pg_proc`/catalog column/OID assignment work
- `testing` — picking regress vs isolation vs TAP vs module
- `commit-message-style` — judging committer-readiness of the message
- `patch-submission` — pre-submission of our own change

## Phase 0 — Reviewer-reflex gates + REJECT-track (added 2026-06-12)

Three persona-driven gates + the REJECT-A/B/C grade rubric. Both fire
before the mechanical checks. Each gate was triggered repeatedly
across the five Phase C calibrations (`knowledge/calibration/`);
leaving them implicit causes the mechanical-only review to ship
patches that real reviewers will push back on. If any gate fails, the
patch goes back to the author with the gate's specific question
before Phase 1.

The REJECT-track was added 2026-06-12 from Phase E run 1 (M4 in
`knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`).
Not every patch should proceed to Phase 1 mechanical review — some
are design-level NACKs where the right output is a thread reply
explaining why the proposal can't proceed, not a phased
implementation. Phase 0 is where that branch happens.

The full reflex catalog is at `knowledge/calibration/gap-catalog.md`
items 1-3.

### REJECT-track decision (M4)

Run this **first** in Phase 0 — before the three reflex gates. If the
patch is design-level rejectable, the gates are moot.

A patch is REJECT-track candidate if any of:

- **Design forecloses on a documented PG invariant** (e.g. proposes a
  network-IO immutable function; would require backwards-incompatible
  on-disk format change without an upgrade path; violates a
  subsystem's `INV-*` tag that the corpus has documented).
- **Context-awareness probe flags it** (per `pg-feature-plan`'s
  Context-awareness pre-step: April-1 thread, joke proposal,
  demonstrably unimplementable).
- **Engagement classification is `contested`** (per `pg-feature-plan`'s
  Thread-engagement classification: named senior contributors raising
  correctness/design objections that haven't been addressed).

If REJECT-track applies, grade as:

| Grade | Meaning |
|---|---|
| `REJECT-A` | Identified all critical design problems, proposed correct alternative. Equivalent to an A-grade review on a serious patch — saves the community cycles. |
| `REJECT-B` | Identified most critical problems but missed one major concern. |
| `REJECT-C` | Rejected for the wrong reasons OR rejected when the proposal was actually sound. Self-correct: re-open and run the seven-phase review. |

For REJECT-A/B verdicts: the deliverable is a thread reply per the
"Posting the review" section below, NOT a phased implementation plan.
The reply names the specific reasons (cited to `source/` invariants
or `knowledge/personas/<name>.md` design reflexes) and offers the
alternative if one exists. Don't continue to Phase 1.

For REJECT-C: stop, escalate to the user — your verdict probably
needs revision before going public.

### Gate 1 — `security@` embargo (HARD)

**Trigger:** the patch's commit message or COVER body contains any of
`DoS`, `denial of service`, `decompression bomb`, `amplification`,
`integer overflow`, `buffer overflow`, `injection`, `TOCTOU`,
`privilege`, `REVOKE`, `GRANT`, AND the patch touches a path
callable via a public SQL API (any `contrib/*/` `.c` exporting a
`Datum *` function; any `src/backend/utils/adt/`; any
`contrib/*/*--*.sql`).

**Question:** has `security@postgresql.org` been notified before
this thread on `pgsql-hackers`?

**Exemption protocol:** the author may answer "no embargo needed
because (defense-in-depth + auth-required + DoS-class + no data
disclosure)" — that's the SP6 shape (`sp6-autoprewarm-revoke.md`).
The exemption argument is acceptable when explicitly stated in COVER;
the gate is about asking the question, not auto-blocking.

**Calibration support:** 5-for-5 across CB1+CB7+CB8+SP2+SP6
(catalog item 1). Source persona: `noah-misch.md` §2.

### Gate 2 — Test-omission skepticism (HARD on security patches)

**Trigger:** the patch's COVER acknowledges "no regression test,
the fixture would dominate buildfarm time / would need N LOC of
scaffolding".

**Question:** is `PG_TEST_EXTRA=stress` (per Daniel Gustafsson's
online-checksums work) an acceptable home for the test? Even if
the fixture costs 50-100 LOC, the structural-correctness claim
needs a counterexample.

**Exemption protocol:** a `PG_TEST_EXTRA=stress` test is the default
answer. "Skip the test" is acceptable only if the patch is a pure
refactor with existing test coverage of the refactored path.

**Calibration support:** 3-for-3 (CB1+CB8+SP2); pre-empted by
SP6 which added both SQL and TAP tests up front (catalog item 2).
Source personas: `noah-misch.md` §1+§5.

### Gate 3 — Install-script immutability

**Trigger:** the patch modifies a `contrib/*/*--A--B.sql` file
where the `A→B` extension version was released in a tagged
PostgreSQL version.

**Question:** are we editing a shipped extension upgrade script?
Shipped `--*.sql` scripts are immutable post-release — installations
that already ran the `A→B` upgrade have a different post-state than
a fresh install with the edited script. The right shape is shipping
a new `--B--C.sql` with the desired behavior.

**Exemption protocol:** none routine. If you really need to fix a
shipped script (rare — e.g. a syntax error that prevents the script
from running at all), that needs explicit hackers thread agreement
captured in the commit body.

**Calibration support:** 1-for-1 (SP6) but flagged in the methodology
plan as the install-script reflex to test for (catalog item 3).
Source persona: `tom-lane.md` API/ABI back-compatibility reflex
applied to install-script files.

## Phase 1 — Submission review (5 minutes)

Cheap, mechanical checks. If any fail, kick back to author immediately
(`Waiting on Author`) — don't waste cycles on later phases.

- [ ] Patch is in unified or context diff format (with context lines).
- [ ] Applies cleanly to current `master`:
      ```bash
      cd $PG_SOURCE && git checkout master && git pull
      git am --abort 2>/dev/null
      git am /path/to/vN-0001-*.patch  # ... and the rest
      ```
- [ ] Filename follows `vN-0001-…patch` convention.
- [ ] Includes tests (look for changes under `src/test/`).
- [ ] Includes doc updates (look for changes under `doc/src/sgml/`) — or
      explicit justification for none (e.g. internal refactor).

## Phase 2 — Usability review

Does the patch do what it claims?

- [ ] Read the cover email's stated goal. Does the diff match?
- [ ] If it adds SQL syntax: does it align with SQL standard / existing
      PG conventions?
- [ ] Does it need `pg_dump` support? If new schema objects, **yes**.
- [ ] Does it interact with other features sensibly (extensions,
      logical replication, parallel query, …)?
- [ ] Are GUC names / catalog column names / function names well-chosen
      and consistent with neighbors?

## Phase 3 — Feature test

Build and exercise it.

```bash
cd $PG_BUILD_DIR
# configure with -Dcassert=true -Ddebug=true if not already
ninja
meson test
```

- [ ] Clean build, no new warnings.
- [ ] All existing tests still pass.
- [ ] New tests actually fail without the code change (sanity: revert
      just the code part and re-run the new tests — they should fail).
- [ ] Exercise corner cases the author didn't test: empty input,
      max-length input, NULL, encoding edges, concurrent calls, etc.
- [ ] Crash-test under assertion build.

## Phase 4 — Performance review

- [ ] Does it slow down anything currently fast? (Run `pgbench` baseline
      + new build comparison for any hot-path change.)
- [ ] If the patch claims a speedup, does it deliver? Reproduce.
- [ ] Any new O(N²) or unbounded loops? Acceptable only with rationale.
- [ ] Hot-loop micro-optimization? Re-run at significantly larger N than
      the author's benchmark — a faster constant factor that conceals a
      quadratic term is a footgun.
- [ ] Memory: any new per-tuple / per-row allocation? Should it use a
      short-lived MemoryContext?

## Phase 5 — Coding review

Read the diff line by line.

- [ ] Style matches the surrounding module (CamelCase vs snake_case).
- [ ] No long lines that could reasonably be wrapped.
- [ ] Comments explain *why*; no noise comments.
- [ ] Uses existing infrastructure: `ereport`, `palloc`, `MemoryContext`,
      `ResourceOwner`, `fmgr`, `SPI` — not parallel reinventions.
- [ ] Error messages follow the message style guide (capitalization,
      no period on `errmsg`, `errdetail`/`errhint` separated correctly).
- [ ] No new platform-specific code without portability gating.
- [ ] No new compiler warnings with `-Wall -Wextra`.

## Phase 6 — Architecture review

The harder one — does this fit?

- [ ] Locking: are locks acquired in an order consistent with the rest
      of the system? Could this deadlock against existing paths?
- [ ] Concurrency: signal-handler safety, `PG_TRY`/`PG_CATCH` resource
      cleanup, reentrancy.
- [ ] Storage / WAL: backwards-compatibility of any on-disk or WAL
      format change. New WAL records → `XLOG_PAGE_MAGIC` bump. Deep
      checklist: hand off to the `wal-and-xlog` skill.
- [ ] Hint-bit handling in redo: `MarkBufferDirtyHint` vs
      `MarkBufferDirty` — using the wrong one corrupts recovery.
- [ ] Catalog change → `CATALOG_VERSION_NO` bumped, OIDs assigned, and
      this is master-only (never backpatchable).
- [ ] If touching `src/include/` structs in back branches: ABI rules —
      new members at end, no signature changes on exported functions,
      new enum values at end. Inline functions and macros in
      `src/include/` are also part of the extension-visible ABI; treat
      them with the same back-branch caution.
- [ ] Does it foreclose obvious future extensions? Flag if yes.

## Phase 7 — Review review

Before posting:

- [ ] Have I covered all six prior phases, or am I explicit about which
      I skipped and why?
- [ ] Have I distinguished **blocking** issues from **nits**?
- [ ] Are my asks **concrete**? "Please add a test for the empty-array
      case" beats "needs more tests."

## Posting the review

- Reply to the **patch email** on pgsql-hackers (preserve threading).
- Plain text, no HTML, no top-posting — quote inline and respond
  beneath each quoted block.
- Structure suggestion:
  1. One-line summary of where the patch stands.
  2. **Blocking issues** (numbered list).
  3. **Nits / style** (numbered list).
  4. **Questions / design discussion**.
- Flip the CommitFest entry:
  - `Waiting on Author` if you raised blocking issues
  - `Ready for Committer` if you're satisfied (committer will still
    re-review)
- For **performance reviews**, include a small table: master tps,
  patched tps, run count, hardware, build flags, exact repro recipe.
  Numerical claims without a recipe get bounced.

## Pre-submission self-review

When reviewing our **own** change before sending upstream, run the same
seven phases but be ruthless on:

- Tests cover corner cases, not just the happy path
- Docs include an example
- Commit history is split into logical units
- `git diff --check` is clean
- No leftover debug `elog(WARNING, ...)`, no commented-out code
- Catversion / WAL magic / control version bumps where needed

## Sources

- [Reviewing a Patch — wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)
- [Submitting a Patch — wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)
- [Committing Checklist — wiki](https://wiki.postgresql.org/wiki/Committing_checklist)
- knowledge/community/review-patterns.md

## Cross-references

- `.claude/skills/pg-patch-review/SKILL.md` — multi-agent orchestration above this scaffold; each critic walks one of these phases.
- `.claude/skills/patch-submission/SKILL.md` — invokes this skill (via `pg-patch-review --self`) for the self-review path before format-patching.
- `.claude/skills/pg-feature-plan/SKILL.md` — supplies the Context-awareness and Thread-engagement classification feeding Phase 0's REJECT-track.
- `.claude/skills/commit-message-style/SKILL.md` — Phase 5 / committer-readiness defers to this for the commit-message check.
- `.claude/skills/coding-style/SKILL.md` — Phase 5 style check.
- `.claude/skills/testing/SKILL.md` — Phase 3 / Phase 6 test-coverage and feature-test checks.
- `knowledge/calibration/gap-catalog.md` — items 1-3 source the three reflex gates in Phase 0.
- `knowledge/personas/noah-misch.md`, `knowledge/personas/tom-lane.md`, `knowledge/personas/daniel-gustafsson.md` — persona drivers behind the gates.
- `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md` — M4 origin (REJECT-A/B/C rubric).
