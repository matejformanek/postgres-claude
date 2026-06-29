# `src/include/lib/hyperloglog.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 68 (header + MIT preamble)

## Role

Approximate distinct-cardinality estimator. Used by:

- `analyze.c` `compute_scalar_stats` — for n_distinct estimation
- `tuplesort.c` abbreviated-key cardinality cross-check
  (abandons abbrev keys if cardinality too high)
- `nbtree` parallel-build estimation

[verified-by-code] `source/src/include/lib/hyperloglog.h:39-43`

## Public API

- `initHyperLogLog(state, bwidth)` — bwidth ∈ [4..16] effectively;
  controls register count = 1 << bwidth
- `initHyperLogLogError(state, error)` — choose bwidth from
  target error rate
- `addHyperLogLog(state, hash)` — hash is caller-supplied uint32
- `estimateHyperLogLog(state)` → double
- `freeHyperLogLog(state)`

## Invariants

- INV-1: caller supplies *already-hashed* uint32 values. Hash
  quality is caller's responsibility. [from-comment]
- INV-2: register width is fixed `uint8` per register (line 58).

## Trust boundary (Phase D)

Used inside ANALYZE which itself runs SuperuserOnly funcs (e.g.
import/export of stats via `pg_set_relation_stats` etc.).
**A11 postgres_fdw stats-import angle:** an attacker who can
influence the hashes fed to HLL during a cross-server stats
import could skew n_distinct estimates → planner mis-chooses
plans → secondary side-effects (resource exhaustion, plan-shape
oracle). [inferred — no current exploit demonstrated]

## Cross-refs

- `knowledge/files/contrib/postgres_fdw/` (A11) — stats-import
  attack surface
- `knowledge/files/src/include/lib/bloomfilter.h.md` — sister
  approximate-set primitive

## Issues

- ISSUE-TRUST: stats-import path is a planner oracle vector; HLL
  is a small part of that but worth tagging. (Low.)

## Synthesized by
<!-- backlinks:auto -->
- [idioms/aggregate-hash-vs-sort.md](../../../../idioms/aggregate-hash-vs-sort.md)
