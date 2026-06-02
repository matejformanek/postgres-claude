# 2026-06-02 — extension-anthropologist: TimescaleDB ideology

## What I did
- Cloud routine `pg-extension-anthropologist`, second pop of the day. Popped
  `timescale/timescaledb` (head `[pending]` after the citus run).
- Fetched tree listing + manifest (`README.md`, `src/chunk.h`,
  `src/hypertable.h`) via raw.githubusercontent; `docs/SECURITY.md` 404'd.
  Pulled three supplementary files to ground the headline divergence claims:
  `src/loader/loader.c`, `src/init.c`, `timescaledb.control.in`.
- Wrote `knowledge/ideologies/timescaledb.md` (265 lines, 6 divergence
  sections, all cited into the ext repo).

## What I learned
- TimescaleDB's most idiom-divergent machinery is *packaging*, not query
  execution: a **two-tier loader**. A stable thin `timescaledb.so` goes in
  `shared_preload_libraries`; it lazily `load_external_function()`s a
  **version-stamped** `timescaledb-<version>.so` via `post_parse_analyze_hook`
  (`loader.c:725-800`, `control.in:4`). Mismatched version in a live session →
  `ereport(FATAL, ...)` and session restart (`loader.c:741-748`).
- It can't check extension-installed-ness at preload time because
  `shared_preload_libraries` runs in `PostmasterMain` before `InitPostgres` /
  any DB assignment / syscache (`loader.c:46-81`). Hence the analyze-hook
  trampoline.
- Single repo, **two licenses**: `src/` Apache 2.0, `tsl/` Timescale License.
  Enforced at runtime by deferring TSL `.so` load out of `_PG_init` into the
  SQL-callable `ts_post_load_init` → `ts_license_enable_module_loading()`,
  because loading TSL during `_PG_init` races parallel workers into link
  errors (`init.c:135-145`).
- Chunks are TS's own N-dimensional hypercube model (each slice a CHECK
  constraint), with its own catalog (`FormData_hypertable`/`FormData_chunk`) —
  parallel to, not built on, native PG declarative partitioning (`chunk.h:55-76`).
- Persisted `CHUNK_STATUS_*` bitmask has a hand-maintained on-disk
  compatibility contract (downgrade scripts must handle new flags) —
  fundamentally different from core's single-`CATALOG_VERSION_NO`+initdb model
  (`chunk.h:277-307`).

## What I'm unsure about
- The README on `main` is now marketing/quickstart; older architecture prose
  may have moved to `docs/` or the website. `docs/SECURITY.md` is gone from
  this path — security model not characterized.
- Continuous-aggregate and columnstore internals are only sketched (from
  README + chunk.h flags); the `tsl/` implementation files weren't fetched.
- Custom-scan node internals (`ConstraintAwareAppend`, `ChunkAppend`) are named
  from `init.c` registration but their exec callbacks weren't read.

## Pointers left for next time
- Next queue head: `pgpartman/pg_partman` (then pgvector, hypopg, ...).
- If timescaledb gets a deeper pass: fetch `tsl/src/nodes/.../planner.h` +
  the chunk-exclusion planner code to characterize the query-layer divergence
  (this run focused on the loader/license/packaging ideology).
</content>
