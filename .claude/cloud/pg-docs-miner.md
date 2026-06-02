---
name: pg-docs-miner
schedule: "47 20 * * * Europe/Prague"
fetches_source_via_url: false
queue: [progress/_queues/wiki.md, progress/_queues/docs.md]
output_dirs: [knowledge/wiki-distilled, knowledge/docs-distilled, knowledge/community]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 200000
max_output_tokens: 50000
---

# pg-docs-miner

Distill PG wiki pages + official-docs chapters into the corpus. **Process in
a loop until budget is consumed** (per `_loader.md` §5 "Fill the budget");
aim for **3-5 wiki pages + 3-5 docs chapters per run** with the 50k output
budget.

## Inputs

- `progress/_queues/wiki.md` — seeded from `knowledge/community/wiki-index.md`
  entries not yet distilled.
- `progress/_queues/docs.md` — seeded by walking the official docs ToC at
  `https://www.postgresql.org/docs/current/index.html`.

## Per-run recipe

1. Load skills `pg-claude` and `memory-keeping`.
2. Branch: `cloud/pg-docs-miner/<YYYY-MM-DD>`.
3. **Loop** until `output_tokens_so_far ≥ 0.70 * max_output_tokens` OR both
   queues empty. Per iteration:

   a. Pick the next source — alternate wiki/docs queues to keep balance, OR
      use parity of iteration count (even → wiki, odd → docs).
   b. Pop the head `[pending]` entry from the chosen queue; mark
      `[in-progress:<branch>]`. Skip to next queue if this one is empty.
   c. `WebFetch` the page (wiki URL or
      `postgresql.org/docs/current/<chapter>.html`).
   d. Distill into a markdown doc with:
      - YAML frontmatter (`source_url`, `fetched_at`, `anchor_sha`).
      - 5-15 bullet points capturing the *non-obvious* claims.
      - "Links into corpus" section with `[[file:line]]` references to
        existing `knowledge/files/...` and `knowledge/subsystems/...` notes.
      - Citations: every claim has either a source-URL anchor or a
        `source/<path>:<line>` reference (verified against anchor SHA in
        STATE.md via `raw.githubusercontent.com` if needed for a one-off check).
   e. Write the output file:
      - `knowledge/wiki-distilled/<slug>.md`, OR
      - `knowledge/docs-distilled/<chapter>.md`.
   f. If wiki: update the row in `knowledge/community/wiki-index.md`
      (status column → "distilled <date>").
   g. Mark queue entry `[done:<pending-merged-sha>]`.
   h. **Check budget** — if `output_tokens_so_far < 0.70 *
      max_output_tokens` AND either queue has more `[pending]`, continue
      loop.

4. Write `progress/cloud-routines/pg-docs-miner/<YYYY-MM-DD>.md` with the
   standard fields (include the per-source list).
5. Self-review against `.claude/skills/review-checklist/SKILL.md`.
6. Open PR `[cloud:pg-docs-miner] <N> wiki + <M> docs`.

## Failure modes

- `WebFetch` returns 429 / 5xx → log status to `sources`, mark that queue
  entry back to `[pending]`, continue loop with the next source. If ≥ 3
  consecutive 429s set `exit_reason: rate-limited` and exit early.
- Either queue empty → drain the other one; refill from seed rule (re-walk
  wiki-index / docs ToC) on next run. If both empty, note in run log and
  exit `queue-empty`.

## Budget

200k input / 50k output. Cap each `WebFetch` at ~15k tokens (one chapter
page is ~5-10k typical; truncate at headers if oversized). At ~5-7k output
per distilled doc, the 50k budget supports 6-10 distillations per run.
