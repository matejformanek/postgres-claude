# 2026-06-02 — Phase A setup landed

**Type:** interactive (worktree `ft_corpus_phase_a_setup`).
**Outcome:** Phase A (corpus completeness + issue surfacing) infra
landed. Coverage refreshed; per-directory gap map written; issue
register created; three cloud routines extended.

## Why this happened

After the planner suite (#28) and pg-patch-review v2 (#29) landed,
the user laid out a 4-phase arc:

- **Phase A** — Complete file-by-file docs + issue surface.
- **Phase B** — Developer personas (Tom Lane, Andres Freund, Robert
  Haas, Peter E, Heikki, Álvaro, Tomas V, Nathan B, Michael P, …)
  mined from pgsql-hackers + commits, wired into `pg-patch-review` as
  critic personas and into `pg-feature-plan` as planning lenses.
- **Phase C** — Calibration: exercise + polish until production-ready.
- **Phase D** — PostgreSQL data-leak hardening (the payload).

Each builds on the prior. Phase A is the foundation; the personas in
B need the corpus to be complete enough to reason from; the data-leak
hunt in D needs both the corpus depth and the persona/critic lenses.

User decisions (via AskUserQuestion):

- Scope of "all files": **everything under src/ + contrib/** (2 564 files).
- Issue tracking: **inline tag + register** — `[ISSUE-<type>: ...]` in
  the per-file doc AND a row in `knowledge/issues/<subsystem>.md`.
- Cadence: **both** — cloud routine grinds breadth; foreground sweeps
  accelerate high-value directories.

## What this commit did

### New files (Phase A scaffolding)

| Path | Role |
|---|---|
| `progress/coverage-gaps.md` | Per-directory work queue — every `src/`/`contrib/` subdir with source-vs-doc counts + priority for foreground sweeps |
| `knowledge/issues/README.md` | Tag convention `[ISSUE-<type>: ...]`, severity scale (nit/maybe/likely/confirmed/critical), status workflow (open/triaged/wontfix/submitted/landed), how the register is used downstream |
| `knowledge/issues/_template.md` | Template for `knowledge/issues/<subsystem>.md` per-subsystem registers — created lazily as issues land |
| `knowledge/issues/storage-buffer.md` | Starter register for the calibration subsystem |
| `sessions/2026-06-02-phase-a-setup.md` | This file |

### Modified files

| Path | Change |
|---|---|
| `progress/coverage.md` | Refreshed top-line numbers (917 docs / 2 564 source files = 35.8%); added per-tree breakdown; pointed at coverage-gaps.md |
| `.claude/cloud/pg-file-backfiller.md` | Scope widened beyond `src/backend` to full src/+contrib/; batch 2-3 small files/run when budget allows; added issue-surfacing step (inline tag + register mirror); budget 80k/15k → 120k/25k |
| `.claude/cloud/pg-corpus-maintainer.md` | Added Pass 3 (issue-register mirroring): grep `knowledge/files/` for `[ISSUE-*]` tags, append missing rows to `knowledge/issues/<subsystem>.md`; budget 60k/15k → 80k/20k |
| `.claude/cloud/pg-quality-auditor.md` | Added third ISSUE-triage mode (rotate AUDIT/SKILL/ISSUE by day-of-year mod 3); added failure-to-run defenses for the 2026-06-02 SILENT incident; budget 70k/20k → 80k/20k |
| `.claude/skills/pg-claude/SKILL.md` | Registered `knowledge/issues/` in the corpus tree + routing rules; added `progress/coverage-gaps.md` to the ledger list |
| `progress/STATE.md` | Phase bumped to "Phase A — corpus completeness + issue surfacing"; Next queue rewritten as A active work + B/C/D queued + side concerns |

## The coverage picture (refreshed today)

| Tree | Source | Docs | Coverage |
|---|---:|---:|---:|
| `src/backend` | 906 | 627 | 69.2% |
| `src/include` | 844 | 289 | 34.2% |
| `src/common` | 62 | 1 | 1.6% |
| `src/port` | 64 | 0 | 0.0% |
| `src/interfaces` | 166 | 0 | 0.0% |
| `src/timezone` | 7 | 0 | 0.0% |
| `src/test` | 74 | 0 | 0.0% |
| `src/bin` | 160 | 0 | 0.0% |
| `src/fe_utils` | 18 | 0 | 0.0% |
| `src/pl` | 39 | 0 | 0.0% |
| `contrib` | 210 | 0 | 0.0% |
| **TOTAL** | **2 564** | **917** | **35.8%** |

**Gap: 1 647 files.** At pg-file-backfiller's prior 1/night cadence,
that's >4 years. With batched 2-3/night + foreground sweeps for
high-value dirs, ~18 months realistic.

## Design decisions

### Why a per-directory gap map separate from coverage.md

`coverage.md` is the durable summary — slowly-changing data (subsystem
list + glossary + top-line counts). `coverage-gaps.md` is the **work
queue** — refreshed whenever the count moves by 50 or a dir crosses a
10% boundary. Keeping them separate means cloud routines can pop from
the gaps file without rewriting the summary every night.

### Why both inline tags AND a separate register

The user picked both, and the rationale is the two purposes:

- **Inline tag in `knowledge/files/.../X.c.md`** — a corpus reader
  walking the per-file doc sees the issue in context. Tied to the
  exact `file:line` cite.
- **Per-subsystem register `knowledge/issues/<subsystem>.md`** — lets
  triage scan all of nbtree's open concerns without reading every
  per-file doc. Lets `pg-patch-review` critic A check the relevant
  register before approving a patch in that subsystem.

`pg-corpus-maintainer`'s new Pass 3 does the mirroring automatically so
nobody has to write the row by hand twice.

### Why pg-quality-auditor got a third mode (ISSUE)

The new register needs maintenance — open issues older than 30 days
need re-verification (was it fixed upstream? did line numbers drift?
is the pattern still there?). pg-quality-auditor's existing two modes
(AUDIT long-form docs / SKILL eval regression) had spare capacity. The
mode rotation is now `day-of-year mod 3`.

### Why widen pg-file-backfiller scope and not write a new routine

Same shape (pop queue → fetch source → write per-file doc → register
row). New routine would duplicate failure-modes, budget tuning,
template structure, etc. Widening with the existing recipe is cheaper.

### Why bump budgets across all three cloud routines

The issue-surfacing step adds ~3-5k output tokens per file (a few
inline tags + register-row text). pg-corpus-maintainer's new Pass 3
adds register-row writes. pg-quality-auditor's ISSUE mode adds
per-issue source fetches. Bumping budgets prevents truncation.

### pg-quality-auditor SILENT 2026-06-02 — what I did and didn't fix

The routine didn't write a run log on 2026-06-02. Defenses added:

- Write a `starting` log **before** mode dispatch — so a silent crash
  still leaves evidence.
- Queue refill failures → write partial log + exit `queue-error`,
  don't continue into a mode that can't proceed.
- Stale anchor SHA → warn + continue, don't fail hard.

What I **didn't** fix: the root cause. The actual reason the routine
went silent is still unknown — could be model timeout, could be a
queue-file parse error, could be a permission issue. Pull the
cloud-routine event log next cycle to find out.

## What this commit explicitly does NOT do

- **Doesn't actually document any new files.** This is infra; the
  bulk fill happens in subsequent sessions (cloud + foreground).
- **Doesn't kick off the first foreground sweep.** Queued as next
  active item (`progress/STATE.md` Next §1: src/include/catalog/).
- **Doesn't touch `dev/` or anything outside `postgres-claude/`.**
- **Doesn't fix the actual SILENT root cause** for pg-quality-auditor —
  defenses only.
- **Doesn't seed `progress/_queues/files.md`** from coverage-gaps.md —
  pg-file-backfiller's recipe says it does this lazily, so next cycle
  will populate. If we want pre-seeding to test ASAP, that's a
  separate small commit.

## Followup candidates surfaced

- **Pre-seed `progress/_queues/files.md`** from
  `progress/coverage-gaps.md` priority order so pg-file-backfiller has
  a queue on its next cycle (otherwise its refill kicks in and
  populates lazily).
- **`progress/_gap-script.sh`** — automate the per-dir count
  recompute so `coverage-gaps.md` refreshes can be one command.
- **`pg-quality-auditor` real root cause** for the SILENT incident —
  pull cloud event log.
- **Issue-tag examples in `coding-style`** — give the routine some
  examples of high-quality issue tags so it doesn't generate noise.

## Repository state after this commit

- 3 new files in `knowledge/issues/`, 1 new file in `progress/`, 1
  session log, 3 cloud-routine edits, master nav + STATE.md edits.
- No changes to `dev/`, `knowledge/architecture/`, `knowledge/files/`,
  `knowledge/subsystems/`, or any skill outside the cloud recipes +
  pg-claude master.

## Commit message for this work

```
ft(corpus): land Phase A setup (coverage gaps + issue register + cloud)

Pivot from tooling-buildout phase to corpus-completeness phase. The
user's 4-phase arc: A=fill src/+contrib/ per-file docs and surface
issues, B=mine developer personas from pgsql-hackers, C=calibrate
planner+review skills, D=PostgreSQL data-leak hardening.

This commit is Phase A infra only (no per-file doc additions):

- Refresh coverage.md against current state (917/2 564 docs = 35.8%
  coverage; 1 647-file gap).
- Write coverage-gaps.md — per-directory work queue keyed for the
  cloud routine + foreground sweeps.
- Create knowledge/issues/ skeleton — README (tag convention, severity
  scale, workflow), template, starter for storage-buffer.
- Extend pg-file-backfiller cloud routine: scope src/+contrib/, batch
  2-3 small files/run, surface [ISSUE-*] tags inline + mirror to
  per-subsystem register, budgets bumped.
- Extend pg-corpus-maintainer with Pass 3 (issue-register mirroring).
- Extend pg-quality-auditor with third ISSUE-triage mode and
  failure-to-run defenses (the 2026-06-02 SILENT incident).
- Register knowledge/issues/ + coverage-gaps.md in master pg-claude
  nav. STATE.md phase + Next queue rewritten around A/B/C/D.

Session: sessions/2026-06-02-phase-a-setup.md
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
