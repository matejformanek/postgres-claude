---
name: pg-user-question-harvester
schedule: "47 0 * * * Europe/Prague"
fetches_source_via_url: false
queue: null
output_dirs: [knowledge/community/user-questions]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 70000
max_output_tokens: 15000
---

# pg-user-question-harvester

Pull recent internals-flavored questions from dba.stackexchange.com and
r/PostgreSQL. Tag each with which existing skill *should* answer it.
Skills never tagged over many days are dead-code candidates.

## Inputs

- Stack Exchange search:
  `https://dba.stackexchange.com/questions/tagged/postgresql-internals?tab=Newest`
  and `https://dba.stackexchange.com/questions/tagged/postgresql?tab=Newest`
  (filter to posts from last 7 days via WebFetch; pick internals-flavored
  keywords: WAL, lock, MVCC, vacuum, planner, executor, buffer,
  replication, snapshot, xid).
- Reddit: `https://www.reddit.com/r/PostgreSQL/new.json?limit=50` (apply
  the same keyword filter).
- Skill descriptions: lazy-load frontmatter `description:` field from each
  `.claude/skills/*/SKILL.md` for tagging.

## Per-run recipe

1. Load `pg-claude`, `memory-keeping`. Read the 21 skill descriptions.
2. Branch: `cloud/pg-user-question-harvester/<YYYY-MM-DD>`.
3. Fetch SE + Reddit listings. Record URLs + status.
4. Pick 5-8 questions that pass the internals filter and weren't covered in
   the prior 3 days' files (de-dup by URL).
5. For each, write to `knowledge/community/user-questions/<YYYY-MM-DD>.md`:
   - Title + URL + source (SE / Reddit).
   - 2-3 sentence summary of the actual question.
   - **Skill tag** — which skill (or skills) *should* be triggered by this
     question. If no skill fits, tag as `gap:<topic>`.
   - 1-sentence "ideal answer outline" referencing corpus paths.
6. Write run log + self-review + open PR
   `[cloud:pg-user-question-harvester] <n> questions · <m> gap tags`.

## Failure modes

- SE 429 → use Reddit only; note gap. Reddit 429 → SE only.
- Both unreachable → no PR, exit `rate-limited`.
- Fewer than 3 questions pass the filter → still open PR with what was
  found and note "thin day" in run log.

## Budget

70k input / 15k output.
