---
scenario: fix-memory-leak
when_to_use: I want to fix a memory leak in a PG backend code path — either a known upstream report, a leak commit in git log I want to validate the methodology against, or a leak my own harness surfaced.
companion_skills: ["pg-feature-brainstorm", "pg-feature-plan", "pg-implement", "memory-contexts", "debugging", "build-and-run"]
related_scenarios: ["add-new-test-module"]
canonical_commit: 5a2043bf713
last_verified_commit: e18b0cb7344
---

# Scenario — Fix a memory leak in a backend code path

## Scope — what's in / out

**In scope:**
- Transient leaks inside a single backend function (palloc'd
  arrays / structs / lists never freed before the surrounding
  MemoryContext resets, leading to quadratic-or-worse growth on
  pathological inputs).
- Long-lived leaks in cache / catalog / hash machinery (allocations
  that grow with `pg_backend_memory_contexts` across iterations
  but never plateau).
- Bringing up the **two-toolchain detection harness** (macOS
  ASan+UBSan+`leaks` + Linux Valgrind container) when the project
  doesn't have one yet.
- Validating the **trilogy methodology** by running it blind
  against a known-fixed upstream commit and comparing designs at
  the end (Phase 4).

**Out of scope:**
- Pure use-after-free / heap-buffer-overflow / double-free bugs
  with no leak component — ASan alone catches those; no harness
  setup needed. Use `debugging/SKILL.md` directly.
- Shared-memory leaks (DSM segments not destroyed, shmem hash
  entries not removed). The harness here is per-backend; shmem
  leaks need a different probe.
- Memory pressure / OOM-killer tuning. Leaks are unbounded growth
  under load; pressure is bounded growth that's too big. Different
  problem.
- `ereport`/error-recovery path leaks — distinct subsystem; the
  ErrorContext is reset on every elog cycle, so leaks there
  accumulate only across log-not-error sessions. Handle separately.

## Pre-flight

- **Companion skills:** load `pg-feature-brainstorm` +
  `pg-feature-plan` + `pg-implement` for the trilogy;
  `memory-contexts` and `memory-context-allocset-internals` for
  the underlying model; `debugging` for ASan + `leaks` invocations;
  `build-and-run` for the parallel `dev/build-{debug,asan}/`
  profiles.
- **Canonical commit:** `5a2043bf713` — *Fix transient memory
  leakage in jsonpath evaluation* (Tom Lane, 2026-03-19). Read it
  for the reproducer SQL, the design rationale, and the
  inline-chunked-list pattern. Read the full commit message; it's
  the reference example of how a memory-leak fix should be written
  up.
- **Common pitfalls (one-line each):**
  - Valgrind doesn't work on macOS 26 arm64 (F26 in
    `sessions/2026-06-23-memory-hunt-calibration.md`) — Apple
    Silicon mainline support stops at macOS 10.13 x86_64. Use
    Ubuntu 24.04 Docker container for Valgrind 3.22+; macOS host
    gets the ASan + `leaks` triangulation only.
  - macOS `/usr/bin/leaks` refuses to probe ASan binaries (F27) —
    "target process is using Address Sanitizer which doesn't work
    with memory analysis tools." Use the debug build for `leaks`,
    ad-hoc codesign it with `com.apple.security.get-task-allow`
    so it's debuggable.
  - macOS LSan is unavailable on Darwin per
    `.claude/skills/build-and-run/SKILL.md` — `detect_leaks=0` is
    mandatory in `ASAN_OPTIONS`. Real leak detection needs Linux
    container OR `leaks` against codesigned debug build OR
    `pg_backend_memory_contexts` plateau test.
  - Debian 12's stock Valgrind 3.19 trips
    `m_debuginfo/readdwarf.c:2761` ("unhandled DW_OP_ 0x92") on
    GCC 12 arm64 binaries. Use Ubuntu 24.04 (Valgrind 3.22+) or
    newer.
  - Ownership invariants in plan §7 must be grep-verified per
    F30 — the brainstorm-time claim "X is owned by Y" is FALSE
    if any code site producing X hands it elsewhere; absent the
    grep-pass it surfaces only at Phase 2's R4 phase-end check.
  - Storage representation choice (by-value inline / by-pointer /
    by-reference-to-shared-pool) is foundational per L5 — the
    brainstorm must consider all three. Inheriting the parent
    code's representation as a given is the failure mode the L5
    sub-question prevents.

