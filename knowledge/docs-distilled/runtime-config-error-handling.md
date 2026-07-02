---
source_url: https://www.postgresql.org/docs/current/runtime-config-error-handling.html
fetched_at: 2026-07-01T20:47:00Z
anchor_sha: c776550e4662
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Error Handling configuration

Four small but load-bearing durability/availability GUCs. Companion:
`knowledge/idioms/error-handling.md`, `knowledge/docs-distilled/wal-reliability.md`,
skill `error-handling`, `wal-and-xlog`.

## The fsync-failure PANIC is deliberate

- **`data_sync_retry` (default off, restart-only) means a failed data-file
  `fsync()` PANICs the server** rather than retrying. This is the safer default
  because on some kernels (notably Linux, the "fsyncgate" behavior) a **failed
  fsync may discard the dirty page, so a subsequent fsync falsely returns
  success** — silently losing the write. Only set `on` after you've verified
  your OS's write-back-failure semantics. [from-docs]
- **`recovery_init_sync_method` (default `fsync`, restart-only)**: `fsync`
  recursively opens+syncs every data file before crash recovery (safe, slow);
  `syncfs` (Linux) syncs whole filesystems at once (fast, but may sync unrelated
  files, and pre-5.8 Linux may not surface I/O errors to PG). [from-docs]

## Availability knobs

- **`restart_after_crash` (default on, SIGHUP-file/CLI) makes the postmaster
  reinitialize after a backend crash** to maximize uptime. **Set `off` for
  clusterware** that wants to detect the crash and drive failover itself instead
  of letting PG bounce. [from-docs]
- **`exit_on_error` (default off)**: off = only FATAL ends the session, ordinary
  ERRORs let it continue; on = *any* error terminates the current session.
  [from-docs]

## Links into corpus

- [[knowledge/idioms/error-handling.md]] — ereport/elog elevels (FATAL/PANIC).
- [[knowledge/docs-distilled/wal-reliability.md]] — the durability contract.
- [[knowledge/docs-distilled/runtime-config-wal.md]] — `fsync` /
  `full_page_writes` siblings.
- Skill: `error-handling` (PANIC elevel), `wal-and-xlog` (crash recovery).

## Confidence note

All claims `[from-docs]` (Error Handling chapter, fetched 2026-07-01). The
fsync-failure PANIC path lives in `src/backend/storage/file/fd.c`
(`data_sync_elevel`); `[from-docs]`-only here.
