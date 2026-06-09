# contrib/tsm_system_rows/tsm_system_rows.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 342
**Verification depth:** full read

## Role

Implements the `SYSTEM_ROWS(n)` TABLESAMPLE method — block-level sampling
that returns approximately `n` random rows (or the whole relation if fewer
rows exist), advancing through blocks via a linear-probing scheme with
a randomly chosen stride that is relatively prime to `nblocks`.
[verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:1-26`

## Public API

- `tsm_system_rows_handler` (PG_FUNCTION_INFO_V1) — returns a `TsmRoutine`
  node with `parameterTypes=[INT8]`, `repeatable_across_queries=false`,
  `repeatable_across_scans=true`, and the five callbacks
  (SampleScanGetSampleSize, InitSampleScan, BeginSampleScan,
  NextSampleBlock, NextSampleTuple).
  [verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:80-99`

## Invariants

- INV-1: NOT repeatable across queries (nblocks may change), but IS
  repeatable across scans of the same query — pattern (firstblock+step)
  is computed once on first NextSampleBlock and frozen for the query.
  [verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:212-241`
- INV-2: `step` must be relatively prime to `nblocks` so that linear
  probing visits every block (full cycle) if needed.
  [verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:235-236, 321-342`
- INV-3: For `n < 0` the sampler errors out
  (`ERRCODE_INVALID_TABLESAMPLE_ARGUMENT`).
  [verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:182-185`
- INV-4: Sampling uses `pagemode` visibility checking — forced regardless
  of executor default.
  [verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:194-198`
- INV-5: Loop in `random_relative_prime` has a `CHECK_FOR_INTERRUPTS` so
  pathological `nblocks` (very small or with few coprimes) can't hang
  the backend indefinitely.
  [verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:330-342`

## Notable internals

- PRNG: `sampler_random_init_state(seed, &randstate)` +
  `sampler_random_fract(&randstate)` — see `utils/sampling.h`. These are
  the standard PG sampler RNG, NOT cryptographic. Seed is derived
  externally (per-scan).
  [verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:224-225, 232`
- Cost estimation: tuple-density-aware estimate of pages visited; clamps
  `ntuples` to `baserel->tuples` and `npages` to `baserel->pages`.
  Default `ntuples=1000` if `n` isn't a knowable Const.
  [verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:101-158`
- Linear probing uses `uint64` arithmetic to forestall overflow when
  advancing `lb + step`.
  [verified-by-code] `source/contrib/tsm_system_rows/tsm_system_rows.c:254-258`
- The do-while loop at line 254-258 handles the edge case where
  `nblocks` could decrease between scans (truncation between rescans);
  it re-rolls until a valid block is found.

## Trust-boundary / Phase-D surface

- **`ntuples` is INT8** — clamped to `baserel->tuples` (a double) in
  the estimator. In `BeginSampleScan` (param 0) it's read as Int64
  and rejected if negative; no overflow risk on positive overflows of
  `donetuples >= ntuples` comparison because donetuples is also int64.
- **Seed** comes from the caller; not security-meaningful.
  Sampling determinism is by design (REPEATABLE clause).
- **Timing leak via sample selection**: block-level sampling reveals
  storage distribution information — an attacker who can repeatedly
  invoke TABLESAMPLE on a table they can read learns nblocks (since
  the cycle length depends on it). This is *not* exploitable for
  reading rows the role lacks SELECT on (visibility is still enforced
  by HeapTupleSatisfiesVisibility downstream), but it does leak
  *physical layout*. **ISSUE-D1 (info)**: physical layout leak via
  block sampling is documented behavior; mark as informational.
- **`pagemode` visibility forced** [verified-by-code:194-198] — this
  matters: in pagemode, visibility is computed up-front for all tuples
  on a page. Without it, certain CHECK_FOR_INTERRUPTS placements
  could observe partial visibility snapshots. The author specifically
  forces it.

## Cross-refs

- `source/src/backend/utils/misc/sampling.c` — `sampler_random_*`.
- `source/src/backend/access/tablesample/` — TABLESAMPLE infra.
- A13 `tablesample` builtin BERNOULLI/SYSTEM methods.
- Sibling: `contrib/tsm_system_time/tsm_system_time.c`.

## Issues raised

- **ISSUE-D1 (info)** — block-sampling leaks physical layout (nblocks)
  to a role with SELECT but not other introspection. Documented
  behavior; not a bug.
