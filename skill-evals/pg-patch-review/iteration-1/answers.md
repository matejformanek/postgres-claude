# Iteration 1 — answers (with_skill vs baseline)

## Eval 1 — Drive a mailing-grade review of CF #5912 end-to-end

### with_skill answer

The skill defines a **five-stage pipeline**. I'll walk it for CF #5912.

**Stage 0 — mechanical pre-amble** (already done per the prompt). The
`/pg-review` slash command would have fetched the patch, applied via
`git am` on `dev/cf5912-review`, run `ninja install`, and recorded
`meson test --no-rebuild regress/regress` and `--suite isolation`
results. Output of Stage 0: list of touched files (`git diff
--name-only`), test result summary, and any pre-existing flake notes
(e.g. macOS `recovery/040_standby_failover_slots_sync`).

**Stage 1 — orchestrator project discovery** (~5 min, single agent,
done once before the fan-out):

1. **Touched files → touched subsystems**: a new LWLock tranche +
   shmem region maps to `knowledge/subsystems/storage-lwlock.md`,
   `knowledge/subsystems/storage-shmem.md`. A new system view + new
   catalog rows map to `knowledge/subsystems/catalog-system-views.md`.
2. **Per-file docs**: look up `knowledge/files/<path>.md` for each
   touched file. If a touched file has no per-file doc, that gets
   flagged in the review email's "Testing performed" block.
3. **Claims that become CHECKs**: from COVER → (a) "backwards-
   compatible — only catalog rows and a new shmem region" → CHECK by
   Critic B; (b) "no WAL changes" → CHECK by Critic B; (c) "refactor
   of LWLockNewTrancheId callers is mechanical" → CHECK by Critic A
   ("every removed line must have an equivalent in the replacement"
   for refactors).
4. **Dispatch block**: assembled with patch ref, branch SHA, touched
   files (with per-file-doc presence/absence flags), touched
   subsystems, verbatim claims, and Stage-0 test summary. Sent to all
   five critics.
5. **Citation drift spot-check**: 3-5 cites from the loaded subsystem
   docs against `source/`. If drift > 10% (cites off by > ~20 lines
   or removed symbols), STOP and tell the user the corpus needs
   `hf(corpus):` refresh before proceeding.

**Stage 2 — five critics in parallel** (single message, parallel tool
calls, ~10-20 min wall time):

- **Critic A — Architecture & invariants.** Loads the LWLock/shmem
  subsystem docs + relevant per-file docs + `review-checklist` Phase
  6. Checks: does the new tranche use `LWLockRegisterTranche` or
  `LWLockNewTrancheId` correctly? Does it follow lock-acquisition
  order in the rest of the system? Does the "mechanical refactor"
  claim hold — every removed line has an equivalent? Provenance: is
  `LWLockNewTrancheId` long-stable or racing an in-flight refactor
  thread (`git -C source log -S 'LWLockNewTrancheId' --oneline | head
  -5`)? Loads sibling skills `locking`, `memory-contexts` if
  relevant.
- **Critic B — Breaking-change scan.** Loads `wal-and-xlog`,
  `catalog-conventions`, the breaking-change bullets of Phase 6.
  Checks: on-disk page format change? No. WAL record change? COVER
  says no — verify the diff doesn't add to `rmgrlist.h` or extend an
  existing WAL info byte. Catalog change? Yes — verify
  `CATALOG_VERSION_NO` is bumped, OIDs assigned, no back-branch
  compatibility issue. Public API / extension ABI? Anything in
  `src/include/` — a new tranche may add inline accessors here. New
  struct members must go at end; no exported-function signature
  changes. Replication protocol / pg_dump? A new pg_stat_* view
  needs pg_dump consideration if dumpable (system views usually
  aren't but verify).
- **Critic C — Test coverage.** Loads `testing` skill + touched
  subsystems' test surface. Checks: does the diff include
  `src/test/`? For a refactor claim, find existing tests exercising
  the LWLock paths (`git grep` for the function names in
  `src/test/`). For the new pg_stat view: are corner cases tested
  (empty result, max-length counters, concurrent stat updates)?
- **Critic D — Style & commit-message.** Loads `commit-message-
  style` + `coding-style` + Phase 5 + Phase 7. Checks: filename
  `vN-NNNN-<title>.patch`. Commit message: imperative title, no
  period, ~76-col wrap, no emoji, NO `Co-Authored-By` (forbidden
  upstream), Author/Reviewed-by trailers, Discussion: link. Code
  style: matches surrounding module. `git diff --check` clean.
  pgindent: noted as CI-caught if not locally runnable.
- **Critic E — Reviewer-reflex probes** (added 2026-06-12 from Phase
  C). Loads `knowledge/calibration/gap-catalog.md` items 4-11 +
  relevant `knowledge/personas/*.md`. Probes that may trigger here:
  catalog #6 (subsystem-local cap discoverability — if the diff adds
  a `#define` for the new tranche or for the stat-row count, should
  it live in the subsystem `.h`?); catalog #10 (symmetric-check
  refactor — if 3+ near-identical LWLock-registration blocks were
  added, recommend a shared helper). Catalog #1-#3 are NOT this
  critic's job; they live in `review-checklist` Phase 0.

