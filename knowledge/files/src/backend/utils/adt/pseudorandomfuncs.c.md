# `src/backend/utils/adt/pseudorandomfuncs.c`

## Purpose

SQL-callable wrappers around `common/pg_prng.h` — the backend's
non-cryptographic PRNG. Exposes `random()`, `random_normal(mean,
stddev)`, `setseed(seed)`, plus typed range overloads
`random(int4, int4)`, `random(int8, int8)`, `random(numeric, numeric)`,
`random(date, date)`, `random(timestamp, timestamp)`,
`random(timestamptz, timestamptz)`. Each session has its own PRNG
state (`prng_state` file-static), lazily seeded on first use. 273
lines total — thin façade.

## Key functions

- `initialize_prng` — `pseudorandomfuncs.c:47`. Tries
  `pg_prng_strong_seed(&prng_state)` first (reads /dev/urandom etc.
  per `common/pg_prng.c`); falls back to `now ^ (MyProcPid << 32)` if
  that fails. Runs once per session via `prng_seed_set` guard.
  `[verified-by-code]`
- `setseed` — `:75`. Range `[-1.0, 1.0]`; rejects NaN.
- `drandom`, `drandom_normal` — `:97`, `:115`. Uniform [0,1)
  via `pg_prng_double`; normal via Box–Muller-ish
  `pg_prng_double_normal`.
- `int4random`, `int8random`, `numeric_random` — `:139`, `:160`,
  `:181`. `CHECK_RANGE_BOUNDS` macro (`:33`) errors if `min > max`.
- `date_random`, `timestamp_random`, `timestamptz_random` — `:203`,
  `:229`, `:255`. Reject `-infinity`/`+infinity` endpoints.

## Phase D notes

The session-PRNG design means `random()` in one session is
predictable from any other `random()` value in the same session
(reverse-engineering the xoroshiro128** state). This is documented
behavior for `random()`. Users wanting unpredictable values must use
`pgcrypto.gen_random_bytes` or `gen_random_uuid` from `uuid-ossp` /
the in-core `gen_random_uuid()` which lives in `uuid.c`, NOT here.

Note: **`gen_random_uuid()` is NOT in this file.** It's defined in
`src/backend/utils/adt/uuid.c` and uses `pg_strong_random`
internally — see that file's doc (in batch B?). The naming in the
task brief was misleading — this file only holds the *weak* random
functions; the *strong* UUID generator is elsewhere.
`[verified-by-code]`

The fallback seed `now ^ (MyProcPid << 32)` is weak (low-entropy
seed when `/dev/urandom` reads fail — rare but possible in seccomp
sandboxes). Output of `random()` then becomes predictable to anyone
who knows the connection time and PID. Documented at `:51-54`.
`[from-comment]`

## Potential issues

- [ISSUE-crypto-weakness: SQL `random()` is seeded with weak fallback
  `now ^ MyProcPid << 32` when strong seeding fails, making session
  PRNG output potentially predictable — but this is documented
  behaviour for the weak `random()` family; users requiring
  unpredictability are directed to pgcrypto / uuid generators (low)]
  — `pseudorandomfuncs.c:56-64`
- [ISSUE-undocumented-invariant: `numeric_random` skips
  `CHECK_RANGE_BOUNDS` macro (comment: "Leave range bound checking
  to random_numeric()" at `:187`), so the macro is defined but not
  applied uniformly across all overloads. Defense-in-depth would
  apply the check here too in case `random_numeric` changes
  semantics. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
