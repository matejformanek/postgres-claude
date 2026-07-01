# Phase 0 baseline — memory-hunt calibration

**Date:** 2026-06-22
**Source pin:** `e18b0cb7344` (`Fix MarkBufferDirtyHint() to not call GetBufferDescriptor() for local buffers`)
**Builds:**
- `dev/build-asan/`  — clang-21, `-Db_sanitize=address,undefined`, cassert+debug+O0
- `dev/install-debug/bin/postgres` — codesigned with `com.apple.security.get-task-allow` entitlement so macOS `leaks` can read process memory

**Platform:** macOS 26.5.1, arm64 (Apple Silicon). Darwin 25.5.0.

## §1 Detection-toolchain pivot (decided pre-Phase-0)

Plan called for Valgrind as primary signal. **Not viable on this host:**

- Mainline Valgrind 3.27.1 (Homebrew has the formula) only supports macOS
  up through 10.13, x86_64. On macOS 26 arm64 the install builds but
  fails at run-time — no syscall / dyld support for arm64-darwin.
- Community fork `LouisBrunner/valgrind-macos` exists but is experimental
  and drifts behind mainline.

Pivoted to three native signals:

1. **ASan + UBSan** (compile-instrumented, `dev/build-asan/`)
   — catches use-after-free, heap-buffer-overflow, double-free, undefined
   behaviour at access time. **Cannot detect pure leaks on macOS**
   (LSan unsupported on Darwin per
   `.claude/skills/build-and-run/SKILL.md`).
