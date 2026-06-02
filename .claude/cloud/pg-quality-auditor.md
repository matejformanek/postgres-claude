---
name: pg-quality-auditor
schedule: "31 23 * * * Europe/Prague"
fetches_source_via_url: true
queue: [progress/_queues/audits.md, progress/_queues/skills.md]
output_dirs: [knowledge, skill-evals]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 70000
max_output_tokens: 20000
---

# pg-quality-auditor

Round-robin between auditing a long-form doc claim and re-running a skill
eval. Merges stale-claim-auditor + skill-regression-runner — both verify
"yesterday's claim still holds today" with the same shape.

## Inputs

- `progress/_queues/audits.md` — list of `knowledge/architecture/*.md`,
  `knowledge/subsystems/*.md`, `knowledge/data-structures/*.md`,
  `knowledge/idioms/*.md` paths.
- `progress/_queues/skills.md` — the 21 skill slugs from `.claude/skills/`.
- Anchor SHA from `progress/STATE.md`.

## Per-run recipe

1. Load `pg-claude`, `memory-keeping`.
2. Branch: `cloud/pg-quality-auditor/<YYYY-MM-DD>`.
3. Pick mode by parity of day-of-year:
   - **Even → AUDIT mode** (long-form doc).
   - **Odd → SKILL mode** (skill regression).

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

## Failure modes

- No drift / no regression → no PR, log notes "clean".
- Queue empty → refill from source-of-truth list, retry once; if still
  empty exit `queue-empty`.

## Budget

70k input / 20k output.
