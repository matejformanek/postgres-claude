---
source_url: https://www.postgresql.org/docs/current/predefined-roles.html
fetched_at: 2026-07-08
anchor_sha: 4c75cc786301
chapter: "§22.5 Predefined Roles"
maps_to_skills: [row-level-security, pgstat-framework, vacuum-autovacuum]
maps_to_corpus: [knowledge/docs-distilled/role-attributes.md, knowledge/docs-distilled/ddl-priv.md, knowledge/docs-distilled/monitoring-stats.md]
---

# Predefined roles — capabilities without SUPERUSER (§22.5)

The `pg_*` bootstrap roles that package a formerly-superuser-only capability as
a `GRANT`-able role, so operators can delegate narrowly instead of handing out
SUPERUSER. Members are added with ordinary `GRANT pg_x TO role`.

## Non-obvious claims

- **Design intent: replace hardcoded superuser checks with role membership.**
  Each capability that used to require `superuser()` in C now also accepts
  "is a member of `pg_<capability>`" — so `pg_read_all_settings`,
  `pg_read_all_stats`, `pg_checkpoint`, `pg_maintain`, etc. each unlock exactly
  one former superuser gate. `[from-docs]`
- **Data-access roles do NOT bypass RLS.** `pg_read_all_data` (≈ SELECT +
  schema USAGE on everything) and `pg_write_all_data` (≈ INSERT/UPDATE/DELETE)
  are still subject to row-level-security policies — that's `BYPASSRLS`'s job,
  not theirs. A common misconception. `[from-docs]`
- **`pg_monitor` is a convenience *composite*** that is itself granted
  `pg_read_all_settings` + `pg_read_all_stats` + `pg_stat_scan_tables` — one
  grant covers the whole monitoring surface. `[from-docs]`
- **`pg_stat_scan_tables` exists because some monitoring takes `ACCESS SHARE`
  locks** (e.g. `pgrowlocks()`), which is a heavier grant than pure stat-reading,
  so it's split out from `pg_read_all_stats`. `[from-docs]`
- **`pg_database_owner` is implicit and memberless.** You can't `GRANT` anyone
  into it; its single effective member is whoever owns the current database, and
  it owns the `public` schema by default — the mechanism behind PG 15+'s locked-
  down `public` schema. `[from-docs]`
- **`pg_signal_backend` cannot signal superuser-owned backends** — a deliberate
  asymmetry so delegated operators can't cancel/terminate the DBA's sessions.
  `pg_signal_autovacuum_worker` is the parallel for autovac workers. `[from-docs]`
- **The three server-file roles are effectively superuser-equivalent.**
  `pg_read_server_files` / `pg_write_server_files` / `pg_execute_server_program`
  "bypass all database-level permission checks" and can be leveraged to full
  superuser — the docs flag them as extreme-care grants. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/role-attributes.md]] — the raw attributes these
  roles were introduced to avoid handing out.
- [[knowledge/docs-distilled/ddl-priv.md]] — `MAINTAIN` privilege = what
  `pg_maintain` bundles cluster-wide.
- [[knowledge/docs-distilled/monitoring-stats.md]] — the `pg_stat_*` views
  `pg_read_all_stats` / `pg_monitor` unlock.
