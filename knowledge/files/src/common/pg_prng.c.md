# src/common/pg_prng.c

## Purpose
PostgreSQL's process-local pseudo-random number generator. Implements
Blackman and Vigna's xoroshiro128** 1.0 (`pg_prng.c:5-11`), a small fast
128-bit-state PRNG. **Not cryptographically strong** — that's explicit at
file header (`pg_prng.c:7-8`). Strong randomness lives in
`src/port/pg_strong_random.c`.

## Role in PG
- Global `pg_global_prng_state` (`pg_prng.c:34`) seeded once in
  `PostmasterMain` via `pg_prng_strong_seed` (postmaster.c:1971) — falls
  back to `pg_prng_seed(rseed)` derived from time+PID if strong-random is
  unavailable. Inherited by every forked backend.
- Used pervasively for *non-security* randomness:
  - vacuum/sampling/analyze (`vacuumlazy.c:589`, `sampling.c:139,271,286`,
    `analyze.c:1286`)
  - lock backoff jitter (`s_lock.c:159`)
  - planner/GEQO randomization (`geqo_random.c`)
  - GiST/SP-GiST tie-breaking (`gistutil.c:511,533`, `spgdoinsert.c:2210`)
  - catcache stats sampling (`catcache.c:2185`)
  - `random()`/`gen_random_uuid v4`/`random_normal()` SQL functions
    (`pseudorandomfuncs.c`, `uuid.c` uses pg_strong_random instead — good)
  - DSM control handle allocation (`dsm.c:221,581,1284`) — **see Phase D**
  - temp tablespace choice (`fd.c:3112`)

## Key functions
- `pg_prng_seed(state, seed)` (`pg_prng.c:88`) — initialize state vector
  from a 64-bit seed via `splitmix64`, falling through `pg_prng_seed_check`
  to ensure non-zero state (xoroshiro all-zero is a fixed point).
- `pg_prng_fseed(state, fseed)` (`pg_prng.c:102`) — seed from double in
  [-1.0, 1.0]. Used by SQL `setseed(double)`.
- `pg_prng_seed_check(state)` (`pg_prng.c:114`) — substitute Knuth LCG
  constants if state is all-zero.
- `pg_prng_uint64`, `pg_prng_uint64_range(rmin,rmax)` (`pg_prng.c:134, 144`)
  — uniform 64-bit. Range uses bitmask-rejection method.
- `pg_prng_int64`, `pg_prng_int64p` (non-negative), `pg_prng_int64_range`
  (`pg_prng.c:173, 182, 192`) — signed variants; range carefully avoids
  signed-overflow UB on conversion (`pg_prng.c:200-216`).
- `pg_prng_uint32`/`pg_prng_int32`/`pg_prng_int32p`/`pg_prng_double`/
  `pg_prng_double_normal`/`pg_prng_bool` (`pg_prng.c:227-318`). All
  consume the **high** 32 or 1 bits of one xoroshiro draw — the comment
  at line 230-233 explains: "*we prefer to use the upper bits of its result
  here and below.*" xoroshiro low bits are weaker in theory.
- `pg_prng_double_normal` uses Box–Muller transform (`pg_prng.c:289-307`).

## State / globals
`pg_prng_state pg_global_prng_state` (`pg_prng.c:34`) — a `{uint64 s0, s1}`
pair. Declared `PGDLLIMPORT` in `pg_prng.h:29`. Per-backend copy via fork
inheritance — the postmaster seed is shared across all backends until a
backend explicitly reseeds (e.g. session-level `setseed`).

## Phase D notes
- **`pg_strong_random` availability vs `pg_prng` callsites.**
  `pg_strong_random` is provided by `src/port/pg_strong_random.c` and is
  always available (it falls back from OpenSSL → Windows CryptoAPI →
  `/dev/urandom`). It can still *fail* (returns bool), which is why
  `pg_prng_strong_seed` is a macro that bails to a weaker seed.
  [verified-by-code: postmaster.c:1971-1986]
- **Audit of pg_prng usage that *might* want pg_strong_random:**
  1. `dsm.c:221, 581, 1284` — DSM segment **handle** generation. The
     handle becomes part of the POSIX shared-memory object name on some
     platforms (`/dev/shm/PostgreSQL.<handle>`). A local attacker who can
     predict handles could pre-create the shm name to interfere with
     parallel query setup. Currently uses `pg_prng_uint32` on the global
     prng. The state is seeded once at postmaster start from
     `pg_strong_random` (when available), but is a deterministic stream
     after that and is *inherited by every forked backend with the
     parent's advanced state* — meaning any backend can observe sibling
     output to some extent.
     **Severity: maybe — race window is narrow and the code already
     retries on collision; but a hardened-postgres reviewer would prefer
     strong-random for handle generation.**
  2. `xact.c:2134` (log_xact_sample_rate), `postgres.c:2477`
     (log_statement_sample_rate), `catcache.c:2185` — sampling decisions.
     **Not security-sensitive.** Weak prng is correct.
  3. `pseudorandomfuncs.c` — SQL `random()`. **Documented as not
     cryptographic** in user-facing docs. Correct as-is.
  4. `nbtinsert.c:985` — kill-prior-tuple sampling. Not security.
  5. `s_lock.c:159` — spin backoff jitter. Not security.
  6. `gistutil.c:511,533`, `spgdoinsert.c:2210` — index tie-breaking. Not
     security.
- **Inherited-state issue.** Because postmaster seeds *once* and every
  child fork inherits the same `pg_global_prng_state`, in theory a
  long-lived backend that has consumed many draws can be predicted from
  another backend that observes the postmaster's startup time. Each
  child does *not* reseed on fork — only `pseudorandomfuncs.c` and a few
  others optionally do. [verified-by-code: postmaster.c:1971,
  fork_process.c:117 reinits *pg_strong_random*, not pg_prng]
- **All-zero state guard.** `pg_prng_seed_check` substitutes Knuth LCG
  constants. Good — protects against the documented xoroshiro fixed point.
  However, `pg_prng_fseed(0.0)` will compute `seed = 0`, then `splitmix64`
  on 0 yields non-zero output, so the all-zero exit is unreachable from
  `pg_prng_seed` itself (the check is defensive against future callers
  who might write `state->s0 = state->s1 = 0` directly).
- **No timing-side-channel risk** in xoroshiro itself — constant-time
  shifts/xors/rotates. `pg_prng_uint64_range` is *not* constant-time
  (bitmask rejection loop) but its output is not used in
  security-sensitive comparisons.

## Potential issues
- [ISSUE-crypto-weakness: DSM control-handle generation uses pg_prng_uint32
  (dsm.c:221,581,1284) rather than pg_strong_random. Local attacker on
  same host could potentially predict shm object names. The current code
  retries on collision, so functionally safe; but defense in depth would
  argue for strong random. (maybe)]
- [ISSUE-undocumented-invariant: pg_global_prng_state is fork-inherited
  unchanged. Two long-lived sibling backends share a derived stream. Not
  exploited anywhere known, but worth documenting. (maybe)]
- [ISSUE-stale-todo: pg_prng_fseed wraps the double into a 52-bit int64
  scale and feeds to splitmix64. This loses precision and could give
  surprising results for SQL `setseed` values very close to ±1. Not a
  security bug — just a documentation/precision quirk. (maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
