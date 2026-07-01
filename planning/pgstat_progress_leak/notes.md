# Notes — pgstat_progress_leak implementation

## Phase 1 — Delete redundant initStringInfo

- **Status:** done.
- **Commit:** `193187edd3a` on `feature_pgstat_progress_leak`
  (worktree `/Users/matej/Work/postgres/postgresql-dev-feature-pgstat_progress_leak`).
  Branched from parent commit `a450dd7ad4ff80c65f565f1a2bd24be8ff0bf3e3`.
- **Title:** *backend_progress: remove redundant initStringInfo before pq_beginmessage*
- **Test scope:** R13 helper-tier via pre-commit hook —
  `PG_PRECOMMIT_SCOPE=regress` (245 subtests clean).  Full
  R13 helper-tier ran independently before commit: 4 OK / 0
  fail / 0 skipped, 245 regress subtests.
- **What changed:**
  - `src/backend/utils/activity/backend_progress.c:103` —
    deleted `initStringInfo(&progress_message);` and the
    blank line above it.
  - Net -2/+0.
- **TC-LB-1 harness verification:** parent-vs-fix reproducer
  runs in `planning/memory-hunt/evidence/pgstat-{parent,fix}/`
  show top worker RSS delta drops from **+18,004 KB** (parent)
  to **+6,384 KB** (upstream fix).  Our fix is byte-identical
  to upstream `b20c952ce70`, so equivalent outcome verified
  by construction.  Docker daemon happened to be down at the
  moment of our-fix TC-LB-1 rerun; the byte-identity vs
  upstream serves as the verification.
- **Surprises / drift:**
  - Initial reproducer workload (5M rows × 8 indexes,
    ~9s VACUUM) produced too-noisy signal — parent showed
    +3 MB per worker, fix showed +2 MB per worker, difference
    within noise band.  Amplified to 10M rows × 16 indexes so
    the VACUUM runs long enough (~43 s per top worker) that
    the leak compounds to +18 MB — clean signal.  Lesson
    baked into `scenarios/fix-memory-leak.md` §"Pitfall: small
    per-call leaks need long-running workers to see clean
    signal above workload noise".
  - Docker daemon stopped mid-run (looks like Docker Desktop
    was closed).  Workaround: byte-identity vs upstream
    verified the fix WITHOUT needing container rerun.  Would
    have re-run in container if the diff had been different.
- **What this phase did NOT do:**
  - No regress test row added (per DECISION 3: cross-platform
    RSS-assertion is flaky; the bug's blast radius is small
    enough that Valgrind in the buildfarm suffices).  Upstream
    `b20c952ce70` also shipped no test.
  - No consultation of `b20c952ce70` source or commit message
    until Phase 4 comparison — blind trilogy constraint held.
- **F30 grep-pass result:** 21 `pq_beginmessage()` call sites
  in `src/backend`; only `backend_progress.c:103` pre-calls
  `initStringInfo`.  No latent duplicates.  The grep-pass
  was the load-bearing step of Phase 2's plan §7 — it
  confirmed the ownership invariant at plan time rather than
  at R4 phase-end check time.
- **L5 storage-representation:** noted in brainstorm §5 that
  `StringInfoData` as BSS-static + palloc'd `data` is the
  correct shape for the pq_ contract.  Approach B (drop
  `static`) considered and rejected.  L5 served its purpose:
  forced explicit consideration of the storage choice, even
  though the answer was "keep it as-is".

## Phase 4 — Comparison

- **Status:** done.
- **Artifact:** `planning/pgstat_progress_leak/comparison.md`.
- **Result:** our fix is **byte-identical** to upstream
  `b20c952ce70`.  Same 2-line deletion at the same location.
  The blind trilogy converged exactly on the upstream shape.
- **Methodology score:** Perfect for this run.  L5 + F30
  (landed after jsonpath_leak) both fired and both anchored
  the recommendation.  No R7 escalations, no re-plan, no
  Phase 1 gate miss.  Simpler bugs = tighter trilogy fit.

## Trilogy timeline (this run)

| step | wall time | outcome |
|---|---|---|
| Container harness reuse (pg-memhunt:noble image already local) | 0 s | ready |
| Reproducer script + amplified workload build (10M rows) | ~5 min | table + indexes populated |
| Parent-commit build + amplified VACUUM run | ~11 min | +18 MB leak on top worker |
| Upstream-commit build + amplified VACUUM run | ~11 min | +6 MB clean growth on top worker |
| Blind brainstorm + F30 grep-pass + plan | ~5 min | approach A recommended |
| Dev-worktree build + apply patch + R13 regress | ~2 min | 245 subtests clean |
| Phase 4 comparison | ~5 min | byte-identical to upstream |

**Total: ~40 minutes** for a full second-target trilogy run
(reuses harness infrastructure from jsonpath_leak).
