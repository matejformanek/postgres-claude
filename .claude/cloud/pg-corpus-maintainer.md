---
name: pg-corpus-maintainer
schedule: "13 0 * * * Europe/Prague"
fetches_source_via_url: false
queue: null
output_dirs: [knowledge]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 60000
max_output_tokens: 15000
---

# pg-corpus-maintainer

Mechanical corpus hygiene — backlinks + glossary growth. Pure-corpus
idempotent passes; opens a PR only if there's a diff. Merges
cross-ref-maintainer + glossary-grower.

## Inputs

- The entire `knowledge/` tree (read-only walk).
- `knowledge/glossary.md` — created on first run if absent.

## Per-run recipe

1. Load `pg-claude`, `memory-keeping`.
2. Branch: `cloud/pg-corpus-maintainer/<YYYY-MM-DD>`.

### Pass 1 — backlinks

3. Run the backlinks reverse-index pass: for every `[[...]]` reference in
   long-form notes (`knowledge/architecture/`, `knowledge/subsystems/`,
   `knowledge/idioms/`, `knowledge/data-structures/`), append an upward
   pointer to the referenced per-file doc's `## Synthesized by` block.
4. Skip per-file docs where the pointer already exists (idempotent).
5. Touch only files where the block changed.

### Pass 2 — glossary growth

6. Walk `knowledge/` and tokenize. For each candidate term (CamelCase
   identifiers, ALL_CAPS macros, lowercase jargon like "snapshot",
   "tuple", "xid"), check if it's defined in `knowledge/glossary.md`.
7. Take the top-15 most-frequent undefined terms; for each, write a 2-3
   sentence entry citing the file:line of its strongest definition site
   in corpus (no source fetch needed — use existing per-file docs as the
   primary definition source).

## Outputs

- Updated `## Synthesized by` blocks across per-file docs.
- New entries in `knowledge/glossary.md`.

## Per-run wrap-up

1. `git diff --stat` — if no changes, write run log "no changes", **no PR**,
   exit `ok`.
2. Otherwise write run log + self-review + open PR
   `[cloud:pg-corpus-maintainer] backlinks <n> · glossary +<m>`.

## Failure modes

- Glossary `WebFetch` not needed; no external dependencies → only failure is
  internal (e.g., corrupt markdown). Log and exit non-zero in that case.

## Budget

60k input / 15k output. The backlinks pass is mostly small edits; glossary
growth is the main output consumer.
