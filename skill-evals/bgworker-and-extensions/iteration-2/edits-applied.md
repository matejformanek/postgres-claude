# Iteration 2 — edits applied

Applied edits from `iteration-1/proposed-edits.md` to
`.claude/worktrees/ft_meta_skill_creator_round_2/.claude/skills/bgworker-and-extensions/SKILL.md`.

## Verification of values against source/

Each cite verified by reading the main repo's `source/` symlink directly
before applying.

- **planner_hook signature** — 5 parameters confirmed at
  `source/src/include/optimizer/planner.h:28-32`. Trailing arg is
  `ExplainState *es`. The skill's previous 4-arg version was stale.
- **`dfmgr.c` _PG_init call site** — confirmed at
  `source/src/backend/utils/fmgr/dfmgr.c:295-299` (dlsym + invocation
  inside the magic-block / library-load block). No symmetric `_PG_fini`
  exists elsewhere in dfmgr.c (grep confirmed only `_PG_init`).
- **`die()` SIGTERM handler** — confirmed at
  `source/src/backend/tcop/postgres.c:3023-3058`. Sets ProcDiePending /
  InterruptPending / SetLatch; does NOT call proc_exit from handler.
- **`SignalHandlerForConfigReload`** — confirmed at
  `source/src/backend/postmaster/interrupt.c:60-65`. Two-line body:
  `ConfigReloadPending = true; SetLatch(MyLatch);`.
- **`bgw_extra` packing/unpacking** — confirmed at
  `source/src/test/modules/worker_spi/worker_spi.c:152-157` (unpack
  dboid + roleoid + flags in main) and `:470-475` (pack in launch).

All values used in the edits match source exactly.

## Edits applied

1. **Edit #1 (HIGH)** — Fixed `planner_hook` example in §8 to use the
   real 5-parameter `planner_hook_type` signature: added `ExplainState
   *es` to the callback prototype and to both recursive call sites
   (`prev_planner_hook(...)` and `standard_planner(...)`). Added a
   bridging sentence above the code block: "The planner_hook callback
   prototype matches `planner_hook_type` exactly — five parameters with
   `ExplainState *es` as the trailing argument" with
   `[verified-by-code source/src/include/optimizer/planner.h:28-32]`
   cite. This is the headline fix; closes the iter-1 with_skill miss.

2. **Edit #2 (LOW)** — Expanded the §8 opening paragraph to name all
   three preload buckets: `shared_preload_libraries`,
   `session_preload_libraries`, AND `local_preload_libraries`, with
   one-clause timing/scope distinction
   (postmaster-startup / per-backend-connect / per-backend-connect-
   by-unprivileged-user).

3. **Edit #3 (MED)** — Added new `### No _PG_fini: libraries never
   unload` subsection at the end of §8. Three bullets: (a) hook stays
   installed for life of backend, (b) DROP EXTENSION removes SQL
   bindings but does NOT undo _PG_init, (c) postmaster shutdown lets
   OS unmap. Cite: `[verified-by-code
   source/src/backend/utils/fmgr/dfmgr.c:295-299]`.

4. **Edit #4 (MED)** — Inserted "Why these signal handlers?" bullet at
   the TOP of §6 "Hard rules inside a worker". Names `die()` at
   `postgres.c:3023-3058` and `SignalHandlerForConfigReload` at
   `interrupt.c:60-65`, explains the flag-and-latch async-signal-safe
   pattern, and enumerates the three failure modes of a custom
   `proc_exit(0)` handler: (a) skip transaction abort, (b)
   signal-unsafe palloc/LWLock/ereport, (c) retire the slot forever
   regardless of `bgw_restart_time`.

5. **Edit #5 (LOW)** — Replaced the bare `bgw_extra` comment in the §2
   struct-fill example with the canonical pointer:
   `worker_spi.c:470-475` (pack: dboid + roleoid + flags) and
   `:152-157` (unpack in main).

## Edits NOT applied

None — all 5 proposed edits were applied. The two `[unverified]` markers
at the bottom of SKILL.md (BGWORKER_INTERRUPTIBLE recommendation,
bgw_notify_pid race) were intentionally left tagged rather than
guessed at.

## git diff --stat (worktree-relative)

```
.claude/skills/bgworker-and-extensions/SKILL.md | 59 +++++++++++++++++++++----
 1 file changed, 51 insertions(+), 8 deletions(-)
```

Confirms non-zero diff on SKILL.md.
