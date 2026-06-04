# Queue: pg-extension-anthropologist

Format: `[status] <owner/repo> branch=<ref> files=<comma,separated,paths>`
Refill rule: when empty, run `gh search topics postgresql-extension --limit
50`, filter to repos > 500 stars not yet covered under
`knowledge/ideologies/`, append as `[pending]` entries.

## Entries

[done:ce97359] citusdata/citus branch=main files=README.md,src/backend/distributed/README.md,src/include/distributed/citus_custom_scan.h
[done:4396a9b] timescale/timescaledb branch=main files=README.md,docs/SECURITY.md,src/chunk.h,src/hypertable.h
[done:cb615ac] pgpartman/pg_partman branch=development files=README.md,src/pg_partman_bgw.c,pg_partman.control  # branch was master in manifest → corrected to development (repo default); doc/pg_partman.md + sql/types/types.sql deferred (plpgsql side, see pg_partman.md gap note)
[done:cb615ac] pgvector/pgvector branch=master files=README.md,src/vector.h,src/ivfflat.h,src/hnsw.h
[done:cb615ac] HypoPG/hypopg branch=REL1_STABLE files=README.md,include/hypopg.h,include/hypopg_index.h,hypopg.control,hypopg.c  # headers live under include/; added .control + hypopg.c for hook detail
[pending] postgres/postgres branch=master files=contrib/pg_stat_statements/pg_stat_statements.c,contrib/pg_stat_statements/README
[pending] reorg/pg_repack branch=master files=README.md,bin/pg_repack.c,lib/repack.c
[pending] postgis/postgis branch=master files=README.postgis,liblwgeom/liblwgeom.h,postgis/postgis.h
[pending] 2ndQuadrant/pglogical branch=REL2_x_STABLE files=README.md,pglogical.h,pglogical_apply.c
[done:cb615ac] pgaudit/pgaudit branch=main files=README.md,pgaudit.c,pgaudit.control  # branch was master in manifest → corrected to main (repo default)
[pending] citusdata/pg_cron branch=main files=README.md,src/pg_cron.c,src/cron.h
[pending] citusdata/postgresql-hll branch=master files=README.markdown,src/hll.c
[pending] powa-team/pg_qualstats branch=main files=README.md,pg_qualstats.c
[pending] markwkm/pg_top branch=master files=README,pg_top.h