## File checklist (the FULL sweep)

This is a methodology scenario, not a change-class scenario, so
the "files that change" varies per bug. The checklist below names
the artifacts every leak-fix run produces, regardless of which
subsystem hosts the bug. `pg-feature-plan` should match this
checklist when it pins §3 for the per-bug plan.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `planning/memory-hunt/baseline.md` | Phase 0 detection-harness write-up: which signals are live on this host, which workloads were run, which findings classify as suppressed-infra-noise vs PG-attributable. | — | — |
| 2 | `planning/memory-hunt/container/Dockerfile` | Ubuntu 24.04 image with `meson`, `ninja`, `valgrind` 3.22+, build deps. Used when the host can't run Valgrind natively (macOS) or for cross-check. | — | build-and-run |
| 3 | `planning/memory-hunt/container/inside-build.sh` | Inside-container: `meson setup --buildtype=debug -Dcassert=true -Doptimization=0 -Dc_args="-DUSE_VALGRIND -DMEMORY_CONTEXT_CHECKING"` + `ninja install`. Runs at every commit-pin change. | — | build-and-run |
| 4 | `planning/memory-hunt/container/inside-run.sh` (or `inside-<bug>.sh`) | Inside-container: postmaster under Valgrind memcheck or RSS-sampler against the running backend; runs the bug's reproducer; captures per-pid logs. | — | debugging |
| 5 | `planning/memory-hunt/workloads/<workload>.sql` (or `.sh`) | The reproducer recipe (gold-standard if the canonical commit ships one; synthesized otherwise). | — | psql, testing |
| 6 | `planning/memory-hunt/evidence/<bug>-{parent,fix}/` | Per-pin evidence: `rss-timeseries.tsv`, `valgrind.log-<pid>`, `repro-output.txt`, `build-info.txt`. | — | — |
| 7 | `planning/<bug-slug>/brainstorm.md` | Phase 2 of the trilogy: §0 usage surface (which input shapes must not leak), §0.5 mechanism survey, candidate approaches with Storage-representation field (per L5), recommended approach + DECISION questions. | — | pg-feature-brainstorm |
| 8 | `planning/<bug-slug>/plan.md` | Phase 2 of the trilogy: 14-section plan with §3 file table + §7 Memory + resource management WITH grep-pass ownership verification (per F30) + §8 phases. | — | pg-feature-plan |
| 9 | `src/backend/<subsystem>/<leak-site>.c` | The actual code fix on a `dev/` worktree branched at the canonical commit's parent. Per-phase commits per R5; each with `Plan:` trailer. | (per-file doc if one exists) | pg-implement |
| 10 | `src/test/regress/sql/<area>.sql` + `expected/<area>.out` | Regress rows for the leak pattern at multiple input sizes — pin counts to catch silent regressions, don't assert RSS or wall-time (those flake on slow CI). | — | testing |
| 11 | `planning/<bug-slug>/notes.md` | R8 per-phase notes: commit SHA, R7 escalations, what each phase did and didn't do. | — | pg-implement |
| 12 | `planning/<bug-slug>/comparison.md` | Phase 4 (when the canonical commit is the fix being shadowed): diff our derived fix vs upstream's, score on RSS envelope + design clarity + API churn; harvest F-findings and L-lessons. | — | — |
| 13 | `sessions/<date>-<slug>-retro.md` | End-of-run retro: F-findings, L-lessons, action items for the corpus + skills. | — | memory-keeping |

## Phases — suggested split for `pg-feature-plan`

These are the trilogy phases for the per-bug planner run. They
sit ON TOP of the per-bug brainstorm/plan, which the planner suite
already structures.

1. **Phase 0 — Harness setup (no fix yet).** Stand up the
   detection toolchain. Verify it surfaces the canonical bug's
   pre-fix signal (RSS climbs to known peak / Valgrind reports
   leaks / pg_backend_memory_contexts grows). If the harness
   produces zero signal on the canonical reproducer, the harness
   is broken — fix it before any plan work.
   **Phase-end check:** the canonical reproducer shows the
   expected signal magnitude on the canonical commit's parent.

