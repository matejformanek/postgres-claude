# Iteration 1 — answers

Skill under test: `.claude/skills/psql/SKILL.md`.

Two answers per eval: `with_skill` (relies on the skill's content) and
`baseline` (generic psql knowledge only — no peek at SKILL.md).

---

## Eval 1 — Watch a backend's memory-context tree, plus snapshot another backend's contexts

### with_skill

Connect to the local dev cluster on the trust + socket defaults the skill
hardcodes:

```bash
psql -h /tmp -d postgres
```

Unix socket at `/tmp`, db `postgres`, superuser = your `$USER` (the skill
notes the `role "postgres" does not exist` gotcha — `initdb` makes the
superuser `$USER`).

**In the same backend (watching this session's own contexts):**

```sql
\set ON_ERROR_STOP on
\timing on

-- Top consumers — use \watch to refresh every 2s while your suspect
-- workload runs.
SELECT name, level, total_bytes/1024 AS kb, used_bytes/1024 AS used_kb
FROM pg_backend_memory_contexts
ORDER BY total_bytes DESC LIMIT 20;
\watch 2
```

This only reflects the CURRENT psql's backend. To watch a DIFFERENT
backend's growing contexts you need a snapshot mechanism, because
`pg_backend_memory_contexts` is per-connection.

**Snapshotting another backend's contexts to the server log:**

```sql
-- Find the target PID.
SELECT pid, application_name, state, query
FROM pg_stat_activity
WHERE backend_type = 'client backend' AND pid <> pg_backend_pid();

-- Send the signal; the targeted backend logs its full context tree
-- to dev/data-debug/server.log on its next CHECK_FOR_INTERRUPTS().
SELECT pg_log_backend_memory_contexts(<pid>);
```

Then tail `dev/data-debug/server.log` (the skill points at `/pg-tail-log`
for that). The skill notes this is PG 14+.

To pin growth across iterations: snapshot `MessageContext` (the
per-message context that holds parse/plan/execute state) on iteration 0,
run the workload N times, snapshot again — growth across iterations is
the leak signature. The skill's leak-workflow §5 spells this out.

If the query keeps finishing too fast, hold it with the `PGAPPNAME=hold`
+ `pg_sleep` trick from `debugging/SKILL.md` (cross-referenced) so you
have a stable target PID.

### baseline

Connect to psql (need to know the connection details — let's assume
`psql -d postgres`). Then:

```sql
SELECT name, level, total_bytes
FROM pg_backend_memory_contexts
ORDER BY total_bytes DESC LIMIT 20;
```

This shows the contexts of the current connection. To re-run repeatedly,
type `\watch 2` after a query.

For another backend, there's `pg_log_backend_memory_contexts(pid)` which
sends a signal; the output lands in the server log file. Find the pid
via `pg_stat_activity`:

```sql
SELECT pid, query FROM pg_stat_activity WHERE state = 'active';
```

Read the log file (location depends on the cluster's `log_directory`
setting).

---

## Eval 2 — Capture backend PID and hand off to lldb without race

### with_skill

The skill calls out the held-PID handoff explicitly as a cross-reference
to `debugging/SKILL.md`, and ships the connection idiom for the dev
cluster. Combined recipe:

```bash
# Tag the holding session with application_name=hold so it's
# trivially findable in pg_stat_activity. PGAPPNAME is a libpq env
# var, NOT a psql \set variable (the skill flags this explicitly).
PGAPPNAME=hold psql -h /tmp -d postgres -X -c 'SELECT pg_sleep(60);' &

# Look up the PID from another psql session.
psql -h /tmp -d postgres -At -c \
  "SELECT pid FROM pg_stat_activity WHERE application_name='hold'"
# → prints e.g. 47213

# Attach lldb. /pg-attach wraps lldb with breakpoints on errstart
# and MemoryContextStats already set (per the skill).
/pg-attach 47213
```

Then once attached, in a THIRD psql session, run the real query you
want to step through. The held backend remains in `pg_sleep` until you
either kill it or let the 60s expire.

If you'd rather drive queries through the attached session, replace
`pg_sleep` with `\set FETCH_COUNT 1` + a long-running cursor, or just
extend the sleep to something safe like 600s.

Why not just `pg_backend_pid()`? Because by the time you read the PID
and shell out to lldb, an already-running query is gone. The hold pattern
gives you a stable target.

Don't forget `-X` to skip `~/.psqlrc` (so a noisy startup file doesn't
emit log lines you'll mistake for the query you want to debug).

### baseline

In psql:

```sql
SELECT pg_backend_pid();
-- prints 47213
```

Then from a shell:

```bash
sudo lldb -p 47213
```

The pid would be the psql backend's pid (every psql connection forks
its own backend in PostgreSQL). To make the backend sit still while
you attach, run a long sleep first:

```sql
SELECT pg_sleep(60);
```

But you need to grab the pid BEFORE the query runs, otherwise you race.
One trick: open psql, run `SELECT pg_backend_pid();`, note it, attach,
then run your real query.

---

## Eval 3 — Force hash join, observe WAL/buffer activity, revert

### with_skill

The skill enumerates exactly the GUCs and EXPLAIN options needed:

```bash
psql -h /tmp -d postgres
```

```sql
-- Show the planner's pick first (sanity).
EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, VERBOSE)
SELECT * FROM big a JOIN small b USING (id) WHERE a.k = 1;

-- Force hash join. enable_* GUCs don't HARD-disable a node type;
-- they apply a huge cost penalty, so the planner picks the next
-- best plan — which is usually what you wanted.
SET enable_nestloop = off;
SET enable_mergejoin = off;

-- Re-run with the same EXPLAIN to compare.
EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, VERBOSE)
SELECT * FROM big a JOIN small b USING (id) WHERE a.k = 1;

-- For SELECT, WAL counts should be near-zero; non-zero means hint
-- bit writes or HOT-prune writes. The skill includes BUFFERS, WAL,
-- SETTINGS, VERBOSE as the canonical EXPLAIN set for this workflow.
```

`SET` is session-scoped — the skill flags this. Exit psql or:

```sql
RESET enable_nestloop;
RESET enable_mergejoin;
-- or all at once
RESET ALL;
```

No cluster restart needed. If you wanted these to stick across sessions
on the dev cluster (e.g., to debug a planner change), the skill mentions
`ALTER SYSTEM SET ... ; SELECT pg_reload_conf()` and the matching
`ALTER SYSTEM RESET`. For one-off plan forcing, plain `SET` + `RESET`
is the right call.

For JSON output (machine-parseable for diffing two plans):

```sql
EXPLAIN (ANALYZE, BUFFERS, WAL, FORMAT JSON)
SELECT ...
```

The skill's "Session knobs" block lists this exact form. Use `\timing on`
on top if you want a wall-clock figure independent of EXPLAIN's
instrumentation overhead.

### baseline

To force a hash join in psql:

```sql
SET enable_nestloop = off;
EXPLAIN ANALYZE SELECT * FROM big JOIN small USING (id);
```

`enable_nestloop = off` discourages nested loops. You may also want
`SET enable_mergejoin = off` if there's a merge candidate. Then run
`EXPLAIN ANALYZE` to see the plan that gets picked.

For buffer info: `EXPLAIN (ANALYZE, BUFFERS) ...`. For WAL: I think
there's a `WAL` option but I'm not 100% sure of the spelling.

To revert: `SET enable_nestloop = on;` or `RESET enable_nestloop;`.
Settings are session-scoped, so closing psql also resets them.
