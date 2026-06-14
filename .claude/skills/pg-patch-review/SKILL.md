---
name: pg-patch-review
description: Multi-agent comprehensive review of a PostgreSQL patch — CommitFest entry, GitHub PR, or local `.patch` file. Orchestrates the mechanical pre-amble (fetch + apply + build + regress/iso/TAP) and then fans out 5 critic sub-agents IN PARALLEL — architecture/invariants critic (cross-checks the patch against `knowledge/subsystems/*.md` INV-* tags), breaking-change critic (on-disk + WAL + catalog + extension ABI), test-coverage critic (consults `testing` skill), style/commit-message critic (consults `commit-message-style` + `coding-style`), reviewer-reflex probes critic (consults `knowledge/calibration/gap-catalog.md`) — then synthesizes one PG-house-style review email. Stage 3 verdict supports REJECT-A/B/C grades for design-level rejections (M4 from Phase E run 1). Heavier than the manual seven-phase `review-checklist` walk; meant for CF entries you intend to send a real review on. Use when the user says "/pg-review <CF#|PR#|patchfile>", "deep-review this patch", "comprehensive review of CF NNNN". Do NOT trigger for non-PG patch review, for self-review-before-mail (use `patch-submission`), or for the lightweight 7-phase walk (use `review-checklist` directly).
when_to_load: Mailing-grade review of someone else's CF patch / GitHub PR / `.patch` file; 5-critic fan-out with synthesis; verdict includes REJECT-A/B/C for design-level NACKs.
companion_skills:
  - review-checklist
  - patch-submission
  - commit-message-style
  - coding-style
  - testing
  - wal-and-xlog
  - locking
  - catalog-conventions
  - memory-contexts
  - error-handling
---

# pg-patch-review — multi-agent comprehensive PG patch review

The deep-review counterpart to the manual seven-phase `review-checklist`.
The cf6402 validation run on 2026-06-02 proved the corpus + skills compose
for a one-author review; this skill turns that loop into a repeatable
multi-agent pipeline.

## When to use this skill vs `review-checklist`

| Situation | Use |
|---|---|
| CF entry you intend to mail a real review on | **this skill** |
| Quick "is this even sane?" pass on a patch | `review-checklist` (manual seven-phase) |
| Self-review of your own patch before mailing | `patch-submission` (which already invokes `review-checklist`) |
| Generic non-PG GitHub PR review | neither — this is PG-specific |

The two are NOT redundant: `review-checklist` is the seven-phase scaffold
each critic agent applies inside its assigned slice. This skill is the
**orchestration layer** above that scaffold (project discovery + parallel
critic fan-out + synthesis).

## Companion skills (each critic loads what it needs)

- `review-checklist` — seven-phase scaffold each critic walks inside its slice
- `wal-and-xlog` — WAL records / redo / hint bits (used by breaking-change critic)
- `locking` — lock primitive choice + acquisition order (architecture critic)
- `catalog-conventions` — `pg_proc` / OID assignment (breaking-change critic)
- `testing` — regress vs isolation vs TAP vs module (test-coverage critic)
- `coding-style` — pgindent / include order / C99 subset (style critic)
- `commit-message-style` — upstream PG commit-message style (style critic, AND used by synthesizer for review-email tone)
- `memory-contexts` — palloc placement / context lifetimes (architecture critic when relevant)
- `error-handling` — `ereport` / SQLSTATE choices (style critic when relevant)

## Inputs

- **A patch reference** (required), one of:
  - CF number: `6402`, `#6402`, or `CF 6402`
  - GitHub PR number on `postgres/postgres`: `pr 19234` or `#19234`
  - A local `.patch` file or directory of patches: `/tmp/v3-0001-foo.patch`
