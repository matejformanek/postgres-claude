---
path: src/backend/storage/aio/aio_callback.c
anchor_sha: 4b0bf0788b0
loc: 333
depth: deep
---

# aio_callback.c

- **Source path:** `source/src/backend/storage/aio/aio_callback.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 333

## Purpose

The callback machinery for IO handles: the static **ID→callbacks
table** (`aio_handle_cbs[]`), registration (`pgaio_io_register_callbacks`),
the per-handle data array (`pgaio_io_set_handle_data_*`), result
reporting (`pgaio_result_report`), and the internal "call all
registered callbacks" drivers for the **stage / complete_shared /
complete_local** phases. This is where the README's "multiple layers
react to one IO" design is realized. [from-comment, aio_callback.c:1-13]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `pgaio_io_register_callbacks(ioh, cb_id, cb_data)` | `aio_callback.c:85` | append a callback ID + 1 byte of data |
| `pgaio_io_set_handle_data_64(ioh, data, len)` | `aio_callback.c:121` | attach a `uint64[]` (e.g. Buffer IDs) |
| `pgaio_io_set_handle_data_32(ioh, data, len)` | `aio_callback.c:139` | `uint32[]` convenience (widens to 64) |
| `pgaio_io_get_handle_data(ioh, *len)` | `aio_callback.c:155` | retrieve the attached array |
| `pgaio_result_report(result, target_data, elevel)` | `aio_callback.c:172` | dispatch to the callback's `report` |
| `pgaio_io_call_stage(ioh)` | `aio_callback.c:198` | run all `stage` callbacks (internal) |
| `pgaio_io_call_complete_shared(ioh)` | `aio_callback.c:224` | run all `complete_shared`, distill result (internal) |
| `pgaio_io_call_complete_local(ioh)` | `aio_callback.c:284` | run all `complete_local`, return distilled result (internal) |

## Internal landmarks

- **`aio_handle_cbs[]` (aio_callback.c:39-49)** — the static table
  mapping each `PgAioHandleCallbackID` to a `{const PgAioHandleCallbacks
  *cb, const char *name}`. Populated via the `CALLBACK_ENTRY` macro.
  The three real entries point at `aio_md_readv_cb`,
  `aio_shared_buffer_readv_cb`, `aio_local_buffer_readv_cb` (defined in
  `md.c` / `bufmgr.c`). The 0 slot is `aio_invalid_cb = {0}`.
- **Callbacks run innermost-first.** All three drivers iterate
  `for (i = num_callbacks; i > 0; i--)` (aio_callback.c:204,243,298),
  i.e. the *last* registered callback runs first — so bufmgr (high
  layer, registered last) sees md.c's (low layer) result first and can
  build on it.

## Invariants & gotchas

- **`complete_shared` always starts from `PGAIO_RS_OK`** with
  `result = ioh->result` (the raw syscall return), because "low level
  IO is always considered OK" (aio_callback.c:234) — it's the
  callbacks' job to reinterpret a short read or `-errno` as
  PARTIAL/ERROR. Each callback receives the prior callback's result and
  returns a possibly-modified one; the final value is stashed in
  `ioh->distilled_result`.
- **Both completion drivers run inside `START_CRIT_SECTION()`**
  (aio_callback.c:229, 289) — completion must be no-throw, see
  `aio.c::pgaio_io_process_completion`.
- **A callback must never transition the result to UNKNOWN** — asserted
  after every call (aio_callback.c:261, 315).
- **`complete_local`'s result is *not* saved to `distilled_result`**
  (aio_callback.c:318-323) — it's returned to the issuer (→
  `report_return->result`) but must not affect other waiters, who only
  ever see the shared result.
- **Handle-data can be set only once per IO** (asserted
  `handle_data_len == 0`, aio_callback.c:125,143), even though up to 4
  callbacks can be registered — the comment (aio_callback.c:114-120)
  justifies this as a shared-memory frugality choice; no current caller
  needs per-callback data.
- **`set_handle_data_*` length is bounded by `PG_IOV_MAX` and
  `io_max_combine_limit`** (aio_callback.c:126-127) — it reuses the
  handle's iovec slot region in `PgAioCtl->handle_data`.
- **`register_callbacks` PANICs past `PGAIO_HANDLE_MAX_CALLBACKS` (4)**
  (aio_callback.c:97-99) and rejects callback IDs whose entry has no
  completion callback at all (aio_callback.c:94-96).
- **`pgaio_result_report` asserts the status is neither UNKNOWN nor OK**
  (aio_callback.c:178-179) — you only report failures/warnings, and the
  selected callback must have a non-NULL `report` (aio_callback.c:181).

## Cross-refs

- Vtable + callback typedefs: `knowledge/files/src/include/storage/aio.h.md`.
- Result struct: `knowledge/files/src/include/storage/aio_types.h.md`.
- Completion driver caller: `aio.c::pgaio_io_process_completion`,
  `aio.c::pgaio_io_reclaim`.
- The actual callbacks: `bufmgr.c` (shared/local buffer readv), `md.c`
  (md readv) — both outside `aio/`.

## Potential issues

- **[ISSUE-undocumented-invariant: completion-callback set must be
  identical between issuing and completing backend]** The callback IDs
  travel in the shared handle, but the ID→pointer table
  (`aio_handle_cbs[]`) is process-local static. Correctness relies on
  every backend compiling the same table in the same order; an
  out-of-tree patch that conditionally adds a callback ID in some
  builds but not others would mis-dispatch in mixed EXEC_BACKEND
  scenarios. Enforced only by "everyone builds the same binary."
  Severity: nit.

## Tally

`[verified-by-code]=8 [from-comment]=2 [inferred]=0`
