---
name: pg-extension-anthropologist
schedule: "7 22 * * * Europe/Prague"
fetches_source_via_url: true
queue: progress/_queues/extensions.md
output_dirs: [knowledge/ideologies]
skills_required: [pg-claude, memory-keeping, extension-development, catalog-conventions, access-method-apis, coding-style]
max_input_tokens: 250000
max_output_tokens: 60000
---

# pg-extension-anthropologist

Capture how popular PG extensions diverge from core Postgres design.
**Process extensions in a loop until budget is consumed** (per `_loader.md`
§5 "Fill the budget"); aim for 2-4 extensions per run with the 60k output
budget, more for smaller extensions.

## Inputs

- `progress/_queues/extensions.md` — hand-seeded with `owner/repo branch
  manifest=[paths]` lines. Refills when empty via `gh search topics
  postgresql-extension --limit 50` (filter to repos with > 500 stars not
  already in `knowledge/ideologies/`).

## Per-run recipe

1. Load skills `pg-claude`, `memory-keeping`, `extension-development`,
   `catalog-conventions`, `access-method-apis`, `coding-style`.
2. Branch: `cloud/pg-extension-anthropologist/<YYYY-MM-DD>`.
3. **Loop** until `output_tokens_so_far ≥ 0.70 * max_output_tokens` OR queue
   is empty. Per iteration:

   a. Pop the head `[pending]` queue entry; mark `[in-progress:<branch>]`. Entry
      format: `owner/repo branch=<ref> files=README.md,ARCHITECTURE.md,...`.
   b. Tree listing (for header/file discovery):
      `https://api.github.com/repos/<owner>/<repo>/git/trees/<branch>?recursive=1`.
   c. Fetch each manifest file via
      `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`.
   d. Produce `knowledge/ideologies/<extension>.md` covering:
      - **Domain & purpose** — one paragraph.
      - **How it hooks into PG** — which APIs (hooks, AMs, BG workers,
        `_PG_init`, custom plan nodes, ...).
      - **Where it diverges from core idioms** — memory contexts, catalog
        conventions, locking, WAL/replication implications.
      - **Notable design decisions** with file:line cites into the ext repo.
      - **Links into corpus** — `[[link]]` to relevant `knowledge/idioms/...`,
        `knowledge/architecture/...`, `knowledge/subsystems/...` notes.
   e. Mark queue entry `[done:<placeholder>]`; the merger rewrites with the
      merge SHA.
   f. **Check budget** — if `output_tokens_so_far < 0.70 * max_output_tokens`
      AND queue has more `[pending]`, continue loop with the next extension.

   **Parallel fanout (recommended, added 2026-06-12)**: when the queue head
   holds ≥ 3 extensions of similar shape (each ~one manifest worth of files,
   no shared cross-cuts), pop them up front and dispatch each to a sub-agent
   — brief per `memory: foreground-sweep-pattern` ("paths RELATIVE to repo
   root", one extension per agent, return the `knowledge/ideologies/<ext>.md`
   doc). Sequential mode is correct when extensions are large (Citus-class)
   and need the full input budget.

4. Write run log + self-review + open PR
   `[cloud:pg-extension-anthropologist] <N> extensions: <list>`.

## Failure modes

- Extension repo 404 / branch missing → mark queue entry `[skipped:404]`,
  pop the next one. No special cap — let the budget loop handle exit.
- Manifest file 404 → log and continue with the files that did fetch; note
  the gap in the ideology doc's "Sources" footer.
- ≥ 3 consecutive 404s or fetch errors → exit `queue-error`.

## Budget

250k input / 60k output. Manifests typically run ~30-50k input per
extension; output ~10-20k per ideology doc → 3-4 extensions per run with
the new budget.
