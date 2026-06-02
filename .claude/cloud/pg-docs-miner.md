---
name: pg-docs-miner
schedule: "47 20 * * * Europe/Prague"
fetches_source_via_url: false
queue: [progress/_queues/wiki.md, progress/_queues/docs.md]
output_dirs: [knowledge/wiki-distilled, knowledge/docs-distilled, knowledge/community]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 60000
max_output_tokens: 20000
---

# pg-docs-miner

Distill one PG wiki page AND one official-docs chapter per run into the corpus.
Replaces the earlier wiki-page-distiller + docs-chapter-distiller pair.

## Inputs

- `progress/_queues/wiki.md` — seeded from `knowledge/community/wiki-index.md`
  entries not yet distilled.
- `progress/_queues/docs.md` — seeded by walking the official docs ToC at
  `https://www.postgresql.org/docs/current/index.html`.

## Per-run recipe

1. Load skills `pg-claude` and `memory-keeping`.
2. Branch: `cloud/pg-docs-miner/<YYYY-MM-DD>`.
3. Pop the head `[pending]` entry from `wiki.md`; mark `[in-progress:<branch>]`.
4. Pop the head `[pending]` entry from `docs.md`; mark `[in-progress:<branch>]`.
5. Pick "primary" of the two by parity of day-of-year (even → wiki, odd → docs);
   spend ~60% of output budget on primary.
6. `WebFetch` each page (wiki URL or `postgresql.org/docs/current/<chapter>.html`).
7. Distill each into a markdown doc with:
   - YAML frontmatter (`source_url`, `fetched_at`, `anchor_sha`).
   - 5-15 bullet points capturing the *non-obvious* claims.
   - "Links into corpus" section with `[[file:line]]` references to existing
     `knowledge/files/...` and `knowledge/subsystems/...` notes.
   - Citations: every claim has either a source-URL anchor or a
     `source/<path>:<line>` reference (verified against anchor SHA in STATE.md
     via `raw.githubusercontent.com` if needed for a one-off check).
8. Write outputs:
   - `knowledge/wiki-distilled/<slug>.md`
   - `knowledge/docs-distilled/<chapter>.md`
9. Update the row for the wiki entry in `knowledge/community/wiki-index.md`
   (status column → "distilled <date>").
10. Mark both queue entries `[done:<pending-merged-sha>]` (the merger updates
    SHA on merge — leave a placeholder marker the merger rewrites).
11. Write `progress/cloud-routines/pg-docs-miner/<YYYY-MM-DD>.md` with the
    standard fields.
12. Self-review against `.claude/skills/review-checklist/SKILL.md`.
13. Open PR `[cloud:pg-docs-miner] <wiki-slug> + <docs-chapter>`.

## Failure modes

- `WebFetch` returns 429 / 5xx → log status to `sources`, set `exit_reason:
  rate-limited`, exit 0 with no PR. Queue entries stay `[in-progress]` →
  next run reclaims them.
- Either queue empty → refill from its seed rule (re-walk wiki-index / docs
  ToC). If still empty, run with whichever queue has work and note the gap.

## Budget

60k input / 20k output. Cap each `WebFetch` at ~15k tokens (one chapter page
is ~5-10k typical; truncate at headers if oversized).
