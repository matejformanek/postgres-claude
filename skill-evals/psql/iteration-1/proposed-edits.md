# Proposed edits — iteration 1 (NOT applied)

## Summary of gaps found in grading

The skill is strong — 28/29 with_skill. The single with_skill miss is
the per-connection-fork model (a backend's PID is the BACKEND's, not
psql's). The skill mentions this only in a cross-ref to
`knowledge/architecture/process-model.md`.

More importantly, **iteration 1 surfaced a real factual bug** in the
SKILL.md query at line 98-100 — the `parent` column does NOT exist in
`pg_backend_memory_contexts`. The actual schema (verified at
`source/src/include/catalog/pg_proc.dat:8709-8715`) is `name, ident,
type, level, path, total_bytes, total_nblocks, free_bytes, free_chunks,
used_bytes` — `path` is an int4 array of parent context_ids, not a
single `parent` column. Running the SKILL.md query verbatim would error
with `column "parent" does not exist`.

## Concrete edits to consider

### 1. [BUG] Fix the `pg_backend_memory_contexts` query — `parent` column does not exist

Currently lines 98-100 of SKILL.md:

```sql
SELECT name, level, parent, total_bytes/1024 AS kb, used_bytes/1024 AS used_kb
FROM pg_backend_memory_contexts
ORDER BY total_bytes DESC LIMIT 20;
```

Verified columns (from `source/src/include/catalog/pg_proc.dat:8713`):
`name, ident, type, level, path, total_bytes, total_nblocks,
free_bytes, free_chunks, used_bytes`.

Proposed replacement:

```sql
SELECT name, type, level, path, total_bytes/1024 AS kb, used_bytes/1024 AS used_kb
FROM pg_backend_memory_contexts
ORDER BY total_bytes DESC LIMIT 20;
```

`path` is `int4[]` — the array of ancestor context_ids from
TopMemoryContext down. Rationale: pasting the SKILL.md query verbatim
into psql currently errors. This is the highest-priority edit.

### 2. Add a "trap" question: managed/network PG vs local dev cluster

The skill's frontmatter description already lists managed-PG out of
scope, but the body doesn't name the trap explicitly. Add a one-line
gotcha to §Common gotchas:

> - **`psql -h db.acme.com …` is the WRONG tool here.** This skill is
>   for the LOCAL dev cluster built from source. If the prompt names a
>   hostname, a managed-PG vendor (RDS / Cloud SQL / Supabase / Neon),
>   or talks about prod data, stop. Use the production-PG tooling for
>   that team, NOT this skill.

Rationale: makes the dev-vs-prod boundary visible inside the skill body
(not only in the description), which is where the user lands when they
open it.

### 3. Inline the held-PID handoff recipe (don't only cross-ref to debugging/)

§"Capturing a backend PID for gdb/lldb" currently says:

```sql
SELECT pg_backend_pid();
```

Then in another shell: `/pg-attach <pid>`. The reader has to context-switch
to `debugging/SKILL.md` for the actual race-safe recipe.

Add a 5-line block:

```bash
# Race-safe: tag a holding backend, look it up, attach.
PGAPPNAME=hold psql -h /tmp -d postgres -X -c 'SELECT pg_sleep(60);' &
PID=$(psql -h /tmp -d postgres -At -c \
  "SELECT pid FROM pg_stat_activity WHERE application_name='hold'")
/pg-attach "$PID"
# Then run your real workload in a THIRD psql session.
```

With a sentence: "`PGAPPNAME` is a libpq env var, NOT a `\set` variable."

Rationale: this is one of the highest-yield psql-on-dev-cluster patterns,
and it lives only in a sister skill. Putting the 5-line recipe inline
costs nothing.

### 4. Name MessageContext explicitly in the leak-workflow

§"Memory-leak workflow" step 1 says:

```sql
SELECT name, total_bytes FROM pg_backend_memory_contexts WHERE name='MessageContext';
```

Add a 1-line note explaining WHY MessageContext: it's the per-message
context reset between client messages, so growth across iterations is
the leak signature for a per-message leak. Currently the reader has to
know this. (Other commonly-watched contexts: `CacheMemoryContext`,
`ExecutorState`, `PortalContext`.)

### 5. Note the per-connection-fork model inline (not only via cross-ref)

The only with_skill miss in iter-1: the answer didn't surface that every
psql connection forks a fresh backend, so the PID returned by
`pg_backend_pid()` is the BACKEND's pid, not psql's. One sentence under
§"Capturing a backend PID" would close this:

> Every psql connection causes the postmaster to `fork()` a fresh
> backend; the PID you get from `pg_backend_pid()` is that backend's
> pid (NOT psql's client-side pid). See
> `knowledge/architecture/process-model.md` for why.

### 6. (Optional) Mention `enable_*` is "discourage not disable"

The skill currently shows `SET enable_seqscan = off` as a planner-forcing
knob without explaining the mechanism. The baseline answer treats
`enable_nestloop = off` as if it hard-disables the node type. Real
behavior: applies a large cost penalty (`disable_cost = 1.0e10` in
`cost.h`), so the planner picks the next-best plan. One inline comment
in the Session-knobs block:

```sql
-- enable_* don't HARD-disable a node; they apply a huge cost penalty
-- so the planner picks the next-best plan. If every alternative is
-- also disabled, the disabled node still wins.
SET enable_seqscan = off;
```

### 7. (Optional) Verify and add `\errverbose` shows SQLSTATE + ereport file:line

The skill at line 57 claims `\errverbose` prints "code, detail, hint,
file:line of the ereport()". This is correct (verified `command.c:1644`).
The trigger eval #8 specifically asks about this — make sure the table
row keeps that phrasing. No edit needed; just don't drop it.

## Non-edits

- The trust+socket+`postgres` defaults are correct and consistently used.
- The `\copy` vs `COPY` distinction (client-side vs server-side) is
  correctly stated.
- The MCP-vs-psql split is well-explained — no churn there.
- The `pg_log_backend_memory_contexts` PG 14+ note is correct: the
  function was added in commit `43620e32861` (2021-04-06), on the PG 14
  dev branch.

## Score delta if all edits applied

iter-1 with_skill: 28/29 (0.966). Edit #5 closes the one miss.
Edits #1-#3 are quality-of-life / bug fixes and would not change the
graded score (no assertion happens to test them), but matter for the
skill's real-world correctness — especially #1, which is a copy-paste
error in the current SKILL.md.

Expected iter-2 with_skill: 29/29 (1.000), holding the same harder set.
