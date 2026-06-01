# `src/backend/utils/misc/sampling.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~300
- **Source:** `source/src/backend/utils/misc/sampling.c`

Sampling primitives shared by ANALYZE and `TABLESAMPLE`:
- `BlockSampler_Init`/`Next`/`HasMore` — Knuth's algorithm S over block
  numbers; selects a uniform random sample of `samplesize` blocks from
  `nblocks` total without replacement.
- `reservoir_init_selection_state` / `reservoir_get_next_S` — Vitter's
  Algorithm Z (reservoir sampling) for picking sample rows from blocks of
  unknown row count.
- `sampler_random_init_state(seed)` / `sampler_random_fract(state)` —
  reproducible PRNG (`pg_prng`-backed) used by `TABLESAMPLE BERNOULLI` /
  `SYSTEM`.

Used by ANALYZE (`commands/analyze.c`) and the four `tablesample`
methods in `access/tablesample/`. [from-comment]
