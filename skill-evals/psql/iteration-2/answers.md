# Iteration 2 — answers

Re-run of the same three prompts against the edited
`.claude/skills/psql/SKILL.md`. Baseline answers are unchanged in spirit
(generic PG knowledge); minor wording variation only.

---

## Eval 1 — Watch a backend's memory-context tree, plus snapshot another backend's contexts

### with_skill

Connect to the dev cluster:

```bash
psql -h /tmp -d postgres
```

Unix socket at `/tmp`, db `postgres`, superuser = `$USER` (the skill
flags that no literal `postgres` role exists — `initdb` makes the
superuser your shell user).

**This backend's own contexts.** Using the corrected query (the skill
now documents the actual columns — `name, ident, type, level, path
int4[], total_bytes, ...`; `path` is the ancestor context_id array, not
a single `parent` column):

```sql
\set ON_ERROR_STOP on
\timing on

SELECT name, type, level, path, total_bytes/1024 AS kb, used_bytes/1024 AS used_kb
FROM pg_backend_memory_contexts
ORDER BY total_bytes DESC LIMIT 20;
\watch 2
```

`\watch 2` re-runs every 2 seconds. `pg_backend_memory_contexts` is
per-connection — it only reflects THIS psql's backend.

**Another backend's contexts → server log.** Find the PID and signal:

```sql
SELECT pid, application_name, state, query
FROM pg_stat_activity
WHERE backend_type = 'client backend' AND pid <> pg_backend_pid();

SELECT pg_log_backend_memory_contexts(<pid>);
```

Output lands in `dev/data-debug/server.log` on the targeted backend's
next `CHECK_FOR_INTERRUPTS()`. Tail with `/pg-tail-log`. PG 14+.

**Leak hunt across iterations.** The skill's leak workflow names
`MessageContext` (the per-message context reset between client protocol
messages — growth across iterations IS the leak signature) plus
`CacheMemoryContext`, `ExecutorState`, `PortalContext` as the other
commonly-watched contexts:

```sql
-- baseline
SELECT name, total_bytes FROM pg_backend_memory_contexts WHERE name='MessageContext';
-- ... run workload N times ...
-- recheck
SELECT name, total_bytes FROM pg_backend_memory_contexts WHERE name='MessageContext';
```

If the query you're studying finishes too fast for `\watch` to catch
it, hold the backend via `PGAPPNAME=hold` + `pg_sleep` (now inlined in
the skill — see eval 2).

### baseline

(Unchanged from iter-1.)

Connect to psql (assume `psql -d postgres`).

```sql
SELECT name, level, total_bytes
FROM pg_backend_memory_contexts
ORDER BY total_bytes DESC LIMIT 20;
```

Current connection only. `\watch 2` re-runs. For another backend:

```sql
SELECT pg_log_backend_memory_contexts(<pid>);
```

Lands in the server log (path depends on `log_directory`).

---

## Eval 2 — Capture backend PID and hand off to lldb without race

### with_skill

The skill now ships the race-safe recipe inline plus the
per-connection-fork note:

> Every psql connection causes the postmaster to `fork()` a fresh
> backend; the PID from `pg_backend_pid()` is THAT backend's pid (NOT
> psql's client-side pid).

```bash
# 1. Tag a holding backend with application_name='hold' and pin it open.
#    PGAPPNAME is a libpq env var (NOT a psql \set var — that won't propagate).
PGAPPNAME=hold psql -h /tmp -d postgres -X -c 'SELECT pg_sleep(600);' &

# 2. From a second psql, find the PID. -At for unaligned+tuples-only.
PID=$(psql -h /tmp -d postgres -At -c \
  "SELECT pid FROM pg_stat_activity WHERE application_name='hold'")

# 3. Attach. /pg-attach wraps lldb with breakpoints on errstart and
#    MemoryContextStats pre-set.
/pg-attach "$PID"

# 4. From a THIRD psql session, run the actual repro you want lldb to
#    step through. Use the same application_name='hold' if you want
#    that session's pid (i.e. drive queries through the attached backend).
```

`-X` skips `~/.psqlrc` so the rc file doesn't emit lines that look like
the query under study.

If you're studying startup or the backend you want doesn't yet exist,
use single-user mode (cross-ref to `debugging/SKILL.md`).

### baseline

(Unchanged from iter-1.)

```sql
SELECT pg_backend_pid();
-- prints 47213
```

Then `sudo lldb -p 47213`. To hold the backend, run `SELECT pg_sleep(60);`
after grabbing the pid. Every psql opens its own backend, so the pid is
that backend's pid.

---

## Eval 3 — Force hash join, observe WAL/buffer activity, revert

### with_skill

The skill now explicitly notes that `enable_*` GUCs don't hard-disable a
node — they apply `disable_cost`, so the planner picks the next-best
plan unless every alternative is also disabled.

```bash
psql -h /tmp -d postgres
```

```sql
EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, VERBOSE)
SELECT * FROM big a JOIN small b USING (id) WHERE a.k = 1;

SET enable_nestloop = off;     -- discourage, don't disable
SET enable_mergejoin = off;

EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, VERBOSE)
SELECT * FROM big a JOIN small b USING (id) WHERE a.k = 1;
```

`BUFFERS` shows shared/local/temp blocks read+hit per node. `WAL`
reports records, full-page-images, bytes — should be near zero for a
SELECT; non-zero usually means hint-bit writes or HOT-prune writes.
`SETTINGS` dumps any non-default planner GUCs (so you can see your
`enable_*` overrides). `VERBOSE` adds output column expressions and
schema qualification.

`FORMAT JSON` for machine-parseable output if diffing two plans:

```sql
EXPLAIN (ANALYZE, BUFFERS, WAL, FORMAT JSON) <query>;
```

`\timing on` if you want a wall-clock figure independent of EXPLAIN's
instrumentation overhead.

Revert without restart:

```sql
RESET enable_nestloop;
RESET enable_mergejoin;
-- or
RESET ALL;
```

`SET` is session-scoped; closing psql also resets. For cross-session
persistence on the dev cluster: `ALTER SYSTEM SET enable_nestloop = off;
SELECT pg_reload_conf();` and `ALTER SYSTEM RESET enable_nestloop;` to
revert. For txn-scoped overrides: `SET LOCAL` inside `BEGIN`/`COMMIT`.

### baseline

(Unchanged from iter-1.)

```sql
SET enable_nestloop = off;
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM big JOIN small USING (id);
```

Maybe `enable_mergejoin = off` too. There's a `WAL` option but not 100%
sure of spelling. Revert with `RESET enable_nestloop;` or close psql.
