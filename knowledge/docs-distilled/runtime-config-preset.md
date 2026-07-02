---
source_url: https://www.postgresql.org/docs/current/runtime-config-preset.html
fetched_at: 2026-07-02T20:50:00Z
anchor_sha: b542d5566705
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Preset Options (§20.15)

The read-only, compile-/init-time-determined GUCs — the ones tools query to
learn the build's capabilities. Companion: `knowledge/docs-distilled/bki.md`,
`storage-page-layout.md`; skill `build-and-run`.

## Compile-time page/segment geometry (the numbers everything else derives from)

- **`block_size` (8192)** = `BLCKSZ`; **`wal_block_size` (8192)** = `XLOG_BLCKSZ`;
  **`wal_segment_size` (16MB)** = the WAL file size; **`segment_size`** =
  `RELSEG_SIZE` in blocks (default → 1GB max per relation file segment, so a big
  table is split into `.1`, `.2`, … files). These four are the on-disk geometry
  constants the storage layer is built around. [from-docs]
- **`max_index_keys` (32)** = `INDEX_MAX_KEYS`; **`max_function_args` (100)** =
  `FUNC_MAX_ARGS`; **`max_identifier_length` (63)** = `NAMEDATALEN - 1` — the
  hard limit behind the classic "identifier truncated" behavior and the
  NAMEDATALEN edge cases R14 test suites probe. [from-docs]

## Build-feature flags a hacker checks

- **`debug_assertions` (bool)** = whether built with `USE_ASSERT_CHECKING`
  (i.e. `configure --enable-cassert` / meson `-Dcassert=true`). **This is the
  fast way to confirm you're on a cassert build** before relying on
  `debug_discard_caches` et al. Default `off` (non-assert build). [from-docs]
- **`integer_datetimes` (on, always since PG10)** — 64-bit-integer date/time
  storage; **`ssl_library`** — `OpenSSL` or empty; **`server_encoding`**,
  **`server_version`** (`PG_VERSION`), **`server_version_num`**
  (`PG_VERSION_NUM`, the integer form code compares against). [from-docs]

## Runtime-state "GUCs" (read-only, but not constant)

- **`in_hot_standby` (bool)** — true when the backend is on a standby still in
  recovery; forces the session read-only. Cleaner to test than catching the
  error on write. [from-docs]
- **`data_checksums` (bool)** — whether the cluster was `initdb -k`'d; the
  precondition for `ignore_checksum_failure` meaning anything. [from-docs]
- **`huge_pages_status` (enum on/off/unknown)** — actual huge-page state
  (reflects a `huge_pages=try` allocation result at startup); **`shared_memory_size`**
  (MB, rounded), **`shared_memory_size_in_huge_pages`** (`-1` if unsupported,
  Linux-only), **`num_os_semaphores`** (derived from `max_connections`,
  `autovacuum_max_workers`, `max_wal_senders`, `max_worker_processes`) — the
  three the DBA sizes kernel SHM/hugepage/semaphore limits from. [from-docs]
- **`data_directory_mode`** — PGDATA permissions at startup (Unix; `0700` on
  Windows). [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/storage-page-layout.md]] — what `block_size` shapes.
- [[knowledge/docs-distilled/storage-file-layout.md]] — the `segment_size` 1GB split.
- [[knowledge/docs-distilled/runtime-config-developer.md]] — `debug_assertions` gates the cassert-only knobs there.
- Skill: `build-and-run` — cassert build, `initdb -k`, geometry constants.

## Confidence note

All `[from-docs]` (Preset Options chapter, fetched 2026-07-02). 21 preset GUCs
present; the compile-macro names (`BLCKSZ`, `RELSEG_SIZE`, `NAMEDATALEN`,
`FUNC_MAX_ARGS`, `INDEX_MAX_KEYS`, `PG_VERSION_NUM`) are quoted by the page and
verified against pg_config.h.in conventions but not re-checked at the anchor SHA
this run.
