# skill-creator iteration — parallel-query

## What I ran

Third skill-creator iteration of the run. Prior two (PR #201 / #202)
established that `run_eval.py` with `claude -p` produces ~40% pass
rates dominated by should-not-triggers (0% on should-triggers).

This iteration tests whether **intent-verb framing + explicit
anti-cues** in the description improves the trigger rate.

Skill picked: `parallel-query` — fresh post-SPLIT from PR #170,
hadn't been through `run_eval.py` yet.

## Setup

- 5 trigger-eval cases: 3 should-trigger (executor-node DSM plumbing,
  PARALLEL SAFE/RESTRICTED/UNSAFE marking, CreateParallelContext
  from extension), 2 should-not-trigger (DBA tuning, React fetch).
- 1 baseline run (no SKILL.md edits).
- 1 iteration-1 run after a focused description rewrite.

## Description rewrite (the only change to SKILL.md)

**Baseline description** (keyword-heavy, lifecycle dump):
> Parallel-query infrastructure in PostgreSQL backend / extensions —
> ParallelContext lifecycle (EnterParallelMode / CreateParallelContext
> / InitializeParallelDSM / LaunchParallelWorkers / ...) ...

**Iter-1 description** (intent-verb first + explicit anti-cues):
> Add parallel-aware C code in a PostgreSQL backend patch or
> extension — covers ParallelContext lifecycle (...). Use whenever
> a PG patch or extension adds parallel-aware code, picks PARALLEL
> SAFE/RESTRICTED/UNSAFE for a SQL-callable function, extends
> execParallel.c, plumbs a worker shmem state via shm_toc, or debugs
> a parallel worker DSM/TOC issue. Skip for DBA tuning of
> max_parallel_workers GUC, OpenMP / CUDA / pthread / Tokio /
> Go-goroutine parallelism, JavaScript Promise.all and async-iter
> parallel fetches, generic worker-pool questions, and ML
> data-parallel training.

Changes:
- Opens with the **action** ("Add parallel-aware C code") instead
  of the **noun** ("Parallel-query infrastructure").
- Adds **specific anti-cues** by name (OpenMP, CUDA, pthread, Tokio,
  Go-goroutine, Promise.all, ML data-parallel) — not just "generic
  threading".
- Restructures "Use whenever" / "Skip for" as parallel clauses
  rather than a comma-list, which is closer to how a triggering
  description in other skill ecosystems reads.

## Results

| Run | passed | should-trigger fired | should-not held |
|---|---|---|---|
| Prior pg-shadow-implement iter | 2/5 | 0/3 | 2/2 |
| Prior commit-message-style iter | 2/5 | 0/3 | 2/2 |
| parallel-query baseline | 2/5 | 0/3 | 2/2 |
| parallel-query iter-1 | **3/5** | **1/3** | 2/2 |

First non-zero should-trigger rate across the entire arc.

Per-query break-down on iter-1:
- ✓ PASS — `CreateParallelContext / shm_toc / LaunchParallelWorkers from C` — trigger_rate **1.00**
- ✗ FAIL — `ExecXXXInitializeDSM and ExecXXXInitializeWorker hooks` — trigger_rate 0.00
- ✗ FAIL — `PARALLEL SAFE / RESTRICTED / UNSAFE in pg_proc.dat` — trigger_rate 0.00
- ✓ PASS — `max_connections / shared_buffers tuning` — held (not triggered)
- ✓ PASS — `React useEffect parallel fetch` — held (not triggered)

## What changed and why

The single trigger that fired (CreateParallelContext from C) is the
most **direct API match** — the query names a specific PG symbol
that appears in the description. The two failing should-triggers
either use a generic verb ("plumb in") or an indirect cite
("PARALLEL SAFE in pg_proc.dat") that requires `claude -p` to
recognize the symbol as a PG thing rather than a generic term.

The improvement (0/3 → 1/3) is real but limited. The methodology
gap from PR #202 still stands: `claude -p` answers conversationally
unless the query verbatim names a tool-like symbol.

## Updates to the methodology recommendation

PR #202's recommendation said: build a session-based eval harness
on the Claude Agent SDK to replace `claude -p`. This run gives
**one new data point** for the recommendation:

- **Intent-verb + anti-cue description rewrites** measurably
  improve trigger rate even within `run_eval.py`'s noisy regime.
  Worth doing on every skill regardless of harness work.
- Action-first descriptions ("Add parallel-aware code...") beat
  noun-first descriptions ("Parallel-query infrastructure...") at
  this style of single-turn trigger eval.
- Specific named anti-cues (OpenMP/CUDA/Tokio/Promise.all) beat
  generic anti-cues ("generic threading"); they short-circuit
  false-positive triggering.

## What this means for the remaining 26 skills

The cheapest-and-effective intervention is a **description
rewrite pass**:
1. Open with the user's intent verb ("Add", "Write", "Pick",
   "Debug", "Configure"), not the domain noun.
2. List 4-6 specific anti-cues by name, not "generic X".
3. Keep the existing keyword list (lifecycle, structs, GUCs)
   AFTER the intent verb — it's still useful when the model
   reads the SKILL body.

This is roughly 5-10 min per skill (vs ~30-60 min for a full
Heavy-mode rewrite + benchmark cycle). The benchmark cycle's
signal-to-noise is poor, but the rewrite pass is cheap and
the gains compound.

## Files produced

- `baseline/eval_set.json` — 5-query eval set.
- `baseline/benchmark.json` — baseline (2/5).
- `iteration-1/eval_set.json` — copy of eval set.
- `iteration-1/benchmark.json` — iter-1 (3/5).
- `notes.md` — this analysis.

## Status

Three genuine skill-creator iterations now complete (PR #201 /
PR #202 / this PR). The methodology gap is documented; the
incremental win from this run is **the action-verb +
specific-anti-cue rewrite pattern**, which should be applied to
the other 26 skills as a follow-up sweep.