2. **macOS `/usr/bin/leaks`** against a running backend
   (`dev/install-debug/`, non-ASan because `leaks` refuses to probe an
   ASan-instrumented binary — *"target process is using Address
   Sanitizer which doesn't work with memory analysis tools"*).
   — catches malloc-tracked leaks (memory allocated, lost reference,
   never freed). Requires `com.apple.security.get-task-allow`
   codesign entitlement to symbolicate properly.
3. **`pg_backend_memory_contexts`** — catches unbounded growth in
   long-lived MemoryContexts across iterations within the same backend
   session.

ASan and `leaks` together cover the same bug classes Valgrind would —
modulo uninitialized-memory reads (MemorySanitizer also broken on Mac).

## §2 Workloads run

All workload scripts live in `planning/memory-hunt/workloads/`:

| #   | Name                      | Description                                                                                            |
|-----|---------------------------|--------------------------------------------------------------------------------------------------------|
| WL0 | (synthetic) baseline      | `psql` opens, snapshots context table, sleeps. Zero work.                                              |
| WL1 | `normal-select.sql`       | 100×: `SELECT 1; SELECT count(*) FROM pg_class; pg_sleep(0.01)`                                        |
| WL2 | `regress-subset.sh`       | `pg_regress` subset: boolean, int4, numeric, select, expressions (partial run via `--use-existing`)    |
| WL3 | `pgbench-tiny.sh`         | pgbench scale=1, 4 clients, 60s (124,164 transactions completed)                                       |
| WL4 | `diverse-subsystems.sql`  | JSONPath ×3000, regex ×3000, PL/pgSQL DO + EXCEPTION ×500, prepared-stmt ×1000, CTE+window, sort/hash off-disk, xpath |

## §3 ASan-pass evidence (`dev/build-asan/`)

| Workload | ASan/UBSan reports | `pg_backend_memory_contexts` plateau test                |
|----------|-------------------:|----------------------------------------------------------|
| WL1      | 0                  | T1→T2→T3 same 100-iter loop: **+0 bytes** (perfect plateau after lazy-init) |
| WL2      | 0                  | (n/a — many short sessions)                              |
| WL3      | 0                  | (n/a — many short sessions; 124k transactions sustained at 2072 TPS, no aborts) |

### WL1 plateau detail

```
T0 (session open):      1,609,496 bytes
T1 (after 1st pass):    2,131,736 bytes   Δ +522,240   (lazy-init: CacheMemoryContext doubles, 7 new contexts: CFuncHash, PLpgSQL cast expressions, Rendezvous variable hash, TableSpace cache + 3 index info)
T2 (after 2nd pass):    2,131,736 bytes   Δ       0
T3 (after 3rd pass):    2,131,736 bytes   Δ       0
```

No unbounded-growth signal under any of WL1/WL2/WL3 against ASan.

## §4 `leaks` evidence (`dev/install-debug/` codesigned)

Probed three different workloads in identical single-backend probe setup
(open psql → run script → sleep 25s → `/usr/bin/leaks <pid>`):

| Workload   | Leaks reported | Bytes leaked |
|------------|---------------:|-------------:|
| WL0 baseline (no work) | 29 | 6,400 |
| WL1 normal-select      | 29 | 6,400 |
| WL4 diverse-subsystems | 29 | 6,400 |

**Identical address sets in all three reports** — `diff` between
`wl0-baseline-leaks.txt` and `wl4-diverse-leaks.txt` returns empty.

Inspecting the leak content:
- 2 of 29 contain env-var strings: `"XPC_SERVICE_NAME=0"`,
  `"LC_CTYPE=UTF-8"` — leaked once at dyld init.
- 27 of 29 are anonymous allocations at fixed sizes (128/64/320/256/512
  bytes), no PG symbols present (the report shows raw addresses; no
  `MemoryContext*` / `palloc*` / `MainLoop` frames).
- The numbers do not depend on workload — same 29 leaks open or stress.

**Interpretation:** these are macOS dyld / libsystem one-time
initialization leaks present in every macOS process. The harness is
working — it detects orphan mallocs deterministically — but PG master
at this pin contributes zero workload-induced leaks measurable through
macOS `leaks`.

## §5 Classification (Phase 0 triage table)

Per the plan, each finding is one of:
- **(A) suppressed by `valgrind.supp` / known infra noise**
- **(B) real leak**
- **(C) unbounded-context growth**

| Finding                                | Class | Notes                                                 |
|----------------------------------------|:-----:|-------------------------------------------------------|
| 29 leaks × 6.4KB, invariant under load | A     | macOS dyld/libsystem init (e.g. env strings); not PG  |
| WL1 lazy-init growth +522KB then 0     | A     | Expected lazy init: catalog/PL/pgSQL hash setup       |
| WL1/WL2/WL3 ASan reports               | n/a   | (none — no UAF/OOB)                                   |
| WL1/WL2/WL3 unbounded growth           | n/a   | (none — plateaus)                                     |

**No (B) or (C) findings.**

## §6 Exit-gate verdict

Phase 0 exit condition (from `pg-claude-plan` / memory-hunt plan):

> The harness reproduces **at least one** real leak — under a workload
> that's representative of "normal use". If Phase 0 produces only
> suppressed output, the harness is broken (or our ambition is wrong)
> — STOP and re-scope before Phase 1.

**Verdict: STOP.** The harness *works* (we can deterministically count
29 leaks down to the byte across three workload variants and a
no-op baseline), but it produces **zero PG-attributable leaks** under
the workloads chosen. Either:

a) **PG master is genuinely clean** under modest workloads after the
   2024-2026 upstream leak-hunting sweep. Recent fixes already in this
   pin include `5a2043bf713` (JSONPath), `89d57c1fb35` (callbacks),
   `abdeacdb092` (nodeSubplan), `d942511f08a` (pg_locale_icu), and
   ~12 others since 2025-01-01.
b) **The macOS detection stack is insufficient.** `leaks` only finds
   orphan malloc(); PG's MemoryContext system manages an arena that
   `leaks` sees as one big malloc. A palloc'd object lost inside a
   live arena would be invisible. Equivalent gap in production would
   need LSan (Linux-only) or Valgrind memcheck (Linux-only) to see.
c) **The workloads don't exercise leak-prone code paths.** Agent 3's
   leak-history list named JSONPath, logical-replication slot sync,
   PL/pgSQL, and regex; only JSONPath/PL/pgSQL/regex hit, and only
   shallowly.

## §7 Re-scope options (input needed)

To make Phase 1 productive, three viable directions:

1. **Linux-container harness.** Bring up a Linux dev container with
   the dev tree mounted, build PG inside with Valgrind + LSan, run
   workloads in the container. Restores Valgrind / LSan signal.
   Cost: ~1-2h container plumbing + first workload run.

