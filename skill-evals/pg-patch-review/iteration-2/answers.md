# Iteration 2 — answers (with_skill vs baseline)

After applying edits 1-5 to `.claude/skills/pg-patch-review/SKILL.md`.

## Eval 1 — Drive a mailing-grade review of CF #5912 end-to-end

### with_skill answer

The skill defines a **five-stage pipeline**.

**Stage 0 — mechanical pre-amble**. The prompt says this is done.
Were it not done, the skill now ships an inline 9-step recipe (no
`/pg-review` needed):
1. `cd dev && git checkout master && git pull`
2. `git checkout -b cf5912-review`
3. Fetch the v3 patch from the CF entry.
4. `git am v3-*.patch`
5. `ninja -C build-debug install` — warning-clean.
6. `meson test --no-rebuild regress/regress`.
7. `meson test --no-rebuild --suite isolation`.
8. `git diff --name-only HEAD~N..HEAD`.
9. Note pre-existing flakes (macOS
   `recovery/040_standby_failover_slots_sync`).

Output: touched-files list, test results, dispatch block input.

**Stage 1 — orchestrator project discovery** (~5 min):
1. **Touched files → touched subsystems.** LWLock tranche + shmem
   region maps to `knowledge/subsystems/storage-*.md` (LWLock and
   shmem live in storage-ipc.md in our corpus). New system view +
   catalog rows maps to a catalog subsystem doc.
2. **Per-file docs.** Look up `knowledge/files/<path>.md` for each
   touched file. Missing per-file docs get flagged in the email's
   "Testing performed" block.
3. **Claims → CHECKs**: (a) "backwards-compatible — only catalog
   rows and shmem region" → Critic B; (b) "no WAL changes" →
   Critic B; (c) "mechanical refactor of LWLockNewTrancheId
   callers" → Critic A (every removed line has an equivalent).
4. **Dispatch block**: patch ref + branch SHA + touched files (with
   per-file-doc presence/absence flags) + subsystems + verbatim
   claims + Stage-0 test summary.
5. **Citation drift spot-check**: 3-5 cites against `source/`. > 10%
   drift (cites stale > ~20 lines OR removed symbols) → STOP. The
   escalation is now wired to the real workflow: ask the user
   whether to (a) refresh the corpus first via a separate
   `hf(corpus):` commit per Rule R9 of
   `.claude/rules/pg-implement-discipline.md`, or (b) proceed with
   a "best-effort against possibly-stale docs" caveat in the email.
   No more pointing at the missing `pg-corpus-maintainer` skill.

**Stage 2 — five critics IN PARALLEL** (single message of parallel
tool calls, ~10-20 min wall):

- **Critic A — Architecture & invariants.** Loads storage-ipc.md +
  per-file docs + `review-checklist` Phase 6. Checks
  `LWLockRegisterTranche` / `LWLockNewTrancheId` usage, lock-order
  discipline, mechanical-refactor equivalence (every removed line
  has an equivalent), provenance via `git -C source log -S
  '<symbol>'`. Loads `locking`, `memory-contexts` siblings.
- **Critic B — Breaking-change scan.** Loads `wal-and-xlog`,
  `catalog-conventions`, Phase 6's breaking-change bullets. Checks:
  on-disk format, WAL records, `CATALOG_VERSION_NO` bump + OIDs +
  back-branchability, `src/include/` ABI (new struct members at
  end, no exported-signature changes, inline functions/macros
  count), replication protocol, pg_dump impact for the new view.
- **Critic C — Test coverage.** Loads `testing`. Refactor claim →
  `git grep` the function names in `src/test/`. New view → corner
  cases (empty, max-length, concurrent updates).
- **Critic D — Style & commit-message.** Loads `commit-message-
  style`, `coding-style`. Filename, imperative title, ~76 col wrap,
  no Co-Authored-By (forbidden upstream), Author/Reviewed-by
  trailers, Discussion: link, `git diff --check`, pgindent.
