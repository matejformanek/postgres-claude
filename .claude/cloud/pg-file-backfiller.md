---
name: pg-file-backfiller
schedule: "53 22 * * * Europe/Prague"
fetches_source_via_url: true
queue: progress/_queues/files.md
output_dirs: [knowledge/files]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 80000
max_output_tokens: 15000
---

# pg-file-backfiller

Pick the highest-priority uncovered source file from the registry and write
its per-file knowledge doc.

## Inputs

- `progress/_queues/files.md` — seeded by walking
  `progress/files-examined.md` for rows with `depth in [skim, unread]`,
  ordered by `LOC × subsystem-priority` descending. Refill rule same.
- Anchor SHA from `progress/STATE.md`.

## Per-run recipe

1. Load `pg-claude`, `memory-keeping`. Inspect queue head's path; load the
   subsystem-relevant skill (e.g., path matches `storage/lmgr/` → load
   `locking`; `access/heap/` → `mvcc-and-snapshots`; `optimizer/` →
   `executor-and-planner`; etc.). One subsystem skill per run.
2. Branch: `cloud/pg-file-backfiller/<YYYY-MM-DD>`.
3. Pop head `[pending]` queue entry → `<path>`. Mark `[in-progress:<branch>]`.
4. Fetch the file:
   `https://raw.githubusercontent.com/postgres/postgres/<anchor-sha>/<path>`.
   If `> 4000` lines, chunk via the contents API with range headers (or
   re-fetch full and process in passes — pick whichever fits the budget).
5. Produce `knowledge/files/<path>.md`:
   - Frontmatter: `path`, `anchor_sha`, `loc`, `depth: deep`.
   - **Purpose** (1 paragraph).
   - **Public symbols** — table of exported functions / types with file:line.
   - **Internal landmarks** — key static helpers, state machines, locks.
   - **Invariants & gotchas** — anything a future agent must not break.
   - **Cross-refs** — `[[link]]` into existing corpus.
6. Append a row to `progress/files-examined.md` (or upgrade the existing row
   to `depth: deep`).
7. Mark queue entry `[done:<placeholder>]`.
8. Write run log + self-review + open PR
   `[cloud:pg-file-backfiller] <path>`.

## Failure modes

- File deleted upstream (404 at anchor SHA) → mark queue
  `[skipped:deleted]`, pop next. Cap 3 pops/run.
- File too large to fit in budget even chunked → mark `[skipped:oversized]`
  with the LOC, pop next, leave a note in run log so the human can split it
  into per-section docs manually.

## Budget

80k input / 15k output. One file ≤ 4000 lines is ~50-70k input typically.
