# Iteration 2 — edits applied

Applied subset of edits from `iteration-1/proposed-edits.md` to
`.claude/skills/psql/SKILL.md`.

## Verification of values against source/

- `pg_backend_memory_contexts` column set — verified at
  `source/src/include/catalog/pg_proc.dat:8709-8715`
  (`proargnames = '{name, ident, type, level, path, total_bytes,
  total_nblocks, free_bytes, free_chunks, used_bytes}'`,
  `proallargtypes = '{text,text,text,int4,_int4,int8,...}'` — so `path`
  is `int4[]`). No `parent` column exists. The SKILL.md query at line
  98-100 was a copy-paste error / stale.
- `pg_log_backend_memory_contexts` — verified at
  `source/src/backend/utils/adt/mcxtfuncs.c:267` and signal-handler
  delivery at line 301 (PROCSIG_LOG_MEMORY_CONTEXT). Introduced in
  commit `43620e32861` (2021-04-06), which landed in the PG 14 dev
  cycle. The "PG 14+" note in SKILL.md is correct.
- `PGAPPNAME=hold` + `pg_sleep` + `application_name='hold'` recipe —
  verified against the sister skill at
  `.claude/skills/debugging/SKILL.md:47-71` (already in use). Inlining
  the 5-line recipe into psql/SKILL.md reproduces it verbatim.
- `enable_*` GUC semantics (cost penalty, not hard-disable) — common
  PG knowledge; encoded in `disable_cost` (1.0e10) in the planner. Not
  citing a line for a single-word inline comment.

## Edits applied

1. **Edit #1 (HIGH — bug fix)** — replaced the broken
   `pg_backend_memory_contexts` query (column `parent` does not exist)
   with the corrected column set (`name, type, level, path, total_bytes,
   used_bytes`) plus a 3-line comment naming the full schema and
   explaining that `path` is the ancestor `context_id` array. This was
   the only outright incorrect SQL in the skill.

2. **Edit #2 (HIGH — trap gotcha)** — prepended a "wrong tool" bullet to
   §Common gotchas naming managed-PG vendors (RDS, Cloud SQL, Supabase,
   Neon, Aurora) and `psql -h db.acme.com` as out-of-scope. Surfaces the
   dev-vs-prod boundary inside the skill body, not only in frontmatter.

3. **Edit #3 (MED — inline recipe)** — expanded
   §"Capturing a backend PID for gdb/lldb" with the full race-safe
   `PGAPPNAME=hold` + `pg_sleep` + `application_name='hold'` recipe
   (4-step bash block), plus the libpq-env-var-not-`\set` note. Reader
   no longer needs to context-switch to `debugging/SKILL.md` for this.

4. **Edit #4 (MED — context names)** — expanded the leak-workflow step
   1 to name MessageContext's role (per-message context, reset between
   client protocol messages) plus the three other commonly-watched
   contexts (`CacheMemoryContext`, `ExecutorState`, `PortalContext`).

5. **Edit #5 (MED — fork model)** — added one-sentence note under
   §"Capturing a backend PID" that every psql connection forks a fresh
   backend, so the PID is the BACKEND's not psql's. Cross-ref to
   `knowledge/architecture/process-model.md` retained.

6. **Edit #6 (LOW — enable_* clarification)** — added a 3-line inline
   comment in the Session-knobs block noting `enable_*` doesn't
   hard-disable a node type — applies `disable_cost` so the planner
   picks the next-best plan unless every alternative is also disabled.

## Edits NOT applied

- **Edit #7** (verify `\errverbose` claim) — was a no-op verification
  request, not an edit. Verified at `source/src/bin/psql/command.c:1641-1644`
  that the function exists; the table-row phrasing in SKILL.md is fine
  and was not changed.
