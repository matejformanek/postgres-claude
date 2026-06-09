# utils/sampling.h — block + reservoir sampling primitives

Source: `source/src/include/utils/sampling.h` (64 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Shared sampling algorithms used by ANALYZE, TABLESAMPLE, and (legacy) FDWs. Wraps `pg_prng` to provide a sampler-specific PRNG state.

## Public API

- `sampler_random_init_state(seed, &randstate)` (`sampling.h:21-22`).
- `sampler_random_fract(&randstate)` (`sampling.h:23`) — random in [0, 1).
- `BlockSamplerData` (`sampling.h:28-35`): Knuth Algorithm S state — N (total blocks), n (sample size), t (current block), m (selected so far), randstate.
- `BlockSampler_Init(bs, nblocks, samplesize, randseed)` (`sampling.h:39-40`).
- `BlockSampler_HasMore`, `BlockSampler_Next` (`sampling.h:41-42`).
- `ReservoirStateData` (`sampling.h:46-50`): Vitter Algorithm Z state.
- `reservoir_init_selection_state`, `reservoir_get_next_S` (`sampling.h:54-55`).
- Legacy API (`sampling.h:58-62`): `anl_random_fract`, `anl_init_selection_state`, `anl_get_next_S` — still in use by external FDWs; declarations duplicated in vacuum.h.

## Invariants

- **INV-Algorithm-S-Knuth-3.4.2** [from-comment, `sampling.h:27`]: BlockSampler implements Knuth's Algorithm S for selecting n blocks out of N known up front. Requires N (total nblocks) known at init.
- **INV-Vitter-Algorithm-Z** [verified-by-code, name `reservoir_get_next_S`]: classic Vitter reservoir sampling for unknown population sizes.
- **INV-PRNG-pg_prng** [verified-by-code, `sampling.h:16`]: PRNG state is `pg_prng_state` from common/pg_prng.h — same xoroshiro generator backbone.
- **INV-legacy-anl_*-duplicated-in-vacuum-h** [from-comment, `sampling.h:58-59`]: "For backwards compatibility, these declarations are duplicated in vacuum.h." Drift risk between the two locations.

## Trust-boundary / Phase-D surface

- **`randseed` is uint32** (`sampling.h:39`) — only 32 bits of entropy; for ANALYZE this is fine (sampling correctness, not security). NOT suitable for security-relevant sampling.
- **`pg_prng` is NOT a CSPRNG** — for any security need (UUID generation, cryptographic shuffling), use `pg_strong_random` instead.

## Cross-refs

- `source/src/include/common/pg_prng.h` — underlying PRNG.
- `source/src/backend/commands/analyze.c` — ANALYZE consumer.
- `source/src/backend/access/tablesample/*.c` — TABLESAMPLE consumers.
- `source/src/include/commands/vacuum.h` — duplicated legacy declarations.

## Issues

- `[ISSUE-DRIFT: duplicated declarations between sampling.h and vacuum.h (low)]` — `sampling.h:58-59` admits this; without a build-time crosscheck, signature changes can drift.
- `[ISSUE-DOC: pg_prng not security-grade (info)]` — worth a one-line warning to discourage reuse for security-sensitive code.
