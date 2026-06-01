# `storage/ipc/sinval.c`

- **Source:** `source/src/backend/storage/ipc/sinval.c` (202 lines)
- **Header:** `source/src/include/storage/sinval.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Thin façade over `sinvaladt.c`. Provides the **send / receive / catchup**
API for shared-cache invalidation messages — the mechanism that tells
every backend "your relcache/syscache entry for X is stale, drop it".

The actual queue is in `sinvaladt.c`; this file handles:
- `SendSharedInvalidMessages` → forwards to `SIInsertDataEntries`.
- `ReceiveSharedInvalidMessages` → pulls + dispatches.
- The `PROCSIG_CATCHUP_INTERRUPT` glue (signal-handler-safe flag set,
  late processing on next interrupt check).

## Why catchup interrupts exist

> "Because backends sitting idle will not be reading sinval events, we
> need a way to give an idle backend a swift kick in the rear and make
> it catch up before the sinval queue overflows and forces it to go
> through a cache reset exercise." `[from-comment] :27-32`.

The sinval queue is finite (`MAXNUMMESSAGES = 4096` in
`sinvaladt.c:130`). An idle backend that never calls
`AcceptInvalidationMessages` will eventually be marked "reset" — when
it finally reads, it has to throw away its whole catalog cache. To
avoid that, `SICleanupQueue` sends `PROCSIG_CATCHUP_INTERRUPT` to the
furthest-behind unsignaled backend.

## ReceiveSharedInvalidMessages — recursion safety

The strange-looking static `messages`/`nextmsg`/`nummsgs` are
**static** so a recursive call (inside `invalFunction`) can resume the
outer loop's batch without losing already-fetched messages.
`[from-comment] :60-66`. The `volatile` keyword on `nextmsg/nummsgs`
guards against the compiler not realizing recursion is possible.

Loop structure:
1. Drain any leftover messages from an outer recursion's buffer.
2. `SIGetDataEntries(messages, 32)` — pull up to 32 messages.
3. If returns `-1` → "reset" message, call `resetFunction` and stop.
4. Process the batch through `invalFunction` (which may recurse).
5. Loop while the last fetch returned a full buffer (still more in queue).
6. **Daisy-chain the catchup signal**: if our own
   `catchupInterruptPending` was set, clear it and call
   `SICleanupQueue(false, 0)` so the *next* furthest-behind backend
   gets the signal. `[from-comment] :126-133`. This avoids a thundering
   herd when many idle backends fall behind.

## HandleCatchupInterrupt / ProcessCatchupInterrupt

Signal-handler-safe: `HandleCatchupInterrupt` just sets the volatile
flag. The latch is set by `procsignal_sigusr1_handler` (in
`procsignal.c`) so a `WaitLatch` wakes up.

`ProcessCatchupInterrupt` runs later — outside signal context — and
calls `AcceptInvalidationMessages` either directly (if inside a xact)
or by starting+committing an empty xact (so xact start can call
`AcceptInvalidationMessages` itself). `[from-comment] :184-189` —
note "I am not sure that things would clean up nicely if we got an
error partway through" → that's why they use the xact-wrapper path
when not already in one.

## `SharedInvalidMessageCounter`

Process-local counter bumped per message processed. Used by
`InvalidateSystemCachesExtended` to detect that catalog cache state
might have changed during a given window. `[verified-by-code]`.

## Cross-references

- `sinvaladt.c` — the queue impl.
- `utils/cache/inval.c` — `AcceptInvalidationMessages`,
  `LocalExecuteInvalidationMessage`, the per-message dispatch.
- `procsignal.c` — `PROCSIG_CATCHUP_INTERRUPT` plumbing.
- `tcop/postgres.c::ProcessClientReadInterrupt` — calls
  `ProcessCatchupInterrupt` when idle.

## Open questions

The recursion comment is convincing but I did not chase a specific
recursive call site (e.g. a `RelationCacheInvalidateEntry` that itself
triggers more invalidations). The static buffer makes the recursion
safe by construction. `[unverified]` whether unbounded recursion
depth is theoretically possible.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
