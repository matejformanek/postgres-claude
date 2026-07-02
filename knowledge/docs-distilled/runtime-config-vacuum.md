---
source_url: https://www.postgresql.org/docs/current/runtime-config-vacuum.html
fetched_at: 2026-07-01T20:47:00Z
anchor_sha: c776550e4662
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Vacuuming (Cost-Delay + Automatic Vacuuming GUCs)

The vacuum/autovacuum GUC reference, distilled to the *surprising* clamps and
formulas. Companion: `knowledge/docs-distilled/routine-vacuuming.md` for the
mechanism these knobs tune. **Note:** the autovacuum-GUC page moved from
`runtime-config-autovacuum.html` → `runtime-config-vacuum.html` in current docs
(the old slug 301-redirects). Cite by slug, not chapter number.

## Freeze-age silent clamps (the biggest footgun)

- **Every manual freeze knob is silently clamped to a fraction of the
  autovacuum max-age**, so a user-set value can be quietly ignored [from-docs]:
  - `vacuum_freeze_table_age` (default 150M) → capped at **95%** of
    `autovacuum_freeze_max_age`.
  - `vacuum_freeze_min_age` (default 50M) → capped at **50%** of
    `autovacuum_freeze_max_age` (prevents pathologically frequent forced
    autovacuums).
  - `vacuum_multixact_freeze_table_age` (150M) / `_min_age` (5M) → same 95% /
    50% caps against `autovacuum_multixact_freeze_max_age`.
- **`vacuum_failsafe_age` (default 1.6B) is silently raised to ≥105% of
  `autovacuum_freeze_max_age`.** When it trips, VACUUM **disables the cost
  delay, skips index vacuuming, and abandons the Buffer Access Strategy ring
  (uses all of shared_buffers)** — pure wraparound-avoidance mode.
  `vacuum_multixact_failsafe_age` is the multixact twin. [from-docs]

## Autovacuum trigger formulas

- **Dead-tuple threshold**: vacuum when obsolete tuples exceed
  `MIN(autovacuum_vacuum_max_threshold, autovacuum_vacuum_threshold +
  autovacuum_vacuum_scale_factor × reltuples)`. Defaults 50 + 0.2·N, capped at
  **100,000,000** (`autovacuum_vacuum_max_threshold`, set −1 to disable the
  cap). [from-docs]
- **Insert-only path is separate**: `autovacuum_vacuum_insert_threshold`
  (default 1000, −1 disables) + `autovacuum_vacuum_insert_scale_factor` (0.2).
  **Anomaly: the insert scale factor multiplies *unfrozen pages*, not table
  size** — unlike every other scale factor which multiplies `reltuples`.
  [from-docs]
- **Analyze threshold**: `autovacuum_analyze_threshold` (50) +
  `autovacuum_analyze_scale_factor` (0.1) × reltuples. [from-docs]

## Cost-based delay arithmetic

- **`vacuum_cost_delay` default is 0 (disabled)** for manual VACUUM; only the
  `autovacuum_vacuum_cost_delay` (default **2ms**) path is on out of the box.
  Page costs: hit=1, miss=2, dirty=20; `vacuum_cost_limit` default 200.
  [from-docs]
- **Actual sleep = `delay × (accumulated_balance / limit)`, capped at `4 ×
  delay`.** Work under a critical lock ignores the delay entirely, so the
  balance can overshoot the limit before the next nap. [from-docs]
- **`autovacuum_vacuum_cost_limit` (default −1 = inherit) is DIVIDED among
  running workers**, not per-worker: more workers ⇒ each throttles harder. A
  table with a per-table cost_delay/cost_limit is *excluded* from this
  balancing. [from-docs]

## Worker slots and always-on wraparound

- **`autovacuum` default on; even `off` still launches workers to prevent XID
  wraparound.** Requires `track_counts=on` to function at all. [from-docs]
- **`autovacuum_max_workers` (default 3) is hard-capped by
  `autovacuum_worker_slots` (default 16, postmaster-only)** — setting workers
  above slots has no effect. `autovacuum_naptime` default 1min. All three are
  postmaster-only; most per-*table* thresholds are overridable via storage
  parameters. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/routine-vacuuming.md]] — the wraparound / freeze /
  daemon mechanism these GUCs drive.
- [[knowledge/subsystems/access-heap.md]] — heap freeze, `relfrozenxid`.
- [[knowledge/subsystems/access-transam.md]] — XID/multixact SLRU spaces.
- [[knowledge/docs-distilled/runtime-config-resource.md]] —
  `autovacuum_work_mem` / `vacuum_buffer_usage_limit` live there.
- Skill: `gucs-config` — GucContext for postmaster-only vs SIGHUP knobs.

## Confidence note

All claims `[from-docs]` (Server Configuration → Vacuuming, fetched
2026-07-01). Defaults quoted as on the page; not re-verified against
`guc_tables.c`/`vacuum.c` this run (a future pg-quality-auditor pass could pin
each clamp to a source line).
