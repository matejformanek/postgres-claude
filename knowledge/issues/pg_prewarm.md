# Issues — `contrib/pg_prewarm`

Page-prewarming extension + autoprewarm background worker. 2 source files / ~1290 LOC.

**Parent docs:** `knowledge/files/contrib/pg_prewarm/pg_prewarm.c.md`, `knowledge/files/contrib/pg_prewarm/autoprewarm.c.md`.

**Source:** 10 entries surfaced 2026-06-09 by A14-1.

## Headlines

1. **🚨 `autoprewarm_start_worker` / `autoprewarm_dump_now` are PUBLIC** — no REVOKE in any install script, no C-side check. Any logged-in user can trigger a full NBuffers dump and contend for buffer-header spinlocks. **Worst entrypoint of A14-1.**
2. **Autoprewarm dump-file path is unvalidated** and PGDATA-relative — symlink/replace on PGDATA can steer prewarm I/O.
3. **`<<N>>` block count read as signed `%d`** — negative N silently propagates to size calculation; corrupted file can OOM the leader via `dsm_create(20*N)`.
4. **Per-DB worker connects with `InvalidOid` user** — cached blocks survive role-perm changes across restart (defense-in-depth nit).

## Entries — `pg_prewarm.c`

- [ISSUE-defense-in-depth: `ACL_SELECT` covers all forks (VM/FSM/INIT), not just MAIN (nit)] — `:149-167`
- [ISSUE-resource: no rate limit on block range; any SELECT user can force full-relation reads (maybe)] — `:220-233`
- [ISSUE-nit: static file-scope `blockbuffer` fragile if function ever becomes re-entrant (nit)] — `:45,230`
- [ISSUE-correctness: documented privOid swap race depends on `IndexGetRelation` idempotence under `AccessShareLock` (maybe)] — `:131-148`

## Entries — `autoprewarm.c`

- [ISSUE-audit-gap: `autoprewarm_start_worker` / `autoprewarm_dump_now` have NO permission check (PUBLIC) (likely)] — `:814,846` (no REVOKE in install scripts)
- [ISSUE-defense-in-depth: per-DB worker connects with `InvalidOid` user; cached blocks survive role-perm changes across restart (nit)] — `:519`
- [ISSUE-defense-in-depth: dump file path is unvalidated; symlink/replace on PGDATA can steer prewarm I/O (nit)] — `:53,322,737-738`
- [ISSUE-resource: leading `<<N>>` drives `dsm_create` of `20*N` bytes; corrupted file can OOM leader (nit)] — `:339-346`
- [ISSUE-correctness: stale `bgworker_pid` after `SIGKILL` of leader blocks re-start (nit)] — `:197-205,892-901`
- [ISSUE-correctness: `<<N>>` read as signed `%d`, negative N silently propagated to size calculation (maybe)] — `:339,346`

## Cross-sweep references

- A8 archive_command — "load arbitrary code from untrusted name" cluster (autoprewarm dump path).
- A12 amcheck, A14 pg_visibility/pg_buffercache — "REVOKE-only / no C-side check" cluster.