- **Critic E — Reviewer-reflex probes** (catalog #4-#11). Loads
  `knowledge/calibration/gap-catalog.md` + relevant
  `knowledge/personas/*.md`. The skill now ships a **severity
  matrix at a glance** table at the end of §Critic E:

| # | Probe | Default | Escalates to blocking when |
|---|---|---|---|
| #4 | Cleanup-on-early-return | warning | COVER doesn't acknowledge cleanup |
| #5 | Multibyte / encoding | warning | text cap with no per-encoding analysis |
| #6 | Subsystem-local cap discoverability | suggestion | — |
| #7 | "Third state" binary-format | warning | COVER doesn't enumerate both states |
| #8 | injection_points reproducer | warning | structural argument on security claim, no probe |
| #9 | Hot-path micro-benchmark | suggestion | — |
| #10 | Symmetric-check refactor | suggestion | — |
| #11 | Persona-aware backpatch routing | suggestion | — |

REJECT-track escalation: 3+ blocking rows AND a context-awareness
signal (engagement class `contested` OR a foreclosed `INV-*`
invariant) → recommend REJECT-A to Stage 3.

For CF #5912 (LWLock tranche + new view), the likely-firing probes
are #6 (new `#define` for tranche or row count → move to subsystem
.h) and #10 (3+ near-identical registration blocks → shared inline
helper). Catalog #1-3 are NOT this critic's job — they live in
`review-checklist` Phase 0.

**Stage 3 — orchestrator consolidates** (~10 min). The skill now
leads §Stage 3 with the **Critic-E recommendation vs orchestrator
verdict** rule: Critic E may emit `recommend_verdict: REJECT-A |
REJECT-B`, but Stage 3 decides; the orchestrator may downgrade to
"Waiting on Author" if the findings don't compose to a design-level
NACK. Critic E's recommendation is one input, not the verdict.

Then: deduplicate (merge cross-critic flags), resolve conflicts
(re-read both critics, cite both), bucket Blocking/Warning/Nit/Open,
pick verdict — Ready / Waiting on Author / Needs more info /
**REJECT-A** (design wrong, all critical issues caught, alternative
proposed) / **REJECT-B** (design wrong, missed a major concern) /
**REJECT-C** (rejected wrongly — STOP, escalate to user).

**Stage 4 — synthesize the review email**, using
`commit-message-style` tone rules (imperative, plain text, no HTML,
no emoji, ~76 col wrap). The email at
`sessions/<date>-cf5912-review.md` has: one-line summary,
high-level read with file:line cites, Blocking, Warnings, Nits,
Open questions, Testing performed (git am / ninja install / regress
/ isolation / patch base), closing line. Below the email in the
SAME session file: per-critic raw findings + Stage 0 mechanical log
+ wall time per stage.

**Sibling-skill / knowledge loads**: subsystem docs (storage-ipc.md,
catalog-* docs); sibling skills review-checklist, wal-and-xlog,
catalog-conventions, testing, coding-style, commit-message-style,
locking, memory-contexts; Critic-E loads gap-catalog.md items 4-11
plus personas per probe trigger.

**Deliverable**: `sessions/<date>-cf5912-review.md` (review email +
per-critic appendix + Stage 0 log + wall time). Patch branch
`dev/cf5912-review` is disposable after the review is mailed.

### baseline answer

