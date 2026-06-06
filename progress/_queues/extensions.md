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
[skipped:in-core] postgres/postgres branch=master files=contrib/pg_stat_statements/pg_stat_statements.c,contrib/pg_stat_statements/README  # 2026-06-05: pg_stat_statements is in-core contrib, already covered by A11 per-file docs + knowledge/issues/pg_stat_statements.md; it IS core, so the "external extension diverging from core" framing doesn't fit. Skipped per anthropologist judgment, processed external entries instead.
[done:PENDING] reorg/pg_repack branch=master files=README.rst,doc/pg_repack.rst,lib/repack.c,bin/pg_repack.c,lib/pgut/pgut-spi.c  # 2026-06-05 cloud/pg-extension-anthropologist; README is .rst not .md; added doc/pg_repack.rst (algorithm) + lib/pgut/pgut-spi.c (SPI wrappers). → knowledge/ideologies/pg_repack.md
[pending] postgis/postgis branch=master files=README.postgis,liblwgeom/liblwgeom.h,postgis/postgis.h
[pending] 2ndQuadrant/pglogical branch=REL2_x_STABLE files=README.md,pglogical.h,pglogical_apply.c
[done:cb615ac] pgaudit/pgaudit branch=main files=README.md,pgaudit.c,pgaudit.control  # branch was master in manifest → corrected to main (repo default)
[done:PENDING] citusdata/pg_cron branch=main files=README.md,src/pg_cron.c,src/job_metadata.c,include/cron.h,pg_cron.control  # 2026-06-05 cloud/pg-extension-anthropologist; manifest cron.h → include/cron.h; added src/job_metadata.c + pg_cron.control for catalog/bgworker detail. → knowledge/ideologies/pg_cron.md
[pending] citusdata/postgresql-hll branch=master files=README.markdown,src/hll.c
[done:PENDING] powa-team/pg_qualstats branch=master files=pg_qualstats.c,pg_qualstats.control,doc/README.md  # 2026-06-05 cloud/pg-extension-anthropologist; default branch is master not main; root README.md is an empty symlink → fetched doc/README.md. → knowledge/ideologies/pg_qualstats.md
[pending] markwkm/pg_top branch=master files=README,pg_top.h