2. **Phase 1 — Triage + target pick.** With the harness live,
   pick the bug to fix. If the user named one, validate it
   reproduces. If "find leaks" was the brief, rank candidates by
   reproducibility × corpus-support ÷ blast-radius; pick one;
   write `triage.md` with a one-line reproducer recipe.
   **Phase-end check:** ONE target picked + a one-paragraph "why
   this one" + a one-line `Reproducer:` recipe.

3. **Phase 2 — Trilogy: brainstorm + plan.** Invoke
   `pg-feature-brainstorm` with the bug's reproducer as input. §5
   "Candidate approaches" MUST fill the "Storage representation"
   field for each (per L5). Invoke `pg-feature-plan`; §7 MUST run
   the grep-pass ownership-invariant check (per F30). Lock
   DECISIONs with the user.
   **Phase-end check:** plan is R2-clean (3-5 cite spot-checks
   match current source); §3 file table is complete; ≥3 phases
   with explicit phase-end checks.

4. **Phase 3 — Implement via `pg-implement`.** One phase = one
   commit per R5. **Per-phase R13 gate** = R13's normal scope
   ladder (catalog → contrib, grammar → ecpg, executor → iso +
   pgss, ruleutils → EXPLAIN VERBOSE) PLUS the bug's harness
   reproducer showing the leak fixed. R7 escalation is normal
   here; ownership-invariant errors caught at R4 phase-end check
   time get absorbed inline tier-1.
   **Phase-end check:** per-phase R13 + per-bug harness.

5. **Phase 4 (calibration mode only) — Comparison.** When the
   canonical commit is the fix being shadowed (blind methodology
   run), diff our final code vs upstream's. Compare design
   choices, diff size, API churn, test coverage. Write
   `comparison.md` with the score table and harvested findings.
   **Phase-end check:** comparison.md exists with §"Score"
   table + ≥1 L-lesson and ≥1 F-finding (or explicit
   acknowledgement that the run is clean).

6. **Phase 5 — Harvest.** Update this scenario if the run
   surfaced a methodology gap; update the planner-suite skills if
   the run produced a new L/F; append session retro;
   `memory-keeping` updates `progress/STATE.md`.

## Pitfalls

- **Trap 1 — Generic workloads on a clean master produce zero
  signal.** When PG master has had a leak-hunting sweep (15+
  fixes 2025-2026 in current pin), WL1/WL3/WL4 of the original
  memory-hunt plan all come back clean. Don't conclude "harness
  broken" before checking git log for recent leak fixes; the
  bug is likely already fixed. Pivot to surgical-reproducer mode:
  pick a recent leak-fix commit, check out the parent, reproduce.
- **Trap 2 — `leaks` reports 29 invariant leaks on macOS for any
  process.** Those are dyld init leaks (`"XPC_SERVICE_NAME=0"`,
  `"LC_CTYPE=UTF-8"` env strings + libsystem internals). They
  reproduce identically on a no-work baseline. Take the diff
  baseline-vs-workload, not the raw count.
- **Trap 3 — Valgrind's "still reachable" is not a leak.** Real
  leaks show under `definitely lost:` or `possibly lost:`.
  "Still reachable" is alive-at-exit memory (caches, dlopen'd
  libs, etc.) — normal for any program. Don't chase it.
- **Trap 4 — Suppressed events ≠ leaks.** `valgrind.supp`
  matches at `ERROR SUMMARY: 0 errors (suppressed: N from M)`
  are invalid-reads/uninit-value reads that PG knows about and
  chose to suppress. They're orthogonal to the LEAK SUMMARY block.
