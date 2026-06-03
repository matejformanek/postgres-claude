# src/include/common/pg_prng.h

## Purpose
Public header for the xoroshiro128** PRNG. Declares the state struct,
the global state vector, and the seeding/draw functions. Implementation
lives in `src/common/pg_prng.c`.

## API
```c
typedef struct pg_prng_state { uint64 s0, s1; } pg_prng_state;
extern PGDLLIMPORT pg_prng_state pg_global_prng_state;

extern void pg_prng_seed(pg_prng_state *state, uint64 seed);
extern void pg_prng_fseed(pg_prng_state *state, double fseed);
extern bool pg_prng_seed_check(pg_prng_state *state);

#define pg_prng_strong_seed(state) \
    (pg_strong_random(state, sizeof(pg_prng_state)) ? \
     pg_prng_seed_check(state) : false)

extern uint64 pg_prng_uint64(pg_prng_state *state);
extern uint64 pg_prng_uint64_range(pg_prng_state *, uint64 rmin, uint64 rmax);
extern int64  pg_prng_int64 / int64p / int64_range(...);
extern uint32 pg_prng_uint32(pg_prng_state *state);
extern int32  pg_prng_int32 / int32p(...);
extern double pg_prng_double(pg_prng_state *state);
extern double pg_prng_double_normal(pg_prng_state *state);
extern bool   pg_prng_bool(pg_prng_state *state);
```

## Role in PG
- The `pg_global_prng_state` is the default seed source for "I need
  *some* randomness, doesn't have to be strong" — sampling, planner
  jitter, GiST tie-breaks, DSM handle allocation, etc.
- The `pg_prng_state` typedef is `PGDLLIMPORT`-exported so extensions
  can embed it (`pg_prng.h:17-23`).
- `pg_prng_strong_seed` is a **macro, not a function** (`pg_prng.h:46-48`)
  on purpose: keeps the `pg_strong_random` symbol unreferenced from
  callers that don't want to drag in OpenSSL. [from-comment: pg_prng.h:40-45]

## State / globals
`pg_global_prng_state` — extern. Defined in `pg_prng.c:34`.

## Phase D notes
- **Macro vs function for strong seed** keeps the `pg_strong_random.c`
  ↔ libcrypto dependency localized to callers that explicitly opt in.
  Frontend tools that just want PRNG (e.g. pgbench's random seed) avoid
  the OpenSSL pull-in.
- **Header exposes raw state struct** so extensions can embed it.
  Reviewers should watch for extensions that read/write `s0`/`s1`
  directly — they should go through `pg_prng_seed` to ensure
  non-all-zero state.

## Potential issues
- [ISSUE-undocumented-invariant: extensions can write s0/s1 directly via
  the exposed struct. If they set both to zero, the xoroshiro fixed
  point makes every subsequent draw return 0. The pg_prng_seed_check
  function is offered but not enforced. (low)]
