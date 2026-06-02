---
name: pg-extension-anthropologist
schedule: "7 22 * * * Europe/Prague"
fetches_source_via_url: true
queue: progress/_queues/extensions.md
output_dirs: [knowledge/ideologies]
skills_required: [pg-claude, memory-keeping, extension-development, catalog-conventions, access-method-apis, coding-style]
max_input_tokens: 70000
max_output_tokens: 20000
---

# pg-extension-anthropologist

Pick one popular PG extension per run and capture how its design diverges
from core Postgres.

## Inputs

- `progress/_queues/extensions.md` — hand-seeded with `owner/repo branch
  manifest=[paths]` lines. Refills when empty via `gh search topics
  postgresql-extension --limit 50` (filter to repos with > 500 stars not
  already in `knowledge/ideologies/`).

## Per-run recipe

1. Load skills `pg-claude`, `memory-keeping`, `extension-development`,
   `catalog-conventions`, `access-method-apis`, `coding-style`.
2. Branch: `cloud/pg-extension-anthropologist/<YYYY-MM-DD>`.
3. Pop the head `[pending]` queue entry; mark `[in-progress:<branch>]`. Entry
   format: `owner/repo branch=<ref> files=README.md,ARCHITECTURE.md,...`.
4. Tree listing (for header/file discovery):
   `https://api.github.com/repos/<owner>/<repo>/git/trees/<branch>?recursive=1`.
5. Fetch each manifest file via
   `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`.
6. Produce `knowledge/ideologies/<extension>.md` covering:
   - **Domain & purpose** — one paragraph.
   - **How it hooks into PG** — which APIs (hooks, AMs, BG workers,
     `_PG_init`, custom plan nodes, ...).
   - **Where it diverges from core idioms** — memory contexts, catalog
     conventions, locking, WAL/replication implications.
   - **Notable design decisions** with file:line cites into the ext repo.
   - **Links into corpus** — `[[link]]` to relevant `knowledge/idioms/...`,
     `knowledge/architecture/...`, `knowledge/subsystems/...` notes.
7. Mark queue entry `[done:<placeholder>]`; the merger rewrites with the
   merge SHA.
8. Write run log + self-review + open PR
   `[cloud:pg-extension-anthropologist] <extension>`.

## Failure modes

- Extension repo 404 / branch missing → mark queue entry `[skipped:404]`,
  pop the next one. Cap at 2 pops per run to bound budget.
- Manifest file 404 → log and continue with the files that did fetch; note
  the gap in the ideology doc's "Sources" footer.

## Budget

70k input / 20k output. Manifests should stay under ~30k input combined.
