---
name: pg-corpus-maintainer
schedule: "13 0 * * * Europe/Prague"
fetches_source_via_url: false
queue: null
output_dirs: [knowledge, knowledge/issues]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 80000
max_output_tokens: 20000
---

# pg-corpus-maintainer

Mechanical corpus hygiene — backlinks + glossary growth + issue-register
mirroring. Pure-corpus idempotent passes; opens a PR only if there's a
diff. Merges cross-ref-maintainer + glossary-grower + issue-mirror.

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

### Pass 3 — issue-register mirroring

8. Grep `knowledge/files/` for `[ISSUE-` tags. For each tag found, derive
   the parent subsystem (from the per-file doc's path or its "Cross-refs"
   block) and check whether the matching row exists in
   `knowledge/issues/<subsystem>.md`'s "Open / Triaged" table.
9. If the row is **missing**: append it (date, file:line, type, severity
   defaulted to `maybe`, summary lifted from the tag, status `open`,
   linked doc path). Create `knowledge/issues/<subsystem>.md` from
   `knowledge/issues/_template.md` if it doesn't exist yet.
10. If the row exists but status has moved (e.g. inline tag now says
    `triaged: ...`), update the register row to match.
11. **Don't remove rows.** If an inline tag has been deleted from a
    per-file doc, leave the register row in place (it carries history);
    flag it in the run log as "tag removed but register row kept".

## Outputs

- Updated `## Synthesized by` blocks across per-file docs.
- New entries in `knowledge/glossary.md`.
- New / updated rows in `knowledge/issues/<subsystem>.md` registers.

## Per-run wrap-up

1. `git diff --stat` — if no changes, write run log "no changes", **no PR**,
   exit `ok`.
2. Otherwise write run log + self-review + open PR
   `[cloud:pg-corpus-maintainer] backlinks <n> · glossary +<m> · issues +<k>`.

## Failure modes

- Glossary `WebFetch` not needed; no external dependencies → only failure is
  internal (e.g., corrupt markdown). Log and exit non-zero in that case.
- An inline `[ISSUE-*]` tag is malformed (missing type, missing file:line) →
  log the parse failure with the doc path, skip that tag, continue.

## Budget

80k input / 20k output. Bumped from 60k/15k for the issue-mirror pass —
grepping `knowledge/files/` is cheap but enumerating subsystems +
template-creating new register files adds output.