2. **Surgical reproducers against known-leak commits.** For each
   2025-2026 leak-fix commit (e.g. `5a2043bf713`), check out the
   parent, run the commit's test case under the existing macOS
   harness, verify the leak appears, apply the fix, verify it
   disappears. Treats the leak-fix history as a regression-detection
   training set rather than fishing for new leaks. Cost: ~1h per
   target; can pick 3-5.

3. **Long-running real-world workload.** Run pgbench or similar
   continuously for hours, sampling `pg_backend_memory_contexts` +
   `top` RSS at intervals. Catches drift in long-lived contexts that
   short workloads miss. Cost: low engineering, high wall-clock; lets
   the machine run unsupervised.

Recommend (1) Linux container — closest to plan-as-written, restores
the proper detection toolchain, and gives a corpus of findings rather
than one-target-at-a-time hunts. If that's unattractive, (2) is the
fastest path to validating the methodology with confirmed-real
bugs.

## §8.5 Linux/Valgrind re-scope (post-§7 follow-up)

Per the §7 question, the user picked the Linux-container harness.
**Result: same conclusion as macOS — PG master is leak-free under
these workloads.** Now corroborated by two independent toolchains.

### Container build

- `planning/memory-hunt/container/Dockerfile` — Ubuntu 24.04 (was
  Debian 12 in first cut; Valgrind 3.19 in Debian 12 hits
  `m_debuginfo/readdwarf.c:2761` "unhandled DW_OP_ 0x92" on GCC 12
  arm64 binaries; Valgrind 3.20+ has the fix, Ubuntu 24.04 ships 3.22).
- Container image `pg-memhunt:noble` — 947MB, build prereqs + Valgrind
  3.22.0 + gcc 13.3.0 + ICU/XML/LDAP/SSL deps, non-root user uid=501
  matching host so bind-mount writes are host-owned.
- PG inside container: compiled with
  `meson setup --buildtype=debug -Dcassert=true -Ddebug=true -Doptimization=0 -Dc_args="-DUSE_VALGRIND -DMEMORY_CONTEXT_CHECKING"`.
  Build is container-local at `/home/pg/build`, never leaks to host.

### Run

`planning/memory-hunt/container/inside-run.sh` starts the postmaster
under Valgrind memcheck with:

```
valgrind --tool=memcheck --leak-check=full \
         --show-leak-kinds=definite,indirect,possible \
         --track-origins=yes --trace-children=yes \
         --child-silent-after-fork=no --num-callers=40 \
         --error-limit=no --suppressions=/pg-source/src/tools/valgrind.supp
```

Workloads executed (clean WL4 after fixing PG 19 incompatibilities —
old JSON `'t'` cast, `array_agg(... LIMIT)` aggregate-internal LIMIT,
`EXECUTE pq1($1)` parameter syntax — fixed by `INTO b` for boolean
return, `(array_agg(... ORDER BY))[1:5]` slice, and `EXECUTE format(...)`):

| Workload | Backend pids       | Status                                     |
|----------|--------------------|--------------------------------------------|
| WL1      | 1 (e.g. 9376)      | 100 iter (SELECT + count(pg_class)) clean  |
| WL4      | 1 (e.g. 9379)      | JSONPath×3000 + regex×3000 + PL/pgSQL×500 + plan-cache×1000 + CTE/window/sort/hash, all clean |
| WL3      | 2 (e.g. 9382-9387) | pgbench 572 transactions under Valgrind    |

### Valgrind aggregate tally (all 21 backends, post-WL4-fix run)

```
ALL backends:  definitely lost = 0 bytes
               indirectly lost = 0 bytes
               possibly lost   = 0 bytes
               still reachable = 166KB-1.3MB (alive-at-exit, normal)

Suppressed (per backend, matched by upstream valgrind.supp):
  pid 9379 (heavy WL4 backend):  50 events from 3 unique stacks
  pid 9367 (pgbench worker):     43 events from 1 stack
  pid 9360, 9382, 9387:          1-2 events each
  remaining 15 backends:         0 each
```

`ERROR SUMMARY: 0 errors` everywhere. The 50/43 suppressed entries are
NOT leaks (LEAK SUMMARY is all-zero); they're invalid-read /
uninit-value events matched by upstream's `src/tools/valgrind.supp` —
known PG patterns with documented justifications.

### Convergent verdict across both toolchains

