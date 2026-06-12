---
name: pg-community-pulse
schedule: "11 20 * * * Europe/Prague"
fetches_source_via_url: false
queue: null
output_dirs: [knowledge/community/threads, knowledge/community/commitfest, knowledge/community/blog-roundup]
skills_required: [pg-claude, memory-keeping, patch-submission, review-checklist]
max_input_tokens: 250000
max_output_tokens: 60000
---

# pg-community-pulse

One daily 3-section PR covering pgsql-hackers, CommitFest, and Planet
Postgres. Merges hackers-thread-miner + commitfest-scanner +
planet-postgres-aggregator into a single review-able PR.

## Inputs

- pgsql-hackers archive: `https://www.postgresql.org/list/pgsql-hackers/since/<iso-24h-ago>`
- CommitFest page for current cycle: `https://commitfest.postgresql.org/`
  (follow the link to the open cycle; persist the cycle slug between runs in
  `progress/cloud-routines/pg-community-pulse/_cf-cycle.txt` for stable
  yesterday-snapshot diffing).
- Planet feed: `https://planet.postgresql.org/rss20.xml`.

## Per-run recipe

1. Load skills `pg-claude`, `memory-keeping`, `patch-submission`,
   `review-checklist`.
2. Branch: `cloud/pg-community-pulse/<YYYY-MM-DD>`.
3. `WebFetch` each of the three sources. Record the URL and HTTP status in
   the run log's `sources` block.
4. **Hackers section** — pick **8-12** threads from the last 24h that look
   internals-relevant (filter on keywords: WAL, lock, MVCC, planner, executor,
   buffer, vacuum, replication, etc. — broaden to also catch: AIO, IO concurrency,
   parallel query, partition pruning, logical replication, BRR/SSL, libpq, oauth,
   pg_dump/restore, security, JIT, table AM). For each:
   - Subject line, archive URL, 3-bullet summary, "Why it matters" sentence,
     `[[link]]` into existing corpus where applicable.
   - Output → `knowledge/community/threads/<YYYY-MM-DD>.md`.
5. **CommitFest section** — diff today's listing vs yesterday's stored
   snapshot in `knowledge/community/commitfest/<cycle>-<yesterday>.md`:
   - New entries added, entries moved status, entries closed/committed.
   - One-line note per change with patch author + URL.
   - Output → `knowledge/community/commitfest/<cycle>-<YYYY-MM-DD>.md`.
6. **Blog roundup** — pick **6-10** posts from planet RSS published in the last
   24h. For each: title, URL, 2-bullet TL;DR, "Read if you care about <X>"
   tag.
   - Output → `knowledge/community/blog-roundup/<YYYY-MM-DD>.md`.
7. Write the run log at
   `progress/cloud-routines/pg-community-pulse/<YYYY-MM-DD>.md`.
8. Self-review against `review-checklist`.
9. Open PR `[cloud:pg-community-pulse] hackers <n> · cf delta · planet <n>`.

## Failure modes

- Any one of the three sources unreachable → write the other two, note the
  gap in run log under `skipped`, still open PR.
- All three unreachable → no PR, `exit_reason: error: all-sources-down`.

## Budget

250k input / 60k output (matches frontmatter; bumped 2026-06-02 evening and
reconciled with the footer 2026-06-12 — the prior "100k/30k" line was
caps-on-the-prior-budget and was making the agent stop at half budget).
Cap per source: 60k input. **Target**: hackers section grows from 3-5
threads to **8-12** at the new budget; planet roundup grows from 3-5 to
**6-10**; CommitFest diff is whatever the day produced. The recipe is
sweep-driven — fill until `output_tokens_so_far ≥ 0.70 *
max_output_tokens` per `_loader.md` §5.