- **Trap 5 — Mixed copy-vs-borrow Append patterns.** When the
  collection accepts both `Append(list, ownedThing)` and
  `Append(list, borrowedRef)`, you can't safely pfree elements at
  Free time — and you can't safely NOT pfree them if the leak is
  in the owned-thing case. Either rewrite to always-copy (Tom
  Lane's choice for JsonValueList) or wrap the hot site in a
  per-call MemoryContext that absorbs ownership ambiguity (our
  jsonpath_leak choice). The "ownership-invariant" F30 grep-pass
  surfaces this trap at plan time.
- **Trap 6 — Backportability bias.** "Fix it in a way that
  backports cleanly to PG 16" pushes you toward Approach A
  (per-site explicit free) over Approach C/E (struct redesign).
  Approach A leaves the underlying inefficiency intact — leak
  gone, but allocation overhead remains. Decide consciously
  whether backport is in scope; if not, the struct redesign
  often wins on long-term clarity.
- **Synchronization traps** (sibling artifacts that must change
  together):
  - `inside-build.sh` ⟷ `Dockerfile` — Valgrind version
    requirement changes pull both.
  - per-bug plan's §3 ⟷ §7 — when §3 adds a file, §7's
    ownership-invariant grep-pass MUST re-run over the
    updated source set.

## Verification (exact test invocations)

```bash
# 1. Build the Linux/Valgrind container (one-time per host)
docker build -t pg-memhunt:noble planning/memory-hunt/container/

# 2. Bind-mount a worktree at the canonical commit's parent, run the
#    reproducer, capture RSS / Valgrind logs.
docker run -d --name pg-memhunt --platform=linux/arm64 \
  -v /tmp/pg-<bug>-parent:/pg-source:ro \
  -v "$PWD/planning/memory-hunt/workloads:/workloads:ro" \
  -v "$PWD/planning/memory-hunt/evidence/<bug>-parent:/evidence" \
  -v "$PWD/planning/memory-hunt/container:/scripts:ro" \
  pg-memhunt:noble \
  tail -f /dev/null
docker exec pg-memhunt bash /scripts/inside-build.sh
docker exec pg-memhunt bash /scripts/inside-<bug>.sh

# 3. Native macOS path (when Linux container isn't an option)
# Codesign the debug postgres so `leaks` can probe it:
cat > /tmp/dbg.entitlements <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.get-task-allow</key>
  <true/>
</dict>
</plist>
XML
codesign -s - -f --entitlements /tmp/dbg.entitlements dev/install-debug/bin/postgres
# Then start with MallocStackLogging=1 and probe with /usr/bin/leaks <pid>.

# 4. Per-phase R13 phase-end check (executor-tier default)
meson test -C dev/build-debug --suite setup --suite regress \
                              --suite isolation --suite pg_stat_statements \
                              --no-rebuild

# 5. R12 end-gate (after Phase 3 lands all per-phase commits)
meson test -C dev/build-debug --no-rebuild
```

## Worked example (jsonpath_leak calibration, 2026-06-23)

The canonical commit's parent shows **5,686,688 KB peak RSS** on
Tom Lane's reproducer
(`SELECT jsonb_path_query((SELECT jsonb_agg(i) FROM
generate_series(1,10000) i), '$[*] ? (@ < $)')`); the fix lands
at **32,160 KB**. Our blind trilogy run landed at **32,272 KB**
via a different design (per-call MemoryContext at executePredicate)
than Tom Lane's (chunked inline-storage JsonValueList). Both
mechanisms work; Tom's is structurally cleaner. The R7
escalations that fired were both anchored in failures the L5
brainstorm-sub-question and F30 plan-grep-pass would have
prevented at planning time.

Full retro: `planning/jsonpath_leak/comparison.md` +
`sessions/2026-06-23-memory-hunt-calibration.md`. The per-bug
artifacts at `planning/jsonpath_leak/{brainstorm,plan,notes,comparison}.md`
serve as the reference shape for future runs of this scenario.

## Cross-refs

- Companion skills: `.claude/skills/pg-feature-brainstorm/SKILL.md`,
  `.claude/skills/pg-feature-plan/SKILL.md`,
  `.claude/skills/pg-implement/SKILL.md`,
  `.claude/skills/memory-contexts/SKILL.md`,
  `.claude/skills/debugging/SKILL.md`,
  `.claude/skills/build-and-run/SKILL.md`.
- Related scenarios: `scenarios/add-new-test-module.md` (when the
  per-bug fix wants a `src/test/modules/test_<area>/` harness
  rather than appending to an existing regress suite).
- Idioms: `knowledge/idioms/memory-contexts.md`,
  `knowledge/idioms/memory-context-allocset-internals.md`,
  `knowledge/idioms/memory-context-slab-generation-bump.md`,
  `knowledge/idioms/memory-context-api-and-dispatch.md`.
- Subsystems: `knowledge/subsystems/utils-mmgr.md`.
- Issues: `knowledge/issues/<subsystem>.md` per the bug's host.
- Reference patch (canonical_commit):
  `git -C source show 5a2043bf713`.
- Calibration retro:
  `sessions/2026-06-23-memory-hunt-calibration.md`,
  `sessions/2026-06-01-mmgr-file-by-file.md` (the 5 mmgr gotchas
  flagged before this scenario existed).
