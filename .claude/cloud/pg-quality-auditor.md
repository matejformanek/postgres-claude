---
name: pg-quality-auditor
schedule: "31 23 * * * Europe/Prague"
fetches_source_via_url: true
queue: [progress/_queues/audits.md, progress/_queues/skills.md, progress/_queues/issues.md]
output_dirs: [knowledge, knowledge/issues, skill-evals]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 250000
max_output_tokens: 60000
---

# pg-quality-auditor

Three-mode rotation: audit a long-form doc claim, re-run a skill eval,
or triage open issues in the issue register. All three verify
"yesterday's claim still holds today" with the same shape. Merges
stale-claim-auditor + skill-regression-runner + issue-triage.

## Inputs

- `progress/_queues/audits.md` — list of `knowledge/architecture/*.md`,
  `knowledge/subsystems/*.md`, `knowledge/data-structures/*.md`,
  `knowledge/idioms/*.md` paths.
- `progress/_queues/skills.md` — skill slugs from `.claude/skills/`
  (currently 26).
- `progress/_queues/issues.md` — auto-seeded from
  `knowledge/issues/<subsystem>.md` registers: any `open` row whose
  date is older than 30 days. Refilled when empty.
- Anchor SHA from `progress/STATE.md`.

## Per-run recipe

1. Load `pg-claude`, `memory-keeping`.
2. Branch: `cloud/pg-quality-auditor/<YYYY-MM-DD>`.
3. Pick **primary mode** by `day-of-year mod 3`:
   - **0 → AUDIT mode** (long-form doc).
   - **1 → SKILL mode** (skill regression).
   - **2 → ISSUE mode** (issue-register triage).
4. **Loop in the primary mode** until `output_tokens_so_far ≥ 0.70 *
   max_output_tokens` OR that mode's queue is empty. Target **5-10 items
   per run** with the 60k output budget (vs prior 1 item/run). If primary
   mode's queue empties before budget is consumed, rotate to the next
   mode and continue. Per `_loader.md` §5 "Fill the budget" — don't exit
   after one item if budget remains.

### AUDIT mode

1. Pop head `[pending]` from `audits.md`.
2. Open the doc; pick one section densest in `source/<path>:<line>` cites.
3. For each cite in that section, fetch `<path>` via
   `raw.githubusercontent.com/postgres/postgres/<anchor-sha>/<path>` and
   verify the cited line still matches the claim.
4. If all cites hold → write run log "audit clean", **no PR**, push queue
   entry back to tail as `[pending]` with a `verified=<date>` annotation.
5. If drift found → patch the doc with corrected cites/claims and open PR
   `[cloud:pg-quality-auditor:audit] <doc-name>`.

### SKILL mode

1. Pop head `[pending]` from `skills.md`.
2. Load `.claude/skills/<skill>/SKILL.md` and its iter-1 eval suite (under
   `skill-evals/<skill>/` if present).
3. Rerun the eval. For assertions hinging on source cites, fetch those
   files via URL and re-verify.
4. Compute pass-rate vs the previous run.
5. If pass-rate drop > 5pp → write
   `skill-evals/<skill>/regression-<YYYY-MM-DD>.md` with failing
   assertions, open PR `[cloud:pg-quality-auditor:skill] <skill>
   regression`.
6. Otherwise → run log only, no PR.

### ISSUE mode

1. Pop head `[pending]` from `issues.md` (an open issue row older than
   30 days).
2. Re-fetch the source file at the cited `<path>:<line>` via
   `raw.githubusercontent.com/postgres/postgres/<anchor-sha>/<path>`.
3. Determine the issue's current state:
   - **Still present** → bump the register row's `triaged: <date>`
     annotation; status stays `open`. No PR unless severity should
     change.
   - **Fixed upstream** (the line / pattern no longer matches) → update
     register row status to `landed` with a `git log -S` lookup for the
     resolving commit SHA. Open PR `[cloud:pg-quality-auditor:issue]
     <subsystem>: <N> resolved`.
   - **Reproducer drifted** (line numbers off but pattern still there
     elsewhere in the file) → patch the register row's file:line and
     the inline tag in the per-file doc; status stays `open`. Open PR.
4. If the issue's per-file doc tag is missing (someone removed it but
   the register row remains) → re-add the inline tag and note in the
   run log.

## Failure modes

- No drift / no regression / no register movement → no PR, log notes
  "clean".
- Queue empty → refill from source-of-truth list, retry once; if still
  empty exit `queue-empty`.
- `knowledge/issues/` directory empty (no registers yet, Phase A still
  early) → ISSUE mode short-circuits to AUDIT mode for that run.

## Failure-to-run defenses (added 2026-06-02)

The routine went SILENT on 2026-06-02 (no log written at all). Defenses:

- Write `progress/cloud-routines/pg-quality-auditor/<YYYY-MM-DD>.md`
  with `exit_reason: starting` **before** entering mode dispatch — so a
  silent crash still leaves evidence.
- If any queue refill fails, write a partial log + exit `queue-error`
  rather than continuing into a mode that can't proceed.
- If anchor SHA is older than 7 days (stale), log a warning and continue
  rather than fail hard — Phase A reviews tolerate slight drift.

## Budget

250k input / 60k output. Bumped 2026-06-02 evening per the "fill the
budget" directive (`_loader.md` §5). At ~5-8k output per AUDIT/SKILL/ISSUE
item, supports **5-10 items per run** vs prior single-item cadence —
which means the audit queue (currently ~24 long-form docs) cycles every
3-5 days instead of every 24+ days, and the issue register triage keeps
up with growth.