(unchanged from iter-1 — baseline doesn't load SKILL.md)

For a mailing-grade review of CF #5912 I'd be systematic:
1. Mechanical first: apply, build, run tests. The prompt says done.
2. Read COVER claims and verify against the diff. The three are
   backwards-compatible, no WAL changes, mechanical refactor.
3. For each claim, run a targeted check (catalog version, WAL/
   rmgrlist grep, every removed line has an equivalent).
4. Test coverage: src/test/ changes? New view should be tested.
5. Style: imperative commit title, no Co-Authored-By upstream,
   pgindent, no debug elog.
6. Architecture: lock-acquisition order, parallel query +
   replication interactions.
7. Synthesize a review email: plain text, blocking vs nit, concrete
   asks, CommitFest flip.

No multi-agent fan-out, no named REJECT-A/B/C, no knowledge/ docs.

---

## Eval 2 — Adversarial probe: BufFile leak on ereport in ReorderBufferIterTXNInit

### with_skill answer

This is Critic E catalog #4 probe.

**Critic E — Cleanup-on-early-return tracing (catalog #4)**:
- **Trigger**: a new `return` (or `ereport(ERROR, ...)` longjmp)
  added inside a function whose entry block owns a resource handle —
  `z_stream`, `BufFile`, `FileFd`, `MemoryContext`, `Relation`,
  `LWLock`. The diff opens a `BufFile` via `BufFileCreateFileSet`
  and the new error path does NOT call `BufFileClose` before
  `ereport(ERROR, ...)`. Trigger fires.
- **Persona driver**: `daniel-gustafsson.md` errorhandling discipline.
- **Severity** (per the new severity-matrix table at the end of
  §Critic E): default `warning`; **escalates to `blocking`** when
  COVER doesn't acknowledge the cleanup question. The author's
  "MemoryContext on backend reset will clean up" hand-wave is not
  an acknowledgement — it's a category error specifically because
  the reorderbuffer context is long-lived (survives many xacts),
  not per-statement. So severity here is **blocking**.
- **Suggested ask**: "Trace cleanup on the new ereport path. The
  reorderbuffer's spill BufFile is tied to a FileSet whose
  ResourceOwner is per-decoding-session, not per-ereport. Either
  wrap the open + header-read + ereport in PG_TRY/PG_CATCH that
  calls BufFileClose in the catch handler, or close before the
  ereport." Cite `error-handling` skill for the PG_TRY/PG_CATCH
  pattern.

**Critic A — Architecture & invariants** flags independently:
- The reorderbuffer is a long-lived structure. Resources held on
  its memory context are NOT freed by per-statement context resets.
  Cite knowledge/subsystems/replication-* or knowledge/architecture/
  replication.md if such an INV-* tag exists; otherwise tag the
  finding "no INV cited" and recommend adding one.
- `error-handling` documents the longjmp-out-of-resource-owning-
  function discipline: PG_TRY/PG_CATCH wrap or `resowner`
  registration are the canonical patterns.

**Verdict — REJECT-track or Waiting on Author?**

This is **Waiting on Author**, not REJECT-track. REJECT-A/B/C is
reserved for design-level NACKs (proposes a network-IO immutable
function; requires backwards-incompatible on-disk format with no
upgrade path; flagged by Context-awareness probe). A correctable
lifecycle bug on an otherwise sensible feature isn't REJECT-track.

The skill's threshold (now visible at the end of §Critic E and
echoed at the top of §Stage 3): REJECT-A recommendation needs 3+
**blocking** rows from the severity matrix AND a context-awareness
signal (engagement class `contested` OR a foreclosed `INV-*`). One
escalated-to-blocking finding on a single probe doesn't compose to
that — and Stage 3 may downgrade Critic E's recommendation
regardless.

The review email buckets this under **Blocking issues** with the
specific ask above.

### baseline answer

(unchanged from iter-1)

The patch adds ereport without BufFileClose. This is a resource
leak in an error path. PG_TRY/PG_CATCH or close-before-ereport is
the standard fix. MemoryContext reset frees palloc'd memory but
doesn't close BufFile handles correctly. Severity blocking — real
leak in a long-running process (walsender). Waiting on Author, not
REJECT — patch idea is fine, only error path is wrong. No named
"Critic E / catalog #4" or persona references.

---

## Eval 3 — Tests pass + warning-clean + "pure refactor" — what else?

### with_skill answer

The skill's stages distinguish mechanical-pass-but-still-needs-
review concerns into explicit bins.

**Stage 0 — mechanical pre-amble (DONE per prompt).** Pass.
Stage-0 pass qualifies the patch for stages 1-4; it does NOT make
the patch ready. Skill is explicit: "If stage 0 fails — stop. No
point spending tokens on the critics." The converse is not "tests
pass = good".

**Stage 1 — orchestrator concerns:**
1. **Touched file not in any subsystem doc.** Don't stop; note in
   the review email's "Testing performed" block that the area is
   uncovered by the corpus. File a follow-up to document that
   subsystem.
2. **Corpus drift detected** (spot-check cites stale > 10%). Skill
   escalation (now corrected): ask the user whether to (a) refresh
   the corpus first via a separate `hf(corpus):` commit per Rule R9
   of `.claude/rules/pg-implement-discipline.md`, or (b) proceed
   with a "best-effort against possibly-stale docs" caveat noted in
   the review email's "Testing performed" block. (Previous version
   pointed at the nonexistent `pg-corpus-maintainer` skill.)
3. **The CLAIMS the patch makes.** "Pure refactor, no behavior
   change" → Critic A: every removed line must have an equivalent
   in the replacement. If the diff removes calls to a helper with
   side effects (logging, error reporting, resource tracking) and
   the replacement only captures the "primary" behavior, that's a
   silent regression.

**Stage 2 — five critics, things that pass mechanical but flag
manually:**

- **Critic A (Architecture)**: provenance check — `git -C source
  log -S '<symbol>' --oneline | head -5`. A symbol introduced last
  release with no other callers is a riskier refactor target than
  one stable for years. A refactor that races an in-flight feature
  thread is itself a problem.
- **Critic A**: parallel-query / extension / logical-replication
  interactions. Refactors that change struct initialization can
  break parallel-worker serialization. Existing tests rarely catch
  this.
