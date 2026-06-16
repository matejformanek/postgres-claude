---
path: src/backend/storage/aio/aio_funcs.c
anchor_sha: 4b0bf0788b0
loc: 230
depth: deep
---

# aio_funcs.c

- **Source path:** `source/src/backend/storage/aio/aio_funcs.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 230

## Purpose

The **SQL interface** to AIO: a single SRF, `pg_get_aios()`, backing
the `pg_aios` system view. Iterates the entire global handle array and
emits one row per non-idle IO handle with owner PID, state, op, offset,
length, target description, and the three flag columns — **without
taking any lock**, using a generation/state recheck protocol instead.
[from-comment, aio_funcs.c:1-14]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `pg_get_aios(PG_FUNCTION_ARGS)` | `aio_funcs.c:47` | materialized SRF, 15 columns (`PG_GET_AIOS_COLS`) |

## Internal landmarks

- **`iov_byte_length` (aio_funcs.c:34)** — sums an iovec's
  `iov_len`s to report the IO byte size.
- **The lock-free snapshot protocol (aio_funcs.c:71-145)** is the
  interesting part:
  1. read `generation`;
  2. `retry:` read `state` (skip if IDLE);
  3. `memcpy` the whole `PgAioHandle` and its iovecs into local copies;
  4. `pg_read_barrier()`, then recheck: if `generation` changed, the IO
     completed and a new one started — **skip it** (it started after we
     were called); if only `state` changed, `goto retry` (states only
     advance, bounded, so no livelock).
  After the snapshot, the "live" pointers are nulled to catch
  accidental post-snapshot access (aio_funcs.c:144-145).

## Invariants & gotchas

- **No lock is taken on purpose** — the comment (aio_funcs.c:72-82)
  states they don't want to introduce atomics into the very hot IO
  path just to support a monitoring view. The cost is that `pg_aios`
  shows a best-effort, possibly-already-stale snapshot.
- **Generation change ⇒ drop the row; state change ⇒ retry.** These are
  asymmetric on purpose: a generation bump means the row you were
  rendering is a *different* IO now (don't show it); a state bump is the
  *same* IO advancing (re-render it). Livelock is impossible because
  states are finite and monotonic (aio_funcs.c:120-136).
- **HANDED_OUT rows show only id/generation/state** — all later columns
  are nulled because the op/target/data aren't valid yet
  (aio_funcs.c:163-172).
- **Raw `result` column is only non-null in COMPLETED_* states**
  (aio_funcs.c:203-208).
- **Reads owner PID via `GetPGProcByNumber(owner)->pid` from the
  snapshot's `owner_procno`** (aio_funcs.c:113-115) — captured before
  the final recheck so an exited owner is detected by the generation
  check.

## Cross-refs

- Handle struct fields read here: `knowledge/files/src/include/storage/aio_internal.h.md`.
- State/op/status name helpers: `aio.c::pgaio_io_get_state_name`,
  `aio_io.c::pgaio_io_get_op_name`, `aio.c::pgaio_result_status_string`.
- Target description: `aio_target.c::pgaio_io_get_target_description`.
- View definition: `src/backend/catalog/system_views.sql` (`pg_aios`).

<!-- issues:auto:begin -->
- [Issue register — `storage-aio`](../../../../../issues/storage-aio.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-info-disclosure: `pg_aios` exposes other backends' IO
  targets + offsets cluster-wide]** `aio_funcs.c:197,211,218` — the
  view surfaces RelFileLocator-derived target descriptions and file
  offsets for IOs owned by *any* backend. The protecting role-ACL is on
  the view, not enforced here; consistent with `pg_stat_activity`-class
  exposure but worth noting for the data-leak threat model: which role
  can `SELECT pg_aios` determines who sees cross-backend IO metadata.
  Severity: maybe.

## Tally

`[verified-by-code]=5 [from-comment]=3 [inferred]=0`
