---
path: src/test/isolation/isolationtester.c
anchor_sha: e18b0cb7344
loc: 1142
depth: read
---

# src/test/isolation/isolationtester.c

## Purpose

The **C utility that runs a single isolation-test `.spec` file**,
spawned per-test by `pg_isolation_regress`. Reads a spec from stdin
(via the bison grammar in `specparse.y` + flex tokenizer in
`specscanner.l`), opens one libpq connection per declared session
plus an extra **control connection** for lock-wait probing, and then
either runs every named permutation (if `permutation` directives are
present) or generates **all possible interleavings** of the steps
across sessions. For each permutation it dispatches each step on its
owning session's connection, polls for lock waits via
`pg_isolation_test_session_is_blocked()`, handles blocker annotations
(`(*)`, `(otherstep)`, `(N notices from session)`), and emits a
human-readable trace that the regression diff compares against
`expected/*.out`. This is the **concurrency / deadlock test spine** —
without it there's no way to write reproducible multi-session SQL
tests. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int main(int argc, char **argv)` | `:86-246` | parses `-V`, opens conns, runs spec |
| (no other extern functions — everything else is static) | | parser hooks come from `isolationtester.h` |

## Internal landmarks

### Connection model

- `typedef struct IsoConnInfo` (`:25-38`): per-connection record
  holding the PGconn pointer, backend PID (numeric + string), the
  session name, an `active_step` pointer (NULL when idle), and a
  `total_notices` counter for `PSB_NUM_NOTICES` blockers.
- `conns[0]` is the **control / watchdog connection** used for
  global setup/teardown and the prepared lock-wait probe;
  `conns[1..nsessions]` are the per-session connections. Comment
  at `:22-24`. `[from-comment]`
- All connections share one conninfo string (`:164`). Application
  name is **appended** (not set) with `set_config('application_name',
  current_setting('application_name') || '/' || $1, false)` (`:194-198`)
  so log lines / pg_stat_activity show e.g. `isolation/foo/session1`.
  Comment at `:187-192` explains why append vs. set. `[from-comment]`
- `disconnect_atexit()` (`:76-84`) — `PQfinish` every open conn.

### Lock-wait detection

- Prepared statement `PREP_WAITING` ("isolationtester_waiting",
  `:19`): `SELECT pg_catalog.pg_isolation_test_session_is_blocked(
  $1, '{pid1,pid2,...}')` (`:220-227`). The backend function
  filters out non-test waits (e.g. autovacuum's transient
  AccessExclusiveLock during truncation), per the comment at
  `:213-219`. `[from-comment]`
- `max_step_wait` default is 360 seconds (`:47`). Overridden by env
  `PG_TEST_TIMEOUT_DEFAULT` via `max_step_wait = 2 * atoi * USECS_PER_SEC`
  (`:132-134`).

### Spec validation: `check_testspec()` (`:251-387`)

- Builds a sorted `allsteps[]` lookup (`:265-274`), enforces step-name
  uniqueness across ALL sessions (`:277-286`) — duplicates exit 1.
- Sets `Step.session` index back-pointers (`:288-295`).
- For every PermutationStep, `bsearch` resolves the step name to its
  `Step *` (`:308-320`); undefined → exit 1.
- Marks `step->used = true` so unused-step warnings can fire (`:323`).
- Resolves blocker `stepname` to the actual `Step *` referenced within
  the same permutation (`:336-360`).
- Rejects blockers that reference a step in the SAME session as the
  step being annotated (`:362-367`) — a session can't block on itself.
- Auto-generated permutations skip the "unused step" warning loop
  (`:377-384`). `[from-comment]`

### Permutation generation

- `run_testspec()` (`:393-400`): dispatches to either
  `run_named_permutations` or `run_all_permutations`.
- `run_all_permutations()` (`:405-443`): builds a workspace array
  of `PermutationStep`s, calls `run_all_permutations_recurse`.
- `run_all_permutations_recurse()` (`:445-480`): the standard
  pile-shuffling recursion — at each level, pick any session whose
  pile still has steps, advance its index by 1, recurse, then undo.
  Comment at `:425-433` explains the algorithm. `[from-comment]`
  Produces every interleaving. Output gets huge fast (factorial
  growth) so tests rarely have more than 3-4 short sessions when
  using auto-generation.
- `run_named_permutations()` (`:485-496`): just iterates the
  explicitly-listed permutations.

### Running one permutation: `run_permutation()` (`:519-746`)

1. Print `starting permutation: <step names>` (`:529-532`).
2. Global setup via `conns[0]` (`:535-548`).
3. Per-session `setup` SQL on `conns[i+1]` (`:551-569`).
4. For each step in the permutation (`:572-697`):
   a. If the owning session is still busy on a prior step, wait for
      it: poll `try_complete_step` with `STEP_RETRY`, also poll all
      waiting steps with `STEP_NONBLOCK | STEP_RETRY` to unblock the
      target. Timeout at `2 * max_step_wait` → fatal exit
      (`:636-662`).
   b. `PQsendQuery(conn, step->sql)` (`:667-672`).
   c. Mark `iconn->active_step = pstep`.
   d. Snapshot `target_notices = current + num_notices` for any
      `PSB_NUM_NOTICES` blockers (`:678-685`).
   e. `try_complete_step(pstep, STEP_NONBLOCK)` (`:688`) — returns
      true if the step is now waiting (lock or blocker).
   f. Re-poll the existing waiting[] array (`:691-692`).
   g. If this step is waiting, append to waiting[] (`:695-696`).
5. After all steps issued, drain waiting[] with `STEP_RETRY`
   (`:700`). If anything still waiting, "failed to complete
   permutation due to mutually-blocking steps" → exit 1
   (`:701-705`).
6. Per-session teardown (`:708-726`); teardown failures are
   logged but **don't exit** (comment `:723`). `[from-comment]`
7. Global teardown (`:729-743`). Same swallow-failures policy.

### `try_complete_step()` (`:817-1076`) — the core poll loop

- For each `PSB_ONCE` blocker on first call, force `<waiting ...>`
  output and return true to guarantee deterministic output even when
  the step would otherwise complete instantly (`:837-852`).
  `[from-comment]`
- Inner `while (PQisBusy(conn))` loop:
  - `select(sock+1, &read_set, ...)` with 10 ms timeout (`:867`).
  - On select timeout: if `STEP_NONBLOCK` is set, run the prepared
    lock-wait probe. If the session is blocked on a lock and still
    `PQisBusy`, print `<waiting ...>` (once), return true
    (`:882-928`).
  - After `max_step_wait` of waiting, **send a cancel** via
    `PQcancelCreate` + `PQcancelBlocking` (`:947-964`) and set
    `canceled = true`. After `2 * max_step_wait`, exit 1
    (`:973-978`). Comment `:938-946` explains the rationale: keep
    one bad permutation from hanging the buildfarm forever.
    `[from-comment]`
  - On select() data: `PQconsumeInput`, continue the loop.
- After loop exits (query no longer busy):
  - Re-check blockers via `step_has_blocker()` (`:992-998`). If any
    unsatisfied blocker (e.g. waiting for N notices), keep the step
    marked as waiting and return true.
  - Otherwise print `step <name>: <sql>` (or `<...completed>` for
    retry, `:1001-1004`), drain all `PQgetResult`s (`:1006-1040`),
    print `PGRES_TUPLES_OK` via `printResultSet`, format error
    results showing only `PG_DIAG_SEVERITY` + `PG_DIAG_MESSAGE_PRIMARY`
    (so XIDs in detail strings don't leak into expected output,
    comment `:1018-1022`). `[from-comment]`
  - Drain any pending `PQnotifies` and print them with sender-session
    identification (`:1042-1070`).
  - Set `iconn->active_step = NULL`, return false (step completed).

### `try_complete_steps()` (`:754-802`) — collective drain

Iterates `try_complete_step` over the waiting[] array, compacting it
as steps complete. Keeps looping while there are blocker-conditioned
steps AND either someone completed or `any_new_notice` was raised
(`:792-800`) — this ensures NOTICE-driven blockers re-evaluate even
if no step completes. `[from-comment]`

### `step_has_blocker()` (`:1079-1110`)

Returns true if any of a step's blockers are still unsatisfied:
- `PSB_ONCE` — handled by `try_complete_step`, ignore here.
- `PSB_OTHER_STEP` — block if the referenced step is still
  `active_step` on its session.
- `PSB_NUM_NOTICES` — block if `total_notices < target_notices`.

### Notice processors

- `isotesterNoticeProcessor()` (`:1125-1135`): prefix message with
  session name, increment `total_notices`, set `any_new_notice = true`.
- `blackholeNoticeProcessor()` (`:1138-1142`): swallow messages on
  the control connection.

### Output helpers

- `printResultSet()` (`:1112-1122`): uses `PQprint` with header on,
  align on, field separator `|` — matches the regression expected
  format.

## Invariants & gotchas

- **One conninfo string shared by all sessions** — different
  databases per session aren't supported. If you need multi-DB
  isolation tests, isolationtester won't help.
- **Backend PIDs are required** for the lock-wait probe; the spec
  must declare at least one session (asserted by the prepared-query
  builder at `:223` — comment "assume that here"). `[from-comment]`
- The 10 ms `select` timeout is the **lock-detection granularity**
  — you can't observe sub-10ms races.
- `max_step_wait` doubles for cancel + die: after T seconds the
  driver cancels; after 2T it kills the test. The buildfarm-friendly
  rationale is at `:938-946`. `[from-comment]`
- `(*)` (PSB_ONCE) annotation forces a step to print `<waiting ...>`
  at least once — used when the step might or might not complete
  fast enough for the regular detection to observe it, to keep
  output stable. `[from-comment]`
- Error output is **deliberately minimal** (severity + primary
  message only) so the expected files don't churn on internal
  changes that bump XID values in error details. `[from-comment]`
- Auto-generated all-permutations explodes factorially —
  hand-written `permutation` lists are the norm.
- A "permutation cannot complete due to mutually-blocking steps"
  error means the spec has a real deadlock or under-specified
  blocker hints (`:701-705`).
- Teardown errors are **swallowed** (only logged), so a flaky
  teardown won't fail the test — but it might leave state for the
  next permutation. Comment `:722` and `:740`. `[from-comment]`
- The control connection (`conns[0]`) MUST NOT receive notices that
  pollute output, hence the blackhole processor (`:1138-1142`).
- All static state (`conns`, `nconns`, `any_new_notice`,
  `max_step_wait`) is process-global. `isolationtester` runs ONE
  spec per invocation and exits.

## Cross-refs

- `knowledge/files/src/test/isolation/isolationtester.h.md` — the
  AST consumed here.
- `knowledge/files/src/test/isolation/isolation_main.c.md` — the
  outer driver that spawns this binary per `.spec`.
- `knowledge/files/src/test/regress/pg_regress.c.md` — the shared
  schedule walker / TAP emitter.
- `src/test/isolation/specparse.y` — bison grammar producing the AST.
- `src/test/isolation/specscanner.l` — flex tokenizer.
- `src/backend/utils/adt/lockfuncs.c` —
  `pg_isolation_test_session_is_blocked()` lives here, the backend
  probe used by the prepared statement.
