# `debugging` skill — eval summary (iter-1 → iter-2)

## Scores

| Iteration | with_skill | baseline | uplift |
| --------- | ---------- | -------- | ------ |
| iter-1    | 22/22 (100%) | 15/22 (68.2%) | +7  |
| iter-2    | 22/22 (100%) | 16/22 (72.7%) | +6  |

**Delta: with_skill unchanged (saturated at 100%); baseline +1 (mostly
noise — the model spontaneously cited the project's `dev/install-debug`
path in eval 1 this run, but did not cite it in iter-1).**

## What changed in the skill (iter-1 → iter-2)

Five of seven proposed edits applied; two skipped with rationale logged
in `iteration-2/edits-applied.md`.

- **E1 applied** — `/pg-attach` and `/pg-tail-log` callout at top of §2.
- **E2 applied** — SIGUSR1 silencing promoted to its own sub-heading
  `### First command after every attach`, with both lldb and gdb forms
  side by side.
- **E3 applied** — new §5.1 "Trapping every error" with explicit lldb +
  gdb commands. Verified `ERROR = 21` in `source/src/include/utils/elog.h:53`
  and used the correct value (proposal had said `20`).
- **E4 applied** — §8 restructured into Prerequisites (with expected
  output per step) and Caveats (Apple-signed binaries, missing-sysctl
  fallback).
- **E5 applied** — 4-row decision-rule table at top of §3 mapping
  symptom (pre-shmem / forked-startup / worker / live query) → tool
  (--single / -W / spin-loop / lldb -p).
- **E6 skipped** — line-citation pinning is tracking work outside the
  SKILL.md surface; not visible to evals.
- **E7 skipped** — would link to a nonexistent
  `knowledge/idioms/log_min_messages.md`.

## Where the saturated score hides real improvement

The grading rubric saturated with_skill at 22/22 in iter-1 already, so
the **score** can't show iter-2 gains. The qualitative improvements
visible in the iter-2 with_skill answers but not credited by the rubric:

- Eval 1 now leads with `/pg-attach` and `/pg-tail-log` (project
  shortcuts) before the manual recipe — actionable in one step.
- Eval 2 now gives explicit `errfinish` + `edata->elevel >= 21` filter
  with the correct ERROR constant.
- Eval 3 now opens with the decision table; the "InitPostgres →
  --single" branch reads as the conclusion rather than the body.

These are answer-quality improvements that would matter to a human
reader but don't move the binary-assertion bar.

## Baseline behavior

Baseline (no skill) hits the well-known parts cleanly: lldb-vs-gdb on
macOS, `pg_backend_pid`, `lldb -p`, `ExecutorRun`, single-user mode,
core-dump basics. It consistently misses the PG-specific knobs:

- SIGUSR1 silencing (signal traffic on attach).
- `pprint(Node *)` via `expr` in the debugger.
- `errfinish` as the universal `ereport` funnel.
- macOS hardened-binary core suppression.
- Single-user mode's newline-terminator quirk and `-j` flag.
- `elog(LOG, …)` inside a waitpoint to surface the PID.

That set is exactly what the skill is optimized to deliver and where its
incremental value lives. The skill is doing its job — the rubric just
can't show it numerically once with_skill saturates.

## Recommendation

Skill is production-ready for these three eval shapes. To get further
signal, future iterations need **harder evals** — e.g. parallel-worker
debugging, recovery-path stepping, ExecAppend vs ExecModifyTable
disambiguation — that would unsaturate with_skill and let further edits
show up as score deltas.
