---
source_url: https://www.postgresql.org/docs/current/monitoring-ps.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§28.1 Standard Unix Tools (process title display)"
maps_to_skills: [debugging]
maps_to_corpus: [knowledge/files/src/backend/utils/misc/ps_status.c.md, knowledge/docs-distilled/monitoring-locks.md, knowledge/docs-distilled/monitoring-stats.md]
---

# Standard Unix tools — process-title display (§28.1)

Each backend rewrites its own `ps` title to advertise who/what it is — a
zero-query first look at a live cluster before touching pg_stat_activity.

## Non-obvious claims

- **Title format:** `postgres: user database host activity`, where *activity* is
  a live state word: `idle`, `idle in transaction`, the current command name
  (e.g. `SELECT`), with ` waiting` **appended** when the backend is blocked on a
  lock — so `... SELECT waiting` is directly readable as "blocked query". A
  background process shows `postgres: <role>: <procname>` (e.g.
  `postgres: background writer`). `[from-docs]`
- **`update_process_title` (default `on`)** gates *dynamic* updates; set `off`
  to fix the title at process launch and save a measurable per-command syscall on
  platforms where the update is expensive (negligible elsewhere). `[from-docs]`
- **`cluster_name`** (a logging-category GUC) is prepended so multiple clusters
  on one host are distinguishable in `ps` output. `[from-docs]`
- **Platform mechanism is compile-time.** The rewrite uses either a real
  `setproctitle()` or argv-clobbering, selected by `PS_USE_*` macros; Solaris
  needs `/usr/ucb/ps -ww` and the original `postgres` invocation must be *shorter*
  than the spawned title or updates silently no-op. `[from-docs]` (the machinery
  lives in `ps_status.c`.)
- **Complements, doesn't replace, the stats views.** The title is a glance;
  `pg_stat_activity` (per-backend state) and `pg_locks` (who blocks whom) carry
  the queryable detail behind the ` waiting` suffix. `[from-docs]`

## Links into corpus

- [[knowledge/files/src/backend/utils/misc/ps_status.c.md]] — the
  `set_ps_display()` / `PS_USE_*` implementation.
- [[knowledge/docs-distilled/monitoring-locks.md]] — the pg_locks detail behind
  a ` waiting` title.
- [[knowledge/docs-distilled/monitoring-stats.md]] — pg_stat_activity, the
  queryable twin of the title string.
</content>
