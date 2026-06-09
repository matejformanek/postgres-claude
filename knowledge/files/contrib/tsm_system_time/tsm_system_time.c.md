# contrib/tsm_system_time/tsm_system_time.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 356
**Verification depth:** full read

## Role

Implements the `SYSTEM_TIME(millis)` TABLESAMPLE method — block-level
sampling that returns as many rows as can be retrieved within `millis`
milliseconds.  Same linear-probing scheme as `tsm_system_rows`, but the
stopping condition is wall-clock time elapsed since the start of the
scan (`INSTR_TIME_*` monotonic timer).
[verified-by-code] `source/contrib/tsm_system_time/tsm_system_time.c:1-23`

## Public API

- `tsm_system_time_handler` — `parameterTypes=[FLOAT8]`,
  `repeatable_across_queries=false`, `repeatable_across_scans=false`
  (time is inherently unrepeatable).
  [verified-by-code] `source/contrib/tsm_system_time/tsm_system_time.c:81-100`

## Invariants

- INV-1: `millis < 0` or NaN errors out
  (`ERRCODE_INVALID_TABLESAMPLE_ARGUMENT`).
  [verified-by-code] `source/contrib/tsm_system_time/tsm_system_time.c:199-202`
- INV-2: Sampling pattern (firstblock + step) frozen on first
  `NextSampleBlock` and not recomputed between scans within the same
  query, mirroring `tsm_system_rows`.
  [verified-by-code] `source/contrib/tsm_system_time/tsm_system_time.c:223-249`
- INV-3: Time budget enforced via wall-clock check at the *block
  boundary* — NOT via `CHECK_FOR_INTERRUPTS` or anywhere mid-block.
  [verified-by-code] `source/contrib/tsm_system_time/tsm_system_time.c:260-264`
- INV-4: Loop in `random_relative_prime` has `CHECK_FOR_INTERRUPTS`
  protection.
  [verified-by-code] `source/contrib/tsm_system_time/tsm_system_time.c:344-355`

## Notable internals

- Cost estimation translates milliseconds to expected page reads via
  the planner's `random_page_cost` tablespace setting, with the
  comment "completely, unmistakably bogus" — author knows it's a
  hack but has to estimate *something* for the planner.
  [verified-by-code] `source/contrib/tsm_system_time/tsm_system_time.c:138-155`
- Timer is `instr_time` (monotonic on Linux/Darwin via
  `CLOCK_MONOTONIC` — see `portability/instr_time.h`), measured as
  `start_time` set on first `NextSampleBlock` call in the scan,
  then `cur_time - start_time` compared on each subsequent call.
  [verified-by-code] `source/contrib/tsm_system_time/tsm_system_time.c:253, 261-263`

## Trust-boundary / Phase-D surface

- **Time budget check happens AT block boundary, not per-tuple**.
  That means a single block scan can overshoot the budget by however
  long it takes to scan one block + run the per-tuple visibility check.
  **ISSUE-D1 (low)**: a malicious user can't get unbounded query
  time but CAN reliably get one-block-worth-of-time beyond the budget.
  For typical block sizes this is bounded (microseconds), so it's a
  documentation issue not a security one.
- **Visibility leaks via block sampling**: same as `tsm_system_rows`
  — physical layout (nblocks) leaks. Additionally, since
  `repeatable_across_scans=false`, repeated execution gives the
  attacker a way to *cover* the table via random walks over many
  scans.
- **Wall-clock dependence**: the budget is `INSTR_TIME_GET_MILLISEC`
  which on POSIX is monotonic, so the user can't manipulate it by
  e.g. fooling NTP. Good.
- **`pagemode` is NOT forced here** [verified-by-code:188-210] — unlike
  `tsm_system_rows`. **ISSUE-D2 (info)**: asymmetry with the sister
  module. Probably intentional (time-based sampling doesn't need
  the same guarantees) but worth flagging because a copy-paste
  reviewer would expect the same.
- **CHECK_FOR_INTERRUPTS at block boundary?** None — the time check
  itself acts as a natural interrupt opportunity. **ISSUE-D3 (low)**:
  if `millis` is huge (say 24h via `SYSTEM_TIME(86400000)`) and the
  table is small (so the linear-prober wraps), there's NO
  CHECK_FOR_INTERRUPTS in `NextSampleBlock` itself, just the one
  inside `random_relative_prime`. The block read path likely calls
  one via tableam, but the worst-case is the scan loops over the
  whole relation many times without backend cancel responsiveness.
  [inferred] from absence of `CHECK_FOR_INTERRUPTS` in
  `system_time_nextsampleblock` line 217-279.

## Cross-refs

- Sibling `contrib/tsm_system_rows/tsm_system_rows.c`.
- `source/src/include/portability/instr_time.h`.
- `source/src/backend/utils/cache/spccache.c` — `get_tablespace_page_costs`.

## Issues raised

- **ISSUE-D1 (low)** — time budget enforced at block boundary, can
  overshoot by one block's worth of work. Documentation, not security.
- **ISSUE-D2 (info)** — asymmetry with `tsm_system_rows`: pagemode NOT
  forced here.
- **ISSUE-D3 (low)** — no `CHECK_FOR_INTERRUPTS` in the inner
  block-stepping loop; relies on tableam's own interrupt checks.