- **Critic B (Breaking-change)**: on-disk page format change? WAL
  record change? Catalog change with `CATALOG_VERSION_NO` bump?
  Public API / extension ABI? Replication protocol? pg_dump
  impact? **None of these are exercised by regress + iso.**
  `src/include/` changes are extension-visible (inline functions
  and macros count).
- **Critic C (Test coverage)**: For "pure refactor + existing tests
  cover" — find at least one existing test exercising the
  refactored path (`git grep` for the function name in
  `src/test/`). No hit = weak "existing tests cover" claim.
- **Critic D (Style & commit-message)**: Co-Authored-By trailer
  (forbidden upstream); pgindent; commit message imperative + ~76
  col wrap + no emoji.
- **Critic E (Reviewer-reflex probes)** — the new severity matrix
  makes the contract scannable. Eight probes:
  - #4 Cleanup-on-early-return (BufFile / Relation / LWLock / etc).
  - #5 Multibyte/encoding interaction — escalates to **blocking**
    if a text-primitive cap is added with no per-encoding analysis
    (GB18030, EUC_JP, EUC_KR, EUC_CN, EUC_TW). UTF-8 bounds may
    not hold for variable-width legacy encodings.
  - #6 Subsystem-local cap discoverability — new `#define` in
    `contrib/*/*.c` should move to subsystem `.h` if a public-style
    cap.
  - #7 "Third state" cross-check for binary-format changes.
  - #8 `injection_points` reproducer for DoS / scratch-allocation /
    race claims.
  - #9 Hot-path branch-prediction / micro-benchmark — patches in
    `src/backend/utils/adt/*`, `access/{heap,nbtree}/`,
    `optimizer/` adding new guard checks need < 1% overhead
    evidence on the unlikely branch.
  - #10 Symmetric-check refactor — 3+ near-identical added blocks →
    shared inline helper.
  - #11 Persona-aware backpatch routing — top committer for touched
    subsystem with 24mo backpatch rate < 5% → recommend CC'ing a
    higher-backpatch-rate committer from `domain-ownership.md`.

**Stage 3 — verdict considerations beyond "tests pass":**
- **Stage 3 now leads with the Critic-E-recommends-vs-Stage-3-
  decides rule.** Critic E's `recommend_verdict: REJECT-A | REJECT-
  B` is one input; Stage 3 may downgrade if findings don't compose
  to a design-level NACK.
- **REJECT-track conditions** (Phase 0 of `review-checklist`; M4 in
  `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`):
  - design forecloses a documented INV-* invariant
  - Context-awareness probe flagged it (April-1 / joke /
    unimplementable)
  - engagement class is `contested` (named senior contributors with
    unaddressed design objections)
  Tests passing does NOT clear REJECT-track.
- **Phase 0 reviewer-reflex gates (HARD)** — block before any
  mechanical phase even if tests pass:
  - **Gate 1 (`security@` embargo)**: COVER mentions DoS / bomb /
    amplification / overflow / injection / TOCTOU / privilege /
    REVOKE / GRANT AND patch touches public-SQL-API path → ask
    "has `security@` been notified?"
  - **Gate 2 (test-omission skepticism)**: COVER says "no
    regression test, fixture would dominate buildfarm" → push for
    `PG_TEST_EXTRA=stress` per Daniel Gustafsson's online-checksums
    precedent.
  - **Gate 3 (install-script immutability)**: patch modifies a
    shipped `--A--B.sql` for a released version → ship `--B--C.sql`
    instead.

**Stage 4 — synthesizer concerns**:
- Performance-impacting patches: ask for pgbench numbers with
  exact recipe (hardware, build flags, run count, master baseline).
  Numerical claims without a recipe get bounced.
- Blocking vs nit in EVERY review.

**Calibration anchor**: the §Validation reference points at the
2026-06-02 v0 manual review of CF #6402, now marked `[unverified:
session log not preserved in sessions/ at the time of this writing]`
— preserves the intent without claiming a file that doesn't exist.

### baseline answer

(unchanged from iter-1)

If a patch passes regress + iso + ninja install warning-clean, the
COVER says "pure refactor", and I want to be uneasy, I'd look at:
refactor-equivalence (every removed line has an equivalent), test
coverage of the refactored path, src/include/ ABI surface, WAL /
catalog / on-disk changes, parallel-query / extension /
replication interactions, style + commit-message, pgindent,
performance regressions on hot paths, docs, resource cleanup on
new error paths. No named REJECT-A/B/C or Phase 0 gates framework.