Each critic returns structured findings:
```
File: <path:line>
Severity: blocking | warning | suggestion
Invariant: INV-... | "no INV cited"
Description: what and why
Suggestion: proposed fix or question to author
```

**Stage 3 — orchestrator consolidates** (~10 min):
- Deduplicate (two critics may flag the same issue from different
  angles — merge with both rationales).
- Resolve conflicts (if A says "fine" but B says "ABI break", re-read
  both, cite both in the merged finding).
- Bucket: **Blocking** / **Warning** / **Nits/suggestions** / **Open
  questions**.
- **Verdict** — one of: Ready for Committer / Waiting on Author /
  Needs more info / **REJECT-A** (design wrong, all critical issues
  caught, alternative proposed; saves community cycles) / **REJECT-B**
  (design wrong but missed a major concern; send anyway,
  acknowledge gaps) / **REJECT-C** (rejected wrongly — **STOP**,
  escalate to user before posting).

**Stage 4 — synthesize the review email**, using
`commit-message-style` tone rules (imperative, plain text, no HTML,
no emoji, ~76 col wrap). The email at
`sessions/<date>-cf5912-review.md` has: one-line summary →
high-level read with file:line cites → Blocking issues → Warnings →
Nits → Open questions → Testing performed (git am / ninja install /
regress / isolation / patch base) → closing line ("Marking Waiting
on Author pending the items above"). Below the email, in the same
file, appendix: per-critic raw findings + Stage 0 mechanical log +
wall time per stage.

**Knowledge / sibling-skill loads**:
- Subsystem docs: `storage-lwlock.md`, `storage-shmem.md`,
  `catalog-system-views.md`.
- Sibling skills: `review-checklist`, `wal-and-xlog`,
  `catalog-conventions`, `testing`, `coding-style`,
  `commit-message-style`, `locking`, `memory-contexts`.
- Critic-E specific: `knowledge/calibration/gap-catalog.md` items
  4-11 + relevant `knowledge/personas/*.md` (per probe trigger).

**Deliverable**: `sessions/<date>-cf5912-review.md` in this repo
(the review email + per-critic appendix + Stage 0 log + wall time).
Patch branch `dev/cf5912-review` is disposable after the review is
mailed.

### baseline answer

For a mailing-grade review of CF #5912 I'd want to be systematic.

A reasonable pipeline:
1. **Mechanical first**: apply the patch, build, run tests. If apply
   fails, mark Waiting on Author and stop. The prompt says this is
   already done.
2. **Read the COVER claims** and treat each one as something to
   verify against the diff. The three claims here are: backwards-
   compatible, no WAL changes, mechanical refactor.
3. **For each claim, run a targeted check**:
   - "Backwards-compatible" — check `CATALOG_VERSION_NO` bumped, OIDs
     assigned, no on-disk format change, no struct-size changes in
     headers that extensions might use.
   - "No WAL changes" — grep the diff for rmgrlist, XLogRegister,
     XLOG_PAGE_MAGIC.
   - "Mechanical refactor of LWLockNewTrancheId callers" — read the
     diff and verify every removed call has an equivalent replacement.
4. **Test coverage**: does the patch include `src/test/` changes? A
   new system view should be tested with at least basic SQL.
5. **Style**: commit message format (imperative, no Co-Authored-By
   for upstream), pgindent, no debug elog leftover.
6. **Architecture concerns**: lock-acquisition order, interaction
   with parallel query and replication.
7. **Synthesize a review email** to pgsql-hackers: plain text, no
   HTML, blocking vs nit separation, concrete asks, CommitFest flip
   to Waiting on Author or Ready for Committer.

I'd probably run the structured checks one at a time rather than
fanning out — I don't have a named multi-agent setup. I don't have
a named "REJECT-A/B/C" grade in mind; I'd just say Ready or Waiting
on Author. I don't know which `knowledge/` docs to load.

---

## Eval 2 — Adversarial probe: BufFile leak on ereport without BufFileClose

### with_skill answer

This is exactly Critic E's catalog #4 probe.

**Critic E — Cleanup-on-early-return tracing (gap-catalog item #4)**:
- **Trigger**: a new `return` (or `ereport(ERROR, ...)` longjmp) added
  inside a function whose entry block owns a resource handle —
  `z_stream`, `BufFile`, `FileFd`, `MemoryContext`, `Relation`,
  `LWLock`. **The diff opens a `BufFile` via `BufFileCreateFileSet`
  and the new error path does NOT call `BufFileClose` before
  `ereport(ERROR, ...)`.** Trigger fires.
- **Persona driver**: `daniel-gustafsson.md` errorhandling discipline.
- **Severity**: `warning` by default; escalates to `blocking` if the
  COVER doesn't even acknowledge the cleanup question. The author's
  "the MemoryContext on backend reset will clean up" answer is
  *wrong* for `BufFile` specifically — BufFile lifetime is tied to a
  `FileSet` / `SharedFileSet` / `ResourceOwner`, and on `ereport(ERROR)`
  the resource owner cleanup will close the underlying fd but
  `BufFileClose` also does flush / spill-cleanup work that the RO
  callbacks may not exactly replicate. More importantly, the
  ReorderBuffer can be in a long-lived MemoryContext (the
  reorderbuffer's own context survives across many transactions),
  not just the per-tuple context — so "backend reset cleans up" is
  a category error here.
- **Suggested ask to author**: "Please trace cleanup on the new
  ereport path. The reorderbuffer's spill BufFile is tied to a
  FileSet whose ResourceOwner is per-decoding-session, not per-
  ereport — confirm via PG_TRY/PG_CATCH or move the BufFileClose
  before the ereport." Cite: `reorderbuffer.c` BufFile usage and the
  `error-handling` skill's PG_TRY/PG_CATCH pattern.

**Critic A — Architecture & invariants** flags independently:
- The reorderbuffer is a long-lived structure that survives across
  many xacts; resources held on its memory context are NOT freed by
  per-statement context resets. Cite
  `knowledge/subsystems/replication-logical.md` (or
  `knowledge/architecture/replication.md`) if such an INV-* tag
  exists; otherwise tag the finding "no INV cited" and recommend
  adding one.
- For refactors / new error paths in long-lived contexts, the lock-
  order and resource-order discipline is documented in
  `error-handling`: don't longjmp out of a function that owns a
  freshly-opened resource without either PG_TRY/PG_CATCH wrapping or
  a `resowner` registration.

**Verdict — REJECT-track or Waiting on Author?**

This is **Waiting on Author**, NOT REJECT-track. REJECT-A/B/C is
reserved for design-level NACKs where the *idea* of the patch is
wrong — e.g. proposes a network-IO immutable function, requires a
backwards-incompatible on-disk format with no upgrade path, or is
flagged by the Context-awareness probe (April-1 / joke / unimplement-
able). A correctable lifecycle bug on an otherwise sensible feature
is not REJECT-track. Critic E's REJECT-track *escalation* rule
requires 3+ blocking-severity findings from the catalog AND a
context-awareness signal (engagement class `contested` OR a
foreclosed `INV-*` invariant). One BufFile-leak finding by itself
doesn't compose to that.

The review email should bucket this under **Blocking issues** with
the specific ask: "Wrap the BufFileCreateFileSet + header read +
ereport in PG_TRY/PG_CATCH that calls BufFileClose, or close before
ereport. The 'MemoryContext reset cleans up' rationale doesn't hold
for a long-lived reorderbuffer context."

### baseline answer

The patch adds an `ereport(ERROR, ...)` without first calling
`BufFileClose` on a BufFile it just opened. This is a resource leak.

PG uses `ereport(ERROR)` which longjmps to the nearest PG_TRY/PG_CATCH
or to the top-level error handler. If there's no PG_TRY/PG_CATCH
between the BufFile open and the ereport, the BufFile won't be
explicitly closed. The ResourceOwner machinery will free the
underlying file descriptors at transaction-end (or sub-transaction
end), but that's not the same as `BufFileClose` which does additional
work and is what the BufFile API contract expects.

The author's claim "the MemoryContext on backend reset will clean up"
is too vague. MemoryContext reset will free palloc'd memory but
won't necessarily close file handles tied to BufFile or run cleanup
callbacks correctly.

Severity: I'd call this **blocking** — a real resource leak in an
error path in a long-running process (logical decoding via walsender).

Suggested fix: wrap the open + read in `PG_TRY` / `PG_CATCH` with
`BufFileClose` in the catch handler, or close before the ereport.

For Waiting on Author vs REJECT: this is Waiting on Author. The
patch's *idea* is fine, only the error path is wrong.

I don't have a named "Critic E / catalog #4" or persona references
here — I'm just doing PG code review intuition.

---

## Eval 3 — Patch passes regress + iso + warning-clean. What else should make me uneasy?

### with_skill answer

The skill's stages distinguish mechanical-pass-but-still-needs-
review concerns into several explicit bins. Going through them:

**Stage 0 — mechanical pre-amble (DONE per prompt).** Pass. But the
stage-0 result does NOT make the patch ready — it just qualifies it
for stages 1-4. The skill is explicit: "If stage 0 fails — stop. No
point spending tokens on the critics." The converse is *not* "if
stage 0 passes the patch is good"; only "the patch is worth deeper
review."

**Stage 1 — orchestrator project discovery concerns:**
1. **Touched file not in any subsystem doc.** The skill calls this
   out explicitly: don't stop; note in the review email's "Testing
   performed" block that the touched area is uncovered by the corpus.
   File a follow-up to document that subsystem. *This is a process
   uneasiness*: you can't actually critique a patch against
   invariants that haven't been written down.
2. **Corpus drift detected** (spot-check cites stale > 10%). Skill's
   explicit escalation: "stop, ask whether to refresh the corpus
   first via `pg-corpus-maintainer` or to proceed with a 'best-effort
   against possibly-stale docs' caveat."
3. **The CLAIMS the patch makes**. For "pure refactor, no behavior
   change": Critic A's verification rule is "every removed line must
   have an equivalent in the replacement." If the diff removes calls
   to a helper that has side effects (logging, error reporting,
   resource tracking) and the replacement only captures the
   "primary" behavior, that's a silent regression. *Pure refactor*
   claims need line-by-line equivalence.

**Stage 2 — five critics, things that pass mechanical but flag
manually:**

- **Critic A (Architecture)**: provenance check — `git -C source log
  -S '<symbol>' --oneline | head -5`. A symbol introduced last
  release with no other callers is a riskier refactor target than
  one that's existed for years. *A "refactor" that races an in-
  flight feature thread is itself a problem.*
- **Critic A**: "Does the patch interact with parallel query /
  extensions / logical replication in any way the corpus warns
  about?" Refactors that change how a struct is initialized can
  break a parallel worker's serialization of that struct. Existing
  tests rarely catch this.
- **Critic B (Breaking-change scan)**: On-disk page format change?
  WAL record change? Catalog change with CATALOG_VERSION_NO bump?
  Public API / extension ABI? Replication protocol? pg_dump impact?
  *None of these are exercised by regress + iso.* Especially
  `src/include/` changes — inline functions and macros there are
  extension-visible ABI and pgindent/regress won't catch it.
- **Critic C (Test coverage)**: For "pure refactor + existing tests
  cover" — find at least one existing test that exercises the
  refactored code path (`git grep` for the function name in
  `src/test/`). If no existing test exists, the "existing tests
  cover" claim is *weak* and the patch should add one. Also: the
  classic "new test passes both with and without the code change" —
  for behavior changes (this is a refactor so non-applicable), but
  for refactors the failure mode is the inverse: existing tests
  pass against the refactor *because they never exercised the line
  that changed*.
- **Critic D (Style & commit-message)**: `Co-Authored-By` trailer
  (forbidden upstream); pgindent (CI catches but committer-readiness
  prefers it locally clean); commit message imperative + ~76 col
  wrap + no emoji.
- **Critic E (Reviewer-reflex probes)**:
  - Catalog #4 cleanup-on-early-return — does the refactor add a new
    `return` inside a function that owns `z_stream` / `BufFile` /
    `FileFd` / `MemoryContext` / `Relation` / `LWLock`?
  - Catalog #5 multibyte/encoding — does the diff add or change byte-
    walking loops over `varlena`/`text`/`cstring`? UTF-8-specific
    bounds may not hold for GB18030, EUC_JP, EUC_KR, EUC_CN, EUC_TW.
    Escalates to **blocking** if a text-primitive cap is added with
    no per-encoding analysis in COVER.
  - Catalog #6 subsystem-local cap discoverability — new `#define` in
    `contrib/*/*.c` (not header) → move to subsystem `.h` if a
    public-style cap.
  - Catalog #7 "third state" cross-check for binary-format changes —
    flag/version/layout bits.
  - Catalog #8 `injection_points` reproducer for DoS / scratch-
    allocation / race claims.
  - Catalog #9 hot-path branch-prediction / micro-benchmark — patches
    in `src/backend/utils/adt/*`, `access/{heap,nbtree}/`,
    `optimizer/` adding new guard checks need micro-benchmark
    evidence the guard is unlikely-branch + < 1% overhead.
  - Catalog #10 symmetric-check refactor — 3+ near-identical added
    blocks → shared inline helper.
  - Catalog #11 persona-aware backpatch routing — COVER claims
    back-patching AND top committer for touched subsystem has 24mo
    backpatch rate < 5% → recommend CC'ing a higher-backpatch-rate
    committer from `domain-ownership.md`.

**Stage 3 — verdict considerations beyond "tests pass":**
- **REJECT-track conditions** (Phase 0 of `review-checklist`; M4 in
  `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`):
  design forecloses a documented INV-* invariant; Context-awareness
  probe flagged it (April-1 / joke / unimplementable); engagement
  classification is `contested` (named senior contributors raising
  unaddressed design objections). Tests passing does NOT clear
  REJECT-track.
- **Phase 0 reviewer-reflex gates (HARD)** — these block before any
  mechanical phase even if tests pass:
  - **Gate 1 (`security@` embargo)**: if COVER mentions DoS /
    decompression bomb / amplification / integer overflow / buffer
    overflow / injection / TOCTOU / privilege / REVOKE / GRANT AND
    patch touches a public-SQL-API path → ask "has `security@` been
    notified?"
  - **Gate 2 (test-omission skepticism)**: if COVER says "no
    regression test, fixture would dominate buildfarm" → push for
    `PG_TEST_EXTRA=stress` per Daniel Gustafsson's online-checksums
    precedent.
  - **Gate 3 (install-script immutability)**: if the patch modifies
    a `contrib/*/*--A--B.sql` for an already-released `A→B` version →
    flag (shipped install-scripts are immutable post-release; ship
    `--B--C.sql` instead).

**Stage 4 — synthesizer concerns**:
- For performance-impacting patches: ask for pgbench numbers with
  exact recipe (hardware, build flags, run count, master baseline).
  Numerical claims without a recipe get bounced.
- Distinguish blocking from nits in EVERY review.

**Calibration anchor**: the 2026-06-02 v0 review of CF #6402 at
`sessions/2026-06-02-cf6402-review-validation.md` is the
calibration target — re-running pg-patch-review against that patch
should reproduce a comparable review in less wall time.

### baseline answer

If a patch passes regress + isolation + ninja install warning-clean,
the COVER says "pure refactor", and I want to be uneasy beyond that,
I'd look at:

1. **Is the refactor really equivalent?** Read the diff line by
   line: every removed line should have an equivalent. Side effects
   (logging, error reporting, resource tracking) are easy to drop
   silently.
2. **Test coverage of the refactored path**: regress passing only
   matters if some test actually exercises the refactored code.
   `git grep` for the function name under `src/test/` — if nothing
   matches, "existing tests cover" is hollow.
3. **ABI / extension impact**: changes in `src/include/` are
   extension-visible. New struct members must go at end, no
   exported-function signature changes. Inline functions and macros
   in headers are also ABI.
4. **WAL / on-disk / catalog changes**: even if "no behavior
   change", a refactor that touches WAL record construction or
   catalog initialization can still bump CATALOG_VERSION_NO or
   require XLOG_PAGE_MAGIC.
5. **Parallel-query / extension / replication interactions**: a
   refactor that moves a field initialization can break serialization
   of parallel-worker state.
6. **Style / commit-message**: imperative title, no period, no
   Co-Authored-By, ~76 col wrap, Author/Reviewed-by trailers,
   Discussion: link.
7. **pgindent**: regress doesn't check this. CI does.
8. **Performance regressions**: a "pure refactor" can slow a hot
   loop by a few percent. For hot-path code, pgbench numbers should
   accompany the patch.
9. **Documentation**: any doc updates needed? Pure refactors usually
   don't need them but always worth checking.
10. **Resource cleanup on error paths**: if the refactor adds a new
    `ereport(ERROR, ...)` inside a function that owns a `BufFile` /
    `Relation` / `LWLock`, trace cleanup.

I don't have a named "REJECT-A/B/C" rubric or "Phase 0 gates"
framework. I'd just bucket findings as blocking / nit / open
question.