- **Optional flags** (from the slash command):
  - `--skip-build` — patch already applied + built in dev/, skip Phase 0
  - `--no-flaky-isolation` — skip the isolation suite (macOS sometimes flakes)
  - `--subsystem=<name>` — hint for which `knowledge/subsystems/*.md` to load
    first (e.g. `--subsystem=access-nbtree` for CF #6402)

## Output

- A draft review email at `sessions/<date>-cf<N>-review.md` (or
  `sessions/<date>-pr<N>-review.md`) using the PG-hackers house style.
- A per-critic appendix at the bottom of the same file with the raw
  findings each sub-agent produced (blocking / warning / suggestion).
- A run log appended to that session file: which patches applied, which
  tests ran, which subsystem docs the critics consulted, wall time.
- A `dev/` branch named `cf<N>-review` (or `pr<N>-review`) with the patch
  applied — disposable after the review is sent.

## When NOT to invoke

- Patch already merged upstream — use `git log` + corpus walkthrough instead.
- Patch is your own work — use `patch-submission` (it invokes the same critics
  but on the self-review path).
- Patch is non-PG — wrong skill.

## Method — five stages

### Stage 0 — mechanical pre-amble (5-10 min)

Done by the `/pg-review` slash command. If invoked directly (without
`/pg-review`), this skill does it inline before stage 1. See
`.claude/commands/pg-review.md` for the exact recipe. The output of
this stage is:

- `dev/` on branch `cf<N>-review` (or `pr<N>-review`) with the patch applied.
- A built binary (`ninja install` clean, no new warnings).
- `meson test --no-rebuild regress/regress` result (pass/fail per test).
- `meson test --no-rebuild --suite isolation` result.
- A list of files the patch touches (`git diff --name-only HEAD~N..HEAD`).
- A note on any pre-existing flakes (e.g. macOS
  `recovery/040_standby_failover_slots_sync`).

If stage 0 fails (patch doesn't apply, build breaks, regress fails) —
**stop**. Report to the user. The patch is `Waiting on Author`
mechanically; no point spending tokens on the critics.

### Stage 1 — project discovery (orchestrator, ~5 min)

The main agent does this **once** before fanning out:

1. **Touched files → touched subsystems.** From the file list in stage 0,
   map each file to its `knowledge/subsystems/<name>.md` parent. Example:
   `src/backend/access/nbtree/nbtpage.c` → `knowledge/subsystems/access-nbtree.md`.
   Use the §2 "File map" section of each subsystem doc to confirm. If a
   touched file doesn't appear in any subsystem doc, NOTE THAT — the
   review must call out that an uncovered area was changed.

2. **Load per-file docs.** For each touched file, look up
   `knowledge/files/<path>.md` if present. These have INV-* invariants
   and per-function cites the critics will rely on.

3. **Identify the "claims" the patch makes.** Read the patch's commit
   message + cover letter (or the CF/PR description). Each claim that
   says "fixes X", "implements Y", "no behavior change", "doesn't touch
   on-disk format", "is purely a refactor" becomes a CHECK item the
   critics will validate.

4. **Build the dispatch block.** Produce a small reference block that
   every critic sub-agent receives in its prompt:

   ```
   Patch: <CF#|PR#|path>
   Branch: dev/cf<N>-review @ <short-sha>
   Files touched:
     - src/.../X.c (per-file doc: knowledge/files/.../X.c.md)
     - src/.../Y.h (no per-file doc — flag if material)
   Subsystems touched:
     - access-nbtree (knowledge/subsystems/access-nbtree.md)
     - storage-buffer (knowledge/subsystems/storage-buffer.md)
   Claims the patch makes (verbatim from commit msg):
     - "Replace duplicated metapage sanity checks..."
     - "No behavior change."
     - "Restores symmetry with _bt_getroot..."
   Stage-0 test result: regress 245/245 pass, iso 129/129 pass,
     1 unrelated TAP failure recovery/040_* (macOS flake)
   ```

5. **Spot-check 3-5 file:line cites** in the relevant subsystem doc
   against current `source/` — if drift > 10% (cites stale by more
   than ~20 lines or naming since-removed symbols), STOP and tell the
   user the corpus needs an `hf(corpus):` refresh before this review.

### Stage 2 — fan out 5 critic sub-agents IN PARALLEL

Launch **all five** (A-E; Critic E added 2026-06-12 from Phase C) in
a single message with parallel tool calls. Each gets the dispatch
block from stage 1 + its assigned slice. Each is read-only —
sub-agents do NOT edit files or commit. Each returns a structured
finding list.

Use the `Agent` tool with `subagent_type: "general-purpose"` for each.
Estimate ~10-20 min wall time for all five to complete (in parallel).

#### Critic A — Architecture & invariants

**Scope:** does the patch fit the subsystem's existing invariants?

**Loads:** `knowledge/subsystems/<each touched subsystem>.md` + relevant
per-file docs + `review-checklist` Phase 6 (Architecture).

**Checks:**
- Does the patch violate any INV-* invariant tagged in the subsystem
  doc? Cite the tag.
- Does the patch's locking match the subsystem's lock-order discipline?
  (E.g. for nbtree: buffer locks coupled in left-to-right order; for
  heap: buffer-pin-before-buffer-lock; for replication: never hold
  ProcArrayLock across...)
- Does the patch interact with parallel query / extensions / logical
  replication in any way the corpus warns about?
- Does the patch's claim of "no behavior change" hold up under
  inspection? (For refactors: every removed line must have an
  equivalent in the replacement.)
- **Provenance check** for any helper/struct the patch touches: run
  `git -C source log -S '<symbol>' --oneline | head -5` to find when
  the symbol was introduced. A symbol that's existed for years +
  has multiple existing callers is a safer refactor target than a
  symbol introduced last release. Surfaces both "this is a long-
  overdue cleanup" and "this is racing an in-flight feature".

**Output:** structured findings list. Each item:
```
File: <path:line>
Severity: blocking | warning | suggestion
Invariant: INV-... (if applicable) or "no INV cited"
Description: what and why
Suggestion: proposed fix or question to the author
```

#### Critic B — Breaking-change scan

**Scope:** does the patch touch anything backwards-incompatible?

**Loads:** `wal-and-xlog`, `catalog-conventions`, `review-checklist`
Phase 6 (Architecture — the ABI bullets), and the subsystem docs'
§5 "Invariants and breaking-change surfaces" sections.

**Checks:**
- On-disk page format change? (`pd_*` fields, opaque-area layout.)
- WAL record change? (New record, new info byte, existing record
  extended.) If yes, is `XLOG_PAGE_MAGIC` bumped?
- Catalog change? (`pg_proc.dat`, `pg_type.dat`, etc.) If yes, is
  `CATALOG_VERSION_NO` bumped? Are new OIDs assigned?
- Public API / extension ABI? (Anything in `src/include/`.) Inline
  functions / macros there count. If touching back-branchable code:
  new struct members must go at the end; no signature changes on
  exported functions.
- Replication protocol change? (`libpq` wire format, walsender output
  plugins, logical decoding output formats.)
- pg_dump impact? (Any new schema object.)

**Output:** same structured list. For each blocking break, name the
upgrade/backpatch story the author needs to provide.

#### Critic C — Test coverage

**Scope:** is the patch tested adequately for what it claims?

**Loads:** `testing` skill + the touched subsystems' "test surface"
sections + `src/test/` for the existing coverage of the touched code.

**Checks:**
- Does the diff include `src/test/` changes? If not, is the claim "pure
  refactor, no new behavior, existing tests cover" defensible?
- For a refactor: does at least one existing test exercise the code
  path being refactored? (Find by `git grep` for the function name in
  `src/test/`.) If not, the "existing tests cover" claim is weak.
- For new behavior: does the new test ACTUALLY fail without the code
  change? (The classic "test passes both with and without the patch"
  bug.) Sub-agent can't easily verify this without re-running tests
  twice — instead it flags this as a question for the author or for
  manual follow-up.
- Corner cases: NULL, empty input, max-length, encoding edges,
  concurrent calls, parallel-worker visibility, replication catchup.
  Sub-agent enumerates which apply to this patch's surface.
- Isolation tests needed? Concurrent-modification scenarios?
- TAP tests needed? Multi-node, recovery, replication, crash-recovery
  scenarios?

**Output:** same structured list. The "blocking" bar here is whether
the patch's correctness claim is mechanically testable from what's in
the diff.

#### Critic D — Style & commit-message

**Scope:** would a committer have to fix the format before applying?

**Loads:** `commit-message-style` + `coding-style` + `review-checklist`
Phase 5 (Coding review) + Phase 7 (Committer-readiness).

**Checks:**
- Patch filename: `vN-NNNN-<title>.patch`?
- Commit message: imperative title, no period, ~76-col wrap, no emoji,
  no `Co-Authored-By` (forbidden upstream), Author/Reviewed-by trailers
  if relevant, Discussion: link if relevant.
- Code style: matches surrounding module (camelCase vs snake_case),
  no leftover debug `elog`, no commented-out code, no new compiler
  warnings flagged in stage 0.
- Error messages follow the message style guide (capitalization,
  no period on `errmsg`, separated `errdetail`/`errhint`).
- `git diff --check` clean? (Trailing whitespace, broken tab/space mix.)
- `pgindent` clean? (May not be runnable locally — note `pg_bsd_indent`
  install state; CI will catch.)

**Output:** same structured list. Most items here are `suggestion` or
`warning`; only fundamentally broken style is `blocking`.

#### Critic E — Reviewer-reflex probes (added 2026-06-12 from Phase C)

**Scope:** does the patch trigger any of the persona-driven reflexes
the corpus has documented but the generic critics A-D don't encode?

**Loads:** `knowledge/calibration/gap-catalog.md` (the 11-item
catalog) + `knowledge/personas/<name>.md` for each persona named in
items 4-11 that triggers + `knowledge/personas/committer-map.md` +
`knowledge/personas/domain-ownership.md` (item 11 cross-reference).

**Checks (each maps 1:1 to a catalog item):**

- **Cleanup-on-early-return tracing (catalog #4).** Scan the diff for
  a new `return` statement added inside a function whose entry block
  owns a resource handle (`z_stream`, `BufFile`, `FileFd`,
  `MemoryContext`, `Relation`, `LWLock`). If found, surface "trace
  cleanup path under the new error return — does
  `<resource>_destroy()` / `_close()` / `_release()` run on this
  branch?". Driver: `daniel-gustafsson.md` errorhandling discipline.

- **Multibyte/encoding interaction (catalog #5).** Scan the diff for
  byte-walking patterns (`*p++`, `*input++`, manual `for` loops over
  `varlena`/`text`/`cstring`) OR size caps on text-processing
  primitives. If found, surface "enumerate worst-case per encoding
  (UTF-8 documented, GB18030, EUC_JP, EUC_KR, EUC_CN, EUC_TW); cite
  the Unicode TR / SpecialCasing.txt entry for any UTF-8-specific
  bound". Driver: `noah-misch.md` §4 + `jeff-davis.md` Unicode
  standard fidelity.

- **Subsystem-local cap discoverability (catalog #6).** Scan the
  diff for a new `#define` in a `contrib/*/*.c` file (not header).
  If found, surface "move to `<subsystem>.h` if a public-style cap;
  cite the precedent constant in the same area (e.g.
  `LQUERY_MAX_LEVELS` for `ltree_io.c`)". Driver:
  `peter-eisentraut.md` style reflex.

- **"Third state" cross-check for binary-format changes (catalog
  #7).** Scan the diff for changes in how a flag-bit, version-bit,
  or layout-bit is interpreted. If found, surface "enumerate the
  third state: bit set but structure invalid, OR bit unset but
  structure looks valid — what handles each?". Driver:
  `heikki-linnakangas.md` binary-format reflex.

- **`injection_points` reproducer for DoS / scratch-allocation /
  race claims (catalog #8).** Scan the commit-message + COVER for
  phrases like "prevents N MB scratch", "N GB allocation", "fixes a
  race", "OOB read", "amplification". If found AND the patch has
  no `src/test/modules/injection_points/` change, surface "include
  an `injection_points` measurement at the allocation /
  race-windowed boundary; the structural argument is not enough on
  a security claim". Driver: `noah-misch.md` §5.

- **Hot-path branch-prediction / micro-benchmark (catalog #9).**
  When the patch touches a function in `src/backend/utils/adt/*`,
  `src/backend/access/{heap,nbtree}/`, `src/backend/optimizer/`, or
  similar query-evaluator path AND adds a new guard check, surface
  "include micro-benchmark numbers confirming the guard is in the
  unlikely branch and adds <1% overhead on typical inputs". Driver:
  `thomas-munro.md` + `heikki-linnakangas.md` performance reflex on
  hot paths.

- **Symmetric-check refactor for N-entry-point guards (catalog
  #10).** Diff scan for 3+ near-identical added blocks (heuristic:
  same `if`/`ereport`/`ereturn` pattern at 3+ places). If found,
  surface "consider a shared inline helper `<module>_check_<thing>()`
  to keep entry points symmetric". Driver: `peter-eisentraut.md`
  symmetric-primitives reflex.

- **Persona-aware backpatch routing (catalog #11).** When COVER
  claims back-patching AND the predicted top committer for the
  touched subsystem (from `domain-ownership.md` top-committer
  column) has a 24mo backpatch rate < 5% (compute from
  `committer-map.md` or `/usr/bin/git log --author=<name> --since=
  '2yr' --pretty=%s | grep -ciE 'back.?patch'` ratio), surface "X
  doesn't backpatch in 24mo; the realistic v16/v17/v18 landing
  committer is Y (from `domain-ownership.md` reviewer column — pick
  the highest-ranked committer who backpatches at ≥10%). CC them
  on the thread.". Driver: Peter Eisentraut row in
  `committer-map.md`.

**Severity rules for Critic E:**

- Catalog #1-#3 are NOT this critic's job — they live in
  `review-checklist` Phase 0 (gates that block before the patch
  enters the critic fan-out).
- Catalog #4, #5, #7, #8 are `warning` (sometimes `blocking` if the
  COVER doesn't even acknowledge the question).
- Catalog #6, #9, #10, #11 are `suggestion` by default — they
  improve the patch but don't block.
- Catalog #5 escalates to `blocking` if the patch caps a text
  primitive AND no per-encoding analysis is in the COVER — that's
  a real correctness gap (e.g. SP2 had this; the 3× UTF-8 bound
  may not hold for GB18030).

**REJECT-track escalation (M4).** When Critic E surfaces 3+
`blocking`-severity findings from the catalog AND the
context-awareness signal (engagement class `contested` OR a
documented `INV-*` invariant is foreclosed), the critic's output
should explicitly recommend a `REJECT-A` Stage-3 verdict rather than
"Waiting on Author". The Stage-3 orchestrator then decides between
REJECT-A (the grade above), REJECT-B (acknowledge that the critic
may have missed a concern), or downgrade to non-REJECT if the
findings don't actually compose to a design-level NACK. Critic E
*recommends*; Stage 3 *decides*.

**Output:** same structured-finding list as critics A-D, plus an
optional `recommend_verdict: REJECT-A | REJECT-B` field when the
escalation rule above triggers.

### Stage 3 — orchestrator consolidates (10 min)

The main agent gathers all four critics' outputs and:

1. **Deduplicates.** Two critics may flag the same issue from different
   angles — merge into one finding with both rationales.
2. **Resolves conflicts.** If critic A says "this is fine" but critic B
   says "this breaks ABI", the orchestrator re-reads both and picks the
   stronger argument. Cite both in the merged finding.
3. **Severity prioritization.** Group findings into:
   - **Blocking** (must fix before commit; flip CF to "Waiting on Author")
   - **Warning** (should fix or justify)
   - **Nits / suggestions** (take or leave)
   - **Open questions** (need author input)
4. **Verdict.** Decide one of:
   - Ready for Committer
   - Waiting on Author (blocking issues)
   - Needs more info from author (open questions dominate)
   - **REJECT-A** — design fundamentally wrong, all critical problems
     identified, alternative proposed. The right deliverable is a
     thread reply explaining the rejection with cites; saves community
     cycles. Use this when the patch is in `contested` engagement
     class or the Context-awareness probe (from
     `pg-feature-plan`) flagged it.
   - **REJECT-B** — design wrong, but you missed at least one major
     concern that a critic from the community will raise. Solid but
     incomplete; send the reply, acknowledge gaps.
   - **REJECT-C** — rejected for the wrong reasons OR rejected when
     the proposal is actually sound. **STOP** — escalate to user
     before posting. Likely you need to re-run with looser
     priors or load more corpus.

   M4 origin:
   `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`.
   The REJECT-A/B/C grades parallel the A-F grade rubric on
   non-REJECT outcomes — they're not lesser verdicts, just the right
   shape for proposals that shouldn't proceed.

### Stage 4 — synthesize the review email

**Use the `commit-message-style` skill's tone rules** — imperative,
plain text, no HTML, no emoji, ~76 col wrap. The review email lives at
`sessions/<date>-cf<N>-review.md` (or pr<N>) and has this shape:

```
To: pgsql-hackers@lists.postgresql.org
Cc: <author> <author@email>
Subject: Re: [PATCH v<N>] <patch subject>

<one-line summary of where the patch stands>

<one or two paragraphs of the high-level read — what the patch does, why
the corpus thinks it's coherent (or not). Cite specific anchors where
relevant: nbtpage.c:407, knowledge/subsystems/access-nbtree.md §4.>

Blocking issues:
  1. <one-line summary>
     <2-4 lines of context + concrete ask>
  2. ...

Warnings / consider:
  1. ...

Nits, take or leave:
  1. ...

Open questions:
  1. ...

Testing performed:
  - git am: <clean | rejected hunk in X>
  - ninja install: <clean | warnings: ...>
  - meson test regress/regress: <NNN subtests, all pass | failed: ...>
  - meson test --suite isolation: <NNN subtests, all pass | failed: ...>
  - Patch base: <upstream-master short-sha>

<closing line: "I think this is ready for a committer" / "Marking
Waiting on Author pending the items above" / etc.>

Regards,
[Reviewer]
```

Below the email in the SAME session file, append:

```
---

## Per-critic raw findings

### Critic A — Architecture & invariants
<paste the sub-agent's structured list>

### Critic B — Breaking-change scan
<paste>

### Critic C — Test coverage
<paste>

### Critic D — Style & commit-message
<paste>

## Stage 0 mechanical log
- Patch source: <URL or path>
- Base ref: <upstream-master sha>
- Apply: <git am output summary>
- Build: <ninja install summary>
- regress: <pass/fail counts + duration>
- isolation: <pass/fail counts + duration>
- Targeted suites: <if any>
- Pre-existing flakes encountered: <list, with dismissal rationale>

## Wall time
- Stage 0: <min>
- Stage 1: <min>
- Stage 2 (4 critics in parallel): <max of the four, plus orchestration overhead>
- Stage 3: <min>
- Stage 4: <min>
- Total: <min>
```

## Boundaries vs other skills

- **`review-checklist`** (the eight-phase scaffold — Phase 0 added
  2026-06-12 for reviewer-reflex gates): each critic walks the
  relevant phase of it. This skill orchestrates five critics doing
  that in parallel (A-E; E added 2026-06-12 from Phase C) and
  synthesizes. Don't bypass `review-checklist`'s phase definitions —
  extend them.
- **`patch-submission`**: the self-review counterpart. If you're
  reviewing YOUR OWN patch before mailing, use that — it invokes the
  same critics but on the pre-submission path.
- **`commit-message-style`** (upstream PG): used by the synthesizer for
  the review-email tone AND by critic D for judging the patch's commit
  message.
- **`meta-commit-style`** (postgres-claude): does NOT apply to the
  review email (which goes to pgsql-hackers, not into postgres-claude).
  It WOULD apply to the session-log commit (if any) and to the
  STATE.md update.

## What to escalate to the user mid-review

- **Stage-0 fail** (patch doesn't apply, build breaks, regress fails):
  stop, report, ask whether to send a "rebase needed" reply or to skip.
- **Corpus drift** detected in stage 1 (cites stale > 10%): stop, ask
  whether to refresh the corpus first via `pg-corpus-maintainer` or to
  proceed with a "best-effort against possibly-stale docs" caveat.
- **Touched file not in any subsystem doc**: don't stop; note in the
  review email's "Testing performed" block that this area is
  uncovered by the corpus. After the review, file a followup to
  document that subsystem.
- **Two critics genuinely disagree** after orchestrator consolidation:
  ask the user to break the tie before drafting the email.

## Style notes

- The review email is the deliverable; everything else is working notes.
  Make the email scannable — bullets, no walls of prose.
- Cite specific file:line anchors in the email when relevant. The
  validation run proved this is what makes a review feel grounded vs
  generic.
- Distinguish blocking from nits in EVERY review. "Needs more tests" is
  not blocking unless the patch's correctness claim depends on the
  missing test.
- For performance-impacting patches: ask for pgbench numbers with
  exact recipe (hardware, build flags, run count, master baseline).
  Numerical claims without a recipe get bounced.
- If invoking via the `/pg-review` slash command, the command already
  did stage 0 — skip ahead to stage 1.

## Where the artifacts live

- Review email + appendices: `sessions/<date>-cf<N>-review.md` in
  `postgres-claude/` (this repo).
- Patch branch: `dev/cf<N>-review` (the mutable PG clone). Disposable
  after review is sent.
- No `knowledge/` writes by this skill — if the review surfaces a
  corpus gap, file a follow-up `hf(corpus):` commit separately (per
  R10 of `.claude/rules/pg-implement-discipline.md`).

## Validation reference

The 2026-06-02 v0 review of CF #6402 in
`sessions/2026-06-02-cf6402-review-validation.md` is the calibration
target — re-running THIS skill against that patch should reproduce a
review of comparable quality (same draft conclusion, same blocking-vs-nit
split) in less wall time than the v0 manual walk.

## Cross-references

- `.claude/skills/review-checklist/SKILL.md` — the eight-phase scaffold each critic walks; Phase 0 hosts the REJECT-A/B/C grade rubric this skill's Stage 3 verdict consumes.
- `.claude/skills/patch-submission/SKILL.md` — invokes this skill in `--self` mode for the self-review path.
- `.claude/skills/pg-feature-plan/SKILL.md` — supplies the Context-awareness probe + Thread-engagement classification that drive Critic E's REJECT-track escalation.
- `.claude/skills/commit-message-style/SKILL.md` — Critic D + synthesizer use this for upstream PG commit-message format.
- `.claude/skills/coding-style/SKILL.md` — Critic D style check.
- `.claude/skills/testing/SKILL.md` — Critic C test-coverage check.
- `.claude/skills/wal-and-xlog/SKILL.md`, `.claude/skills/catalog-conventions/SKILL.md` — Critic B breaking-change scan.
- `.claude/skills/locking/SKILL.md`, `.claude/skills/memory-contexts/SKILL.md`, `.claude/skills/error-handling/SKILL.md` — Critic A architecture check.
- `knowledge/calibration/gap-catalog.md` — items 4-11 source Critic E's eight reflex probes.
- `knowledge/personas/*.md` — Critic E loads relevant persona docs per probe.
- `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md` — M4 origin (REJECT-A/B/C verdict).
- `.claude/commands/pg-review.md` — slash-command wrapper that runs Stage 0 inline.
