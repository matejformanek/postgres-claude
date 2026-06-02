---
name: pg-file-backfiller
schedule: "53 22 * * * Europe/Prague"
fetches_source_via_url: true
queue: progress/_queues/files.md
output_dirs: [knowledge/files, knowledge/issues]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 400000
max_output_tokens: 100000
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
7. **Fill the budget.** With the 100k output ceiling, target **10-20 small
   files (≤500 LOC each)** per run, OR **3-5 medium files (500-2 000 LOC)**,
   OR **1-2 large files (>2 000 LOC)**. Pop the next queue item after each
   doc as long as `output_tokens_so_far < 0.70 * max_output_tokens` AND the
   queue still has `[pending]`. Only stop at `0.85 *` for budget-cap, or
   when queue is empty (record `exit_reason: queue-empty`). The A1
   catalog-headers sweep landed 11-13 files per agent in ~80k tokens; this
   routine should hit similar volume nightly. **An empty-handed run is a
   process bug** — flag in the run log if you exit at < 30% budget consumed.
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

400k input / 100k output. Bumped from 120k/25k after the A1 catalog-headers
sweep (2026-06-02 evening) demonstrated that 12-13 files fit comfortably in
~80k tokens; the cloud routine should match that throughput nightly. One
4 000-line source file is still ~70k input.

## Why this changed (2026-06-02)

- **Phase A decision** (earlier 2026-06-02): scope widened from `src/backend`-
  focused to full `src/` + `contrib/` (2 564 files; 1 647 uncovered). Issue-
  surfacing step added.
- **Throughput bump** (2026-06-02 evening): the routine was still budgeted
  for 2-3 files/run, which at one-routine-per-night needs ~18 months to
  close the gap. With 100k output budget and an explicit "fill the budget"
  loop the realistic throughput is 10-20 small files/run, closing Phase A
  in **~3-4 months** at the same nightly cadence. See
  `sessions/2026-06-02-cloud-throughput-bump.md`.