| Signal                                         | macOS  | Linux  |
|------------------------------------------------|:------:|:------:|
| UAF / OOB / double-free (ASan / memcheck)      | clean  | clean  |
| Pure leaks (`leaks` / Valgrind LEAK SUMMARY)   | clean¹ | clean  |
| Unbounded-context growth (`pg_backend_*ctx`)   | clean  | clean  |
| Already-suppressed events (`valgrind.supp`)    | n/a    | 100 total events across 5 unique stacks |

¹ macOS `leaks` reports 29 invariant leaks ≈ 6.4KB. These are
identical address-for-address across baseline (no-work) and stressed
runs, contain dyld-init env strings, and are not PG-attributable.

PG master at `e18b0cb7344`, exercised by WL1 + WL4 + WL3 under
Valgrind 3.22 with full PG `USE_VALGRIND` instrumentation, **produces
zero leaks**. The harness *works* (it captures still-reachable
counts, fires suppression matches, reports backend-level summaries
per-PID) but PG simply does not leak on these inputs.

### Why this matters for Phase 1

The plan assumed Phase 0's harness output would *rank candidate
targets* for Phase 1's pick. With zero candidates, "evidence-driven
target picking" can't proceed as written. Three live options:

1. **Surgical reproducers against 2025-2026 leak-fix commits.**
   Treat the leak-fix git history as a regression-detection corpus.
   For each commit (e.g. `5a2043bf713` JSONPath, `abdeacdb092`
   nodeSubplan), checkout the parent, reproduce the leak under the
   working harness, apply the fix, verify it disappears. Validates
   the methodology on confirmed-real bugs even though master-at-HEAD
   is clean.

2. **Adversarial input fuzzing.** Use SQLsmith or random query
   generation against the Valgrind backend. Surfaces leaks in code
   paths not covered by upstream's own regress suite. Out of scope
   for this calibration but a natural Phase 5+.

3. **Deeper static audit of the 5 mmgr gotchas.** From the
   2026-06-01 file-by-file session: `MemoryContextSetParent`
   multi-level loop, AllocSet exact-fit power-of-two write-past-end,
   `bump.c` production no-chunk-header, `dsa.c` lock-order audit
   incomplete, `freepage.c` btree split/merge. Audit-mode rather
   than reproducer-driven. Yields a corpus doc + may surface latent
   bugs; doesn't ship a fix unless one is found.

Recommendation: **(1) surgical reproducers** — it most directly
validates the planner-suite methodology against real bugs, and the
fixes give per-commit `Fixes:`-style citations. (3) is interesting
research but isn't on the calibration critical path.

## §8 Artifacts

```
planning/memory-hunt/
├── baseline.md            (this file)
├── evidence/
│   ├── wl0-baseline-leaks.txt   (29 leaks)
│   ├── wl1-leakprobe-leaks.txt  (29 leaks)
│   ├── wl4-diverse-leaks.txt    (29 leaks)
│   ├── wl1-pre.csv / wl1-post.csv / wl1-T{0..3}.csv
│   ├── wl4-pre.csv / wl4-post.csv
│   ├── wl1-stdout.txt / wl1-stderr.txt
│   ├── wl4-stdout.txt / wl4-stderr.txt
│   ├── wl4b-leaks.txt (post-entitlement re-run)
│   └── (zero asan-pg.* / ubsan-pg.* files written — no instrumentation fires)
└── workloads/
    ├── normal-select.sql
    ├── regress-subset.sh
    ├── pgbench-tiny.sh
    └── diverse-subsystems.sql
```

Plus harness state:
- `dev/install-debug/bin/postgres` is now codesigned with `get-task-allow`
  (signing identity: ad-hoc `-`). Reinstall via `ninja -C dev/build-debug install`
  reverts the signature.
- `dev/data-debug/` was re-`initdb`'d this session (was at catalog
  version 202605131, now at 202606091 matching the build).
- Docker image `pg-memhunt:noble` is local. Reproduce via
  `docker build -t pg-memhunt:noble planning/memory-hunt/container/`.
- `planning/memory-hunt/evidence/linux-pass1/` — first attempt at WL4
  with three PG 19 syntax incompatibilities; included for paper trail.
- `planning/memory-hunt/evidence/linux/` — final clean run after the
  WL4 fixes.
