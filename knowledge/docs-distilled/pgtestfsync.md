---
source_url: https://www.postgresql.org/docs/current/pgtestfsync.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: wal-control-recovery-tools (2026-06-29 refill)
---

# pg_test_fsync — micro-benchmark the wal_sync_method options

`pg_test_fsync` measures per-operation latency/throughput of each
`wal_sync_method` so you can pick the fastest *safe* WAL-flush method for your
storage, and validate that the storage actually honors fsync. `[from-docs]`

## Non-obvious claims

- **It reports average sync time in microseconds per method** — and the docs
  note this also informs `commit_delay` tuning, not just `wal_sync_method`.
  `[from-docs]`
- **Caveat the docs lead with:** the differences it shows "might not translate
  to significant database throughput improvements," because many servers are
  not WAL-write-bound. Treat it as a storage characterization, not a promise of
  TPS. `[from-docs]`
- **Durability self-test.** The "Non-sync'ed 8kB writes" section tests whether
  `fsync()` on a *non-write* file descriptor is honored — i.e. whether the
  storage stack respects fsync ordering at all. A developer reasoning about
  durability guarantees reads this section to confirm the platform isn't lying
  about flushes. `[from-docs]`
- **Test file must sit on the same filesystem as `pg_wal`** for the numbers to
  be meaningful (default `pg_test_fsync.out` in cwd; override with `-f`).
  `[from-docs]`
- **`open_datasync` is frequently the platform default** where available, for
  its performance/safety balance — but the tested *set* is platform-dependent.
  `[from-docs]`

## Output sections

1. One 8kB write, compare sync methods (baseline).
2. Two 8kB writes, compare sync methods (batching behavior).
3. Compare `open_sync` write sizes.
4. Non-sync'ed 8kB writes (the fsync-honored durability probe above).
5. `open_datasync` vs `fdatasync` direct comparison.

## Sync methods benchmarked (platform subset)

`open_datasync`, `open_sync`, `fdatasync`, `fsync`, `fsync_writethrough`. The
write-then-explicit-sync methods (`fdatasync`/`fsync`) vs sync-on-write methods
(`open_datasync`/`open_sync`) are the two families the output contrasts.
`[from-docs]`

## Options

| Flag | Meaning |
|---|---|
| `-f`, `--filename=NAME` | Test file (default `pg_test_fsync.out` in cwd; put on the `pg_wal` filesystem). |
| `-s`, `--secs-per-test=N` | Seconds per test (default 5); longer = more accurate, slower. |

## Links into corpus

- `[[knowledge/docs-distilled/wal-configuration.md]]`,
  `[[knowledge/docs-distilled/runtime-config-wal.md]]` — the `wal_sync_method`
  and `commit_delay` GUCs this benchmark feeds.
- `[[knowledge/docs-distilled/wal-reliability.md]]` — why honoring fsync is the
  durability cornerstone the "non-sync'ed" section probes.
- `[[knowledge/docs-distilled/pgtesttiming.md]]` — sibling micro-benchmark
  (timing-call overhead) in the same Reference family.
- Skill: `wal-and-xlog`, `build-and-run`, `testing`.
