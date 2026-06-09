---
path: src/backend/storage/aio/aio_target.c
anchor_sha: 4b0bf0788b0
loc: 122
depth: deep
---

# aio_target.c

- **Source path:** `source/src/backend/storage/aio/aio_target.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 122

## Purpose

The **target abstraction**: a registry mapping each `PgAioTargetID` to
a `PgAioTargetInfo` vtable, plus the wrappers that assign a target to a
handle and dispatch to the target's `reopen` / `describe_identity`
callbacks. A "target" is *what the IO is performed on* — enough
information to reopen the file in another process (worker mode) and to
describe the IO in logs/views. Today the only real target is `smgr`.
[from-comment, aio_target.c:1-13, README "AIO Targets"]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `pgaio_io_has_target(ioh)` | `aio_target.c:39` | target != INVALID |
| `pgaio_io_get_target_name(ioh)` | `aio_target.c:49` | name string (allows INVALID, for debug) |
| `pgaio_io_set_target(ioh, targetid)` | `aio_target.c:63` | assign target (exactly once, before start) |
| `pgaio_io_get_target_data(ioh)` | `aio_target.c:72` | `&ioh->target_data` |
| `pgaio_io_get_target_description(ioh)` | `aio_target.c:83` | localized, palloc'd identity string |
| `pgaio_io_can_reopen(ioh)` | `aio_target.c:102` | does the target provide `reopen`? (internal) |
| `pgaio_io_reopen(ioh)` | `aio_target.c:115` | reopen the file in this process (internal) |

## Internal landmarks

- **`pgaio_target_info[]` (aio_target.c:25-30)** — designated-init
  registry. Slot `PGAIO_TID_INVALID` is an inline literal with just a
  `.name = "invalid"`; slot `PGAIO_TID_SMGR` points at
  `aio_smgr_target_info` (defined in `smgr.c`, outside `aio/`).

## Invariants & gotchas

- **Target is assigned exactly once, before `pgaio_io_start_*()`**
  (asserts HANDED_OUT + target == INVALID, aio_target.c:66-67). The
  target must be set before staging so the stage callbacks (which may
  bump buffer pins etc.) have valid identity.
- **`get_target_name` permits INVALID; `get_target_description` and
  `reopen` do not** (aio_target.c:53 vs 87,105,118) — the name is used
  in debug log prefixes for any handle including freshly-zeroed ones,
  but there's no description/reopen for a target-less IO.
- **`reopen` is mandatory for worker mode but optional in general** —
  `pgaio_io_can_reopen` gates it; `method_worker.c::pgaio_worker_needs_
  synchronous_execution` forces synchronous (in-issuer) execution when
  the target can't reopen, because a worker has no way to get a valid
  FD otherwise.
- **`describe_identity` allocates in the current memory context**
  (aio_target.c:81) — callers (`pg_get_aios`, error callbacks) must
  pfree or run in a short-lived context.

## Cross-refs

- Target vtable type `PgAioTargetInfo`: `aio.h`.
- The smgr target implementation: `smgr.c::aio_smgr_target_info`
  (`reopen` reopens via `smgropen`/`md.c`; identity is RelFileLocator +
  fork + block).
- Worker reopen caller: `method_worker.c::IoWorkerMain`.
- Description consumer: `aio_funcs.c::pg_get_aios`.

## Tally

`[verified-by-code]=4 [from-comment]=2 [inferred]=1`
