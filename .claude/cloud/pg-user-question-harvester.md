---
name: pg-user-question-harvester
schedule: "47 0 * * * Europe/Prague"
fetches_source_via_url: false
queue: null
output_dirs: [knowledge/community/user-questions]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 200000
max_output_tokens: 50000
---

# pg-user-question-harvester

Pull recent internals-flavored questions from the PostgreSQL mailing-list
archives. Tag each with which existing skill *should* answer it. Skills never
tagged over many days are dead-code candidates.

> Source note: the original sources (dba.stackexchange.com, r/PostgreSQL) are
> unreachable from the cloud sandbox — their CDNs reject datacenter/non-browser
> fetches with HTTP 403 (anti-bot, not Anthropic's egress; even WebFetch and the
> official `api.stackexchange.com` are refused). The pgsql mailing-list archives
> on `www.postgresql.org` serve the same purpose (real users asking internals
> questions), are reliably reachable, and need no auth.

## Inputs

- PostgreSQL mailing-list archives (HTML, on the reachable `www.postgresql.org`):
  - `https://www.postgresql.org/list/pgsql-general/` — general user Q&A
  - `https://www.postgresql.org/list/pgsql-performance/` — performance/tuning Qs
  - `https://www.postgresql.org/list/pgsql-hackers/` — internals discussion
  Fetch each list page, follow into the current month (e.g.
  `.../pgsql-general/<YYYY>/<MM>/`), and read recent thread subjects + opening
  messages. Filter to the last 7 days and internals-flavored keywords: WAL,
  lock, MVCC, vacuum, planner, executor, buffer, replication, snapshot, xid.
- Skill descriptions: lazy-load frontmatter `description:` field from each
  `.claude/skills/*/SKILL.md` for tagging.

## Per-run recipe

1. Load `pg-claude`, `memory-keeping`. Read the 21 skill descriptions.
2. Branch: `cloud/pg-user-question-harvester/<YYYY-MM-DD>`.
3. Fetch the three list archives. Record URLs + HTTP status.
4. Pick **15-25 threads** that pass the internals filter and weren't covered
   in the prior 3 days' files (de-dup by message-id URL). Per `_loader.md`
   §5 "Fill the budget" — with the 50k output budget at ~1-2k per question
   entry, target 20+ questions per run, not 5-8.
5. For each, write to `knowledge/community/user-questions/<YYYY-MM-DD>.md`:
   - Subject + message-id URL + source list
     (pgsql-general / pgsql-performance / pgsql-hackers).
   - 2-3 sentence summary of the actual question.
   - **Skill tag** — which skill (or skills) *should* be triggered by this
     question. If no skill fits, tag as `gap:<topic>`.
   - 1-sentence "ideal answer outline" referencing corpus paths.
6. Write run log + self-review + open PR
   `[cloud:pg-user-question-harvester] <n> questions · <m> gap tags`.

## Failure modes

- One list archive unreachable → use the others, note the gap.
- All three archives unreachable → no PR, exit `rate-limited`.
- Fewer than 3 questions pass the filter → still open PR with what was found
  and note "thin day" in run log.

## Budget

200k input / 50k output. Bumped from 70k/15k 2026-06-02 evening per the
"fill the budget" directive (`_loader.md` §5). At ~1-2k output per
question entry the new budget supports 20-30 questions per run vs prior
5-8 — more skill-tagging signal for the gap-detection use case.
