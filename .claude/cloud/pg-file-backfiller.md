---
name: pg-file-backfiller
schedule: "53 22 * * * Europe/Prague"
fetches_source_via_url: true
queue: progress/_queues/files.md
output_dirs: [knowledge/files, knowledge/issues]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 120000
max_output_tokens: 25000
---

# pg-file-backfiller

Pick the highest-priority uncovered source file(s) from the queue and
write per-file knowledge doc(s), surfacing any potential issues into
the `knowledge/issues/` register as you go.

**Scope (Phase A):** every `.c` / `.h` under `source/src/` + `source/contrib/`.
See `progress/coverage-gaps.md` for the per-directory work queue;
2 564 files target, ~1 647 uncovered as of 2026-06-02.

## Inputs

- `progress/_queues/files.md` — seeded from `progress/coverage-gaps.md`
  in priority order (high-priority dirs first: `src/include/catalog/`,
  `src/backend/utils/`, `src/backend/libpq/`, `src/interfaces/libpq/`,
  `src/bin/`, `src/pl/`). Refill rule: when queue depth < 5, scan
  `progress/coverage-gaps.md` for the next-priority subdir and append
  its uncovered files.
- Anchor SHA from `progress/STATE.md`.

## Per-run recipe

1. Load `pg-claude`, `memory-keeping`. Inspect queue head's path; load the
   subsystem-relevant skill (e.g., path matches `storage/lmgr/` → load
   `locking`; `access/heap/` → `mvcc-and-snapshots`; `optimizer/` →
   `executor-and-planner`; `libpq/` → `replication-overview`; `bin/pg_dump/`
   → `catalog-conventions`; `src/pl/plpgsql/` → `parser-and-nodes`; etc.).
   One subsystem skill per run.
2. Branch: `cloud/pg-file-backfiller/<YYYY-MM-DD>`.
3. Pop head `[pending]` queue entry → `<path>`. Mark `[in-progress:<branch>]`.
4. Fetch the file:
   `https://raw.githubusercontent.com/postgres/postgres/<anchor-sha>/<path>`.
   If `> 4000` lines, chunk via the contents API with range headers (or
   re-fetch full and process in passes — pick whichever fits the budget).
5. Produce `knowledge/files/<path>.md`:
   - Frontmatter: `path`, `anchor_sha`, `loc`, `depth: deep` (or `read`
     for header/small files where deep doesn't add value).
   - **Purpose** (1 paragraph).
   - **Public symbols** — table of exported functions / types with file:line.
   - **Internal landmarks** — key static helpers, state machines, locks.
   - **Invariants & gotchas** — anything a future agent must not break.
   - **Cross-refs** — `[[link]]` into existing corpus.
   - **Potential issues** (NEW — see step 6). Skip the section if none.
6. **Issue surfacing.** While reading, look for the patterns listed in
   `knowledge/issues/README.md`: confirmed/likely correctness or leak
   issues; doc-drift; stale TODO/FIXME/XXX older than ~2 years;
   dead-looking paths; undocumented invariants the code relies on;
   open questions. For each:
   - **Inline tag in the per-file doc** under `## Potential issues`:
     ```
     - **[ISSUE-leak: stack buffer not freed on fast-path return]**
       `nbtsearch.c:1284` — `_bt_search` allocates a stack-local buffer
       but the FAST_PATH branch at line 1290 returns without hitting
       `pfree(stack)` at line 1308. Likely benign (palloc in per-query
       context) but worth a second read.
     ```
   - **Mirror to the subsystem register** at
     `knowledge/issues/<subsystem>.md`. If the register file doesn't
     exist yet, copy `knowledge/issues/_template.md` and customize the
     header. Append a row to the "Open / Triaged" table with status
     `open`, severity per the scale (default `maybe` if uncertain).
   - Be conservative — a noisy register loses value fast. Don't tag
     style nits unless they're systemic; don't tag intentional design
     choices.
7. Try to fit **2-3 small files (≤500 LOC each)** per run when budget
   allows; one large file (>2 000 LOC) is fine standalone. Stop when
   `max_output_tokens / 2` consumed (leave headroom for the run log).
8. Append a row to `progress/files-examined.md` per file processed
   (or upgrade the existing row to `depth: deep`).
9. Mark queue entry `[done:<commit-sha>]`.
10. Write run log + self-review + open PR
    `[cloud:pg-file-backfiller] <path>` (or `<N> files: <dir>` for
    multi-file runs).

## Failure modes

- File deleted upstream (404 at anchor SHA) → mark queue
  `[skipped:deleted]`, pop next. Cap 3 pops/run.
- File too large to fit in budget even chunked → mark `[skipped:oversized]`
  with the LOC, pop next, leave a note in run log so the human can split it
  into per-section docs manually.
- Anchor SHA itself stale → run log notes "fetched against `master` HEAD
  instead of `<anchor>`"; flag for `pg-state-keeper` to bump the anchor.
- A `[ISSUE-*]` tagged that already exists in the register (duplicate)
  → don't re-add; cross-link in the per-file doc to the existing row.

## Budget

120k input / 25k output. Bumped from 80k/15k for the multi-file batch
mode + issue-register writes. One 4 000-line file is still ~70k input.

## Why this changed (2026-06-02)

Phase A decision: scope widened from `src/backend`-focused to full
`src/` + `contrib/` (2 564 files; 1 647 uncovered). Single-file/run
cadence would take 4-5 years to close; batched 2-3-files-per-run mode
brings it to ~18 months at one-routine-per-night. Issue-surfacing
step added so the per-file pass produces durable observation, not just
description. See `sessions/2026-06-02-phase-a-setup.md` for the
rationale.
