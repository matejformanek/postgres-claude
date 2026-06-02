# Counter for autovacuum-skip events — which primitive?

## Triage

The counter is shared-memory state (read by every backend on the hot path, scraped by stats once a minute). The whole update is a single 64-bit increment: one location, one operation. This is the textbook fit for **atomics** — specifically `pg_atomic_fetch_add_u64`.

The skill's decision tree (`.claude/skills/locking/SKILL.md` §1) explicitly routes "a single word (counter, flag, packed state) on the hot path, where the whole update fits in one CAS / fetch-and-add" to `pg_atomic_*`. The locking-overview reinforces this in §4: "Counter, flag, or single packed word, very hot, accessed by many backends → `pg_atomic_*`".

## Why not the other primitives

- **Heavyweight lock**: wrong layer. Heavyweight locks protect user-visible objects (relations, tuples, xids, advisory keys) via the partitioned hash in `source/src/backend/storage/lmgr/lock.c`. A skip counter is not a user-visible object.
- **LWLock**: would work and would be safe across `ereport`, but a full LWLock acquisition is one CAS uncontended *plus* the proclist/semaphore machinery on contention (`source/src/backend/storage/lmgr/lwlock.c:38-75`). For a single counter increment this is pure overhead — every increment pays for a primitive designed to protect 200+-byte structs.
- **Spinlock**: would also work for the writer but every reader (stats collector) would have to take the same spinlock to read consistently on 32-bit platforms. More importantly, a spinlock is harder to reason about than `pg_atomic_fetch_add_u64`: the spinlock forbids subroutine calls / kernel calls / `CHECK_FOR_INTERRUPTS` / `ereport ≥ ERROR` inside the section (`source/src/backend/storage/lmgr/README:8-11`, `source/src/include/storage/spin.h:26-29`), and you have to remember it's not released on error. For one increment, those constraints buy nothing.

## The right call

`pg_atomic_uint64 av_skip_count;` initialized at shmem setup, incremented with `pg_atomic_fetch_add_u64(&x->av_skip_count, 1)`, read with `pg_atomic_read_u64(&x->av_skip_count)`. API in `source/src/include/port/atomics.h:10-30`.

### Gotchas to be aware of (verify on your target platforms)

- `u64` atomics fall back to spinlock-backed emulation on platforms lacking 8-byte atomicity (`source/src/include/port/atomics.h:107-112`). On modern x86_64 / aarch64 this is a real lock-free op; on a 32-bit ARM box it isn't. If you only need 32 bits of range, use `pg_atomic_uint32` to get true lock-free everywhere.
- The header itself says "Use higher level functionality (lwlocks, spinlocks, heavyweight locks) whenever possible. Writing correct code using these facilities is hard." (`source/src/include/port/atomics.h:25-26`). For a single bare counter the simplicity argument flips — there's no invariant beyond "monotonically increasing" to get wrong.

## What to document on the struct

The skill checklist (`.claude/skills/locking/SKILL.md` §4) is explicit:

1. **Header comment on the struct** stating what `av_skip_count` means and that it's a monotonically-increasing counter incremented by any backend with `pg_atomic_fetch_add_u64`. Note that "may briefly read a stale value" is the visibility contract.
2. **No "protected by" line is needed** because no lock protects it — but the comment should *say that explicitly* ("synchronized by atomic ops; no lock needed"). Otherwise a future reader will assume you forgot. The gold-standard example is `BufferDesc.state`'s header comment block in `source/src/include/storage/buf_internals.h` (the overview cites lines 33-86), which lays out exactly which bits are packed into the atomic word.
3. **Barriers**: if there's no second piece of shared state that has to become visible *in order* relative to this counter, you need no explicit barrier. `pg_atomic_fetch_add_u64` includes full fence semantics on the value itself. If there were ordering (e.g. write a reason-string buffer *then* publish the counter), you'd add `pg_write_barrier()` between them and read with `pg_read_barrier()` on the consumer; see `source/src/backend/storage/lmgr/README.barrier`.

## Ordering rules

For *this* counter, none — there's only one location. The ordering rules listed in the skill §3 are about multi-lock acquisitions and don't apply.

If at a later point you add a second related field (e.g. last-skip-timestamp) and they must be read consistently together, the cheap answer is to pack both into a single 64-bit word and CAS-update (the `BufferDesc.state` pattern). The expensive but simpler answer is to upgrade to an LWLock for both fields. Do *not* mix atomics with a spinlock to "make them consistent" — that combination is harder to reason about than either alone.

## Wait-event / lwlocklist updates

None required. Atomics have no tranche and no wait event. If you'd reached for a new named LWLock you'd be editing `source/src/include/storage/lwlocklist.h` and `source/src/backend/utils/activity/wait_event_names.txt` (skill §2.2; overview §1.3 "LWLock tranches and named locks"), but atomics need neither.

## Summary

`pg_atomic_uint64`, `fetch_add` to increment, `read` to scrape, document on the struct that no lock protects it (synchronized by atomic ops), no ordering rules, no wait-event entry. Five lines of code, one comment.
