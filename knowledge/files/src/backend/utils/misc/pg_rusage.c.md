# `src/backend/utils/misc/pg_rusage.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~60
- **Source:** `source/src/backend/utils/misc/pg_rusage.c`

Tiny wrapper around `getrusage(RUSAGE_SELF)` used for VACUUM/ANALYZE
progress reporting and `EXPLAIN (BUFFERS)`-adjacent logging:
- `pg_rusage_init(PGRUsage *ru0)` snapshots the start state.
- `pg_rusage_show(const PGRUsage *ru0)` returns a `psprintf`'d string of
  the form `"CPU: user: X.YYs system: X.YYs elapsed: X.YYs"`. Used by
  `VERBOSE` flavors of maintenance commands. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
