# pmchild.c

- **Source:** `source/src/backend/postmaster/pmchild.c` (302 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top comment + main API)
- **Note:** included although not in the explicit task list — it is the slot-
  allocator the postmaster uses for every fork and is referenced from
  `BackendStartup`.

## Purpose

Tracks postmaster child processes via a fixed pool of `PMChild` structs,
one pool per `BackendType`. Pools are sized from
`autovacuum_worker_slots + max_worker_processes + max_wal_senders +
max_connections` (and aux singletons). [from-comment] `:1-13`

## Why per-type pools

So that a flood of regular backends cannot starve autovac/aux of slots.
[from-comment] `:42-45`

## Dead-end backends

Different rules: unlimited count, dynamically allocated (not from the pool),
no unique IDs needed. [from-comment] `:14-17`

## Globals

- `pmchild_pools[BACKEND_NUM_TYPES]` — per-type freelist of `PMChild`. `:54`
- `num_pmchild_slots` — total pool size. `:55`
- `ActiveChildList` — `dlist` of all live children including dead-ends. `:60`

## Public API (called from `postmaster.c`)

- `AssignPostmasterChildSlot(BackendType)` — pop a free slot of the type.
- `AllocDeadEndChild()` — dynamic alloc for dead-end backends.
- `ReleasePostmasterChildSlot(PMChild *)` — return to pool.
- `InitPostmasterChildSlots()` — startup-time pool init.
- Iteration helpers used by `CountChildren` / `SignalChildren`.

## Shared-memory mirror

The actual PID and ACTIVE/ASSIGNED/etc. state lives in a shmem array
managed by `pmsignal.c` — `pmchild.c` is the postmaster-private view.
[from-comment] `:18-21`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
