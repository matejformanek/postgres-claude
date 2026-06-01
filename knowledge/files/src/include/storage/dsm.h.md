# `storage/dsm.h`

- **Source:** `source/src/include/storage/dsm.h` (58 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Public API for managed DSM segments. See `dsm.c.md`.

- **`DSM_CREATE_NULL_IF_MAXSEGMENTS`** — pass to `dsm_create` to
  return NULL instead of erroring on capacity exhaustion.
- **Pin variants**:
  - `dsm_pin_mapping(seg)` — our mapping survives the current
    `ResourceOwner`'s release (session lifespan).
  - `dsm_unpin_mapping(seg)` — undo the above.
  - `dsm_pin_segment(seg)` — segment refcount stays above zero even
    after every backend detaches. Means the segment lives until
    explicit `dsm_unpin_segment(handle)` or postmaster shutdown.
- **`on_dsm_detach` callbacks** — per-segment cleanup hooks; LIFO
  invocation; entries removed before invocation to be reentry-safe.
- **`reset_on_dsm_detach()`** — called from `on_exit_reset` after
  fork; drops all detach callbacks (child must not run parent's).

## EXEC_BACKEND only

`dsm_set_control_handle(h)` — child processes in EXEC_BACKEND mode
receive the parent's control-segment handle via the startup data and
must call this before using DSM.
