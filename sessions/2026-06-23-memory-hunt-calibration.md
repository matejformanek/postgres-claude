# Memory-hunt calibration — Phase 0 + Phase 1 + Phase 2 of trilogy

**Date:** 2026-06-22 → 2026-06-23 (interactive, single session)
**Plan:** `planning/memory-hunt/baseline.md` (pivoted live during the session)
**Outcome:** detection harness built (macOS + Linux/Valgrind container);
PG master at `e18b0cb7344` confirmed leak-free under generic
workloads; surgical reproducer methodology validated against
`5a2043bf713` JSONPath leak (5.7 GB → 32 MB, 177× signal);
blind brainstorm + plan drafted for the trilogy methodology
validation. Phase 3 (implementation) + Phase 4 (comparison to
Tom Lane's actual fix) deferred to next session.

## Phase 0 — harness

Original plan said Valgrind primary. Three pivots happened
during Phase 0:

1. **Valgrind → ASan+UBSan** (macOS 26 arm64 Apple Silicon —
   mainline Valgrind only supports macOS through 10.13 x86_64;
   LouisBrunner/valgrind-macos arm64 fork is experimental).
2. **ASan-on-Mac → multi-signal triangulation** (LSan
   unsupported on Darwin per `build-and-run/SKILL.md`; macOS
   `leaks` works against the *debug* (non-ASan) build, since
   `leaks` refuses to probe ASan binaries).
3. **macOS-only → Linux container** (after both macOS signals
   produced zero PG-attributable findings, user opted into a
   Docker harness for proper Valgrind).

### macOS-native signals (zero PG-attributable findings)

- ASan/UBSan compile-instrumented (`dev/build-asan/`,
  `b_sanitize=['address','undefined']`): 0 reports across
  WL1 (100-iter SELECT), WL2 (partial regress subset), WL3
  (124k-tx pgbench).
- macOS `leaks` against `dev/install-debug/postgres` (codesigned
  with `com.apple.security.get-task-allow` so it can read process
  memory): **29 leaks / 6,400 bytes, identical address-for-address
  across no-work baseline + WL1 + WL4 (diverse subsystems)**. Two
  contain literal env strings `"XPC_SERVICE_NAME=0"` /
  `"LC_CTYPE=UTF-8"` → dyld init noise, not PG.
- `pg_backend_memory_contexts`: perfect plateau on WL1 — T1→T2→T3
  same 100-iter loop, +0 bytes growth (after lazy-init T0→T1
  +522KB caches stabilize).

### Linux container (also zero PG-attributable leaks)

`planning/memory-hunt/container/`:

- `Dockerfile` (Ubuntu 24.04 — needed for Valgrind 3.22; Debian 12
  ships 3.19 which hits `m_debuginfo/readdwarf.c:2761` "unhandled
  DW_OP_ 0x92" on GCC 12 arm64 binaries; 3.20+ has the fix).
- `inside-build.sh`: meson setup with
  `-Dc_args="-DUSE_VALGRIND -DMEMORY_CONTEXT_CHECKING" -Doptimization=0 -Dcassert=true -Ddebug=true`.
- `inside-run.sh`: postmaster under
  `valgrind --tool=memcheck --leak-check=full --show-leak-kinds=definite,indirect,possible --track-origins=yes --trace-children=yes --num-callers=40 --suppressions=/pg-source/src/tools/valgrind.supp`.

Result across 21 backends spanning WL1 + WL4 (full JSONPath +
regex + PL/pgSQL + plan-cache + CTE + sort/hash) + WL3
(pgbench 572 transactions): every backend reports `definitely
lost: 0 / indirectly lost: 0 / possibly lost: 0`. 100 total
"suppressed" events across 5 unique stacks — matched by
upstream's `valgrind.supp`, NOT leaks.

### Phase 0 verdict

Both detection toolchains converge: **PG master at `e18b0cb7344`
is leak-free under WL1+WL3+WL4 workloads.** Likely cause:
15+ leak-fix commits in 2025-2026 already in our pin
(`b20c952ce70` pgstat, `5a2043bf713` jsonpath, `89d57c1fb35`
context callbacks, `abdeacdb092` nodeSubplan, …).

The plan's "evidence-driven target picking" gate triggers:
STOP and re-scope. User picked: surgical reproducers.

## Phase 1 — surgical reproducer for `5a2043bf713`

Target: Tom Lane's JSONPath leak fix (2026-03-19).

Reproducer (gold-standard, from the commit message):

```sql
SELECT jsonb_path_query(
  (SELECT jsonb_agg(i) FROM generate_series(1, 10000) i),
  '$[*] ? (@ < $)');
```

Setup: two git worktrees of `source/` at parent and fix
(`/tmp/pg-jsonpath-parent` at `7724cb9935a` and
`/tmp/pg-jsonpath-fix` at `5a2043bf713`). Bind-mount one at a
time into the container, rebuild PG, run the reproducer, sample
backend RSS every 0.2s.

**Parent commit `7724cb9935a` (pre-fix):**
RSS climbs from baseline ~32 MB to peak **5,686,688 KB (5.7 GB)** at
t=49s of the reproducer. Plateaus until t=59s. Drops to 1.4 GB
at t=61s as the query returns 9999 rows.

**Fix commit `5a2043bf713`:**
RSS stays flat at **32,160 KB (32 MB)** for the entire 15s
probe window. Returns same 9999 rows in 3.07 s.

| metric             | parent      | fix        | delta       |
|--------------------|------------:|-----------:|------------:|
| Peak backend RSS   | 5,686,688KB | 32,160 KB  | **-99.4%**  |
| Query wall-clock   | ~60 s       | 3.07 s     | **20×**     |
| Result rows        | 9999        | 9999       | identical   |

**177× memory reduction. The reproducer is now a durable
calibration artifact** at `planning/memory-hunt/container/inside-jsonpath.sh`
+ `planning/memory-hunt/evidence/jsonpath-{parent,fix}/`.

## Phase 2 of trilogy — blind brainstorm + plan

User picked: **run the planner trilogy BLIND** — derive the fix
from scratch without consulting `5a2043bf713`'s source. Compare
designs at Phase 4.

### Brainstorm (`planning/jsonpath_leak/brainstorm.md`, ~250 lines)

Root cause located in `jsonpath_exec.c` at parent:
- `JsonValueList` struct (line 147): `singleton + List*` hybrid.
- `executePredicate` (line 2026): declares local `lseq`, `rseq`
  JsonValueLists, populates them, NEVER frees them.
- For `$[*] ? (@ < $)` with 10K elements: rseq materializes 10K
  cells; outer `[*]` calls executePredicate 10K times; 10K × 10K =
  100M cells leak into the surrounding MemoryContext.

§0 enumerated 15+ SQL surfaces that must not leak. Load-bearing
test row **TC-LB-1** = Tom Lane's exact reproducer.

Four candidate approaches:
- **A.** Local explicit free at each call site (minimal diff,
  audit-heavy).
- **B.** Per-call MemoryContext (atomic, ~400ns overhead per
  predicate).
- **C.** Redesign JsonValueList as expansible JsonbValue-pointer
  array (one pfree releases everything; 8× smaller per cell).
- **D.** Caller-side arena reset per top-level iteration
  (most efficient, lifetime-bookkeeping bug surface).

Recommended **C+A** (struct redesign AND explicit free at every
transient call site).

### DECISION answers (user-locked)

1. **Approach:** C+A — recommended.
2. **Test scope:** TC-LB-1 + N-microbench rows N ∈ {10, 100,
   1000, 10000}.
3. **R15 scope:** audit ALL 15 `JsonValueList` declarations in
   the file, add `JsonValueListFree` at every transient one
   (not just the 4 known leak sites).

### Plan (`planning/jsonpath_leak/plan.md`, ~280 lines)

Three phases:
- **Phase 1 — architectural centerpiece:** redesign
  `JsonValueList` struct + 9 helpers + new `JsonValueListFree`.
  Phase-end check at R13's executor tier
  (`--suite regress --suite isolation --suite pg_stat_statements`).
  TC-LB-1 must pass green.
- **Phase 2 — audit + free at all 14 transient sites.**
- **Phase 3 — tests + docs** (regress addition only;
  scenario doc and corpus updates land in Phase 4).

§9 risks enumerated (JsonbValue ownership invariant,
JsonTablePlanState.found semantics, iterator stability under
append, singleton↔array transitions, scope creep into
JSON_TABLE, test fragility on slow CI).

§14 Phase 4 hook: after Phase 3 lands, fetch `5a2043bf713`,
diff our `jsonpath_exec.c` vs Tom Lane's, write
`planning/jsonpath_leak/comparison.md`. Expected dimensions to
compare: struct shape, iterator design, audit completeness,
test coverage shape.

## State carried forward

- `planning/memory-hunt/` — Phase 0/1 artifacts (baseline.md,
  triage.md, evidence/, workloads/, container/).
- `planning/jsonpath_leak/` — Phase 2 of trilogy artifacts
  (brainstorm.md + plan.md).
- `pg-memhunt:noble` Docker image — local, ~983 MB. Rebuild via
  `docker build -t pg-memhunt:noble planning/memory-hunt/container/`.
- `/tmp/pg-jsonpath-parent` and `/tmp/pg-jsonpath-fix` — source
  worktrees at the two relevant commits (`git worktree list` in
  `source/`). Keep until Phase 4 compare lands; remove after.
- `dev/install-debug/bin/postgres` — codesigned ad-hoc with
  `com.apple.security.get-task-allow` so macOS `leaks` can probe.
  Reverts on next `ninja -C dev/build-debug install`.
- `dev/data-debug/` — was at catalog version 202605131, re-initdb'd
  this session to 202606091.

## What's next (in priority order)

1. **Phase 3 — implement.** Create dev worktree at
   `7724cb9935a`, run `/pg-implement jsonpath_leak` to land the 3
   commits per R5. Each commit carries
   `Plan: planning/jsonpath_leak/plan.md (phase N: …)` trailer.
   Per-phase R13 gate `--suite regress --suite isolation
   --suite pg_stat_statements`.
2. **Phase 4 — comparison.** Run `inside-jsonpath.sh` against
   our final commit and verify TC-LB-1 RSS <100 MB. Then fetch
   `5a2043bf713`, diff our `jsonpath_exec.c` against Tom
   Lane's, write `planning/jsonpath_leak/comparison.md` with the
   methodology-validation verdict.
3. **Harvest.** Write
   `knowledge/scenarios/fix-memory-leak.md` codifying the harness
   setup + per-target trilogy run; propose R13 v1.6 "memory-safety
   tier"; update `progress/STATE.md`.

## L-lessons-that-worked

- **L1 — multi-tool detection convergence.** Two independent
  toolchains (macOS native + Linux/Valgrind) both reporting
  zero leaks was the strongest possible negative finding. One
  toolchain alone would have left "harness broken vs PG clean"
  ambiguous; the convergence resolved it.
- **L2 — gold-standard reproducer in commit messages.** Tom
  Lane's "this query: SELECT … requires 6GB" was 100% sufficient
  to validate the harness. Pick targets whose commit messages
  ship reproducers; don't try to invent reproducers for vague
  fix commits.
- **L3 — Valgrind 3.19 vs 3.22.** Debian 12's Valgrind is
  unusable for GCC 12 arm64 PG binaries; Ubuntu 24.04's 3.22 is
  fine. Note for `add-new-test-module` scenario or any docker
  container spec.
- **L4 — `leaks` vs ASan are mutually exclusive.** macOS's
  `leaks` refuses to inspect ASan binaries
  (*"target process is using Address Sanitizer which doesn't
  work with memory analysis tools"*). On Mac you must run two
  builds: ASan for compile-time errors, debug for malloc-tracked
  leaks. Codesigning with `get-task-allow` is required for the
  latter to see anything useful.

## F-findings (calibration retro)

- **F26 — macOS Valgrind compatibility is N/A.** The pg-claude
  plan calls Valgrind "primary" but the assumption breaks on
  Apple Silicon macOS. The `pg-claude` skill or top-level CLAUDE.md
  should note "Valgrind primary signal requires Linux; on macOS
  default to ASan+UBSan compile + `leaks` against codesigned debug
  build + `pg_backend_memory_contexts`. For confirmed Valgrind
  use a Docker container with Ubuntu 24.04+ (Valgrind 3.22+)."
- **F27 — `leaks` codesign requirement.** Every PG developer on
  macOS who wants to run `leaks` against their dev backend has to
  codesign with `com.apple.security.get-task-allow`. The
  `debugging/SKILL.md` should document this in §"macOS-native
  leak detection."
- **F28 — Container bind-mount + git worktree caveat.** A bind
  mount of a git worktree exposes `.git` as a *file pointer*
  whose path resolution depends on host-only links. `git rev-parse
  HEAD` inside the container fails with "(unknown)". Build-info
  capture should fall back to passing the commit via env var.
- **F29 — Brainstorm boundary for bug-fix.** The
  `pg-feature-brainstorm` skill explicitly says "Fix this specific
  bug → no brainstorm needed; cite + patch." For methodology
  *validation* runs against historical bug fixes, this rule
  bends: a lightweight brainstorm enumerating the solution space
  (free per-iteration / arena / struct redesign) IS the
  validation's main output. The skill could note "brainstorm
  applies to bugs when the solution space has >1 viable design
  AND the user wants the trilogy run for methodology validation."

These don't require immediate corpus changes; logging them so
they're available for the next planner-suite tune.
