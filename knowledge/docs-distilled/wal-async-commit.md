---
source_url: https://www.postgresql.org/docs/current/wal-async-commit.html
fetched_at: 2026-06-12T20:48:00Z
anchor_sha: e18b0cb
chapter: "30.4 Asynchronous Commit"
---

# Asynchronous Commit (docs §30.4)

`synchronous_commit=off` trades a bounded loss window for throughput — and the
key insight is that it loses *transactions* but never *corrupts*. `[from-docs]`.

## Non-obvious claims

- **Async commit returns success to the client before the commit WAL record is
  flushed.** The loss window is bounded at **3 × `wal_writer_delay`** (not 1×) —
  the WAL writer flushes every `wal_writer_delay` ms, and the 3× slack is
  deliberate so flushes tend to land on whole-page boundaries during busy
  periods. `[from-docs]`
- **The cardinal distinction: async commit risks data *loss*, never data
  *corruption*.** Recovery replays WAL up to the last flushed record and reaches
  a self-consistent state; only the unflushed tail is gone. `[from-docs]`
- **Causal ordering is preserved across the loss boundary:** if B depends on A,
  A cannot be lost while B survives — commits are replayed in order, so you can
  never see a torn dependency. `[from-docs]`
- **An immediate-mode shutdown == a crash** for this purpose: it discards
  unflushed async commits just like a power loss. `[from-docs]`
- **`synchronous_commit` is evaluated at the moment commit *begins*, not at
  transaction start**, and is freely per-transaction settable — so sync and
  async commits coexist in one database, and you can flip it mid-session for the
  next commit. `[from-docs]`
- **Some commits are forced synchronous regardless of the GUC:** utility
  commands whose effect touches the filesystem vs. logical state (e.g.
  `DROP TABLE`) and `PREPARE TRANSACTION` (two-phase). `[from-docs]`
- **Async commit ≠ `fsync=off`.** `fsync=off` disables *all* sync logic
  server-wide and lets an OS/hardware crash corrupt the database arbitrarily;
  async commit gets most of the same speedup *without* the corruption risk, and
  is per-transaction rather than global. `[from-docs]`
- **Async commit ≠ `commit_delay`.** `commit_delay` is a *synchronous* technique
  (a delay *before* flush to batch multiple commits into one flush) and is
  *ignored* under async commit. `commit_siblings` gates whether the delay is
  worth taking. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/wal.md]] — WAL overview.
- [[knowledge/docs-distilled/runtime-config-wal.md]] — the full GUC set
  (`synchronous_commit`, `wal_writer_delay`, `commit_delay`, `commit_siblings`,
  `fsync`).
- [[knowledge/subsystems/access-transam.md]] — `RecordTransactionCommit` and
  where the sync/async flush branch is taken.
- Skill: `wal-and-xlog` (XLogFlush vs. XLogBackgroundFlush), `gucs-bgworker-parallel`.

## Citations

- All `[from-docs]`. The commit-time sync/async branch is in
  `source/src/backend/access/transam/xact.c` (`RecordTransactionCommit`); the
  WAL writer loop is `source/src/backend/postmaster/walwriter.c`. Verify at
  anchor e18b0cb.
