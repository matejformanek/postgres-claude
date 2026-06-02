# Registering a new built-in LWLock 'FooBarLock'

## Files to edit

### 1. `source/src/include/storage/lwlocklist.h`

Add a `PG_LWLOCK(<id>, FooBar)` entry **at the end** of the predefined-LWLock list. The current last entry is `PG_LWLOCK(57, AioWorkerControl)` (`lwlocklist.h:91`). So:

```c
PG_LWLOCK(58, FooBar)
```

Notes from the header comment (`lwlocklist.h:22-32`):
- **Add at the end** to avoid renumbering existing locks (DTrace and external debuggers key on these IDs).
- **Names omit the "Lock" suffix** here — the suffix is added by the codegen. You'll reference the lock in C as `FooBarLock`.

This file is processed by `generate-lwlocknames.pl` to produce `lwlocknames.h`, which defines the `FooBarLock` macro pointing into `MainLWLockArray`.

### 2. `source/src/backend/utils/activity/wait_event_names.txt`

Add a line in the **`WaitEventLWLock`** section with the name exactly matching (without "Lock"):

```
FooBar	"Waiting for FooBar."
```

The skill (§2.2) calls this out explicitly: "add a `PG_LWLOCK(id, name)` entry in `src/include/storage/lwlocklist.h`, then add the same name to `src/backend/utils/activity/wait_event_names.txt`." If you skip this file, `pg_stat_activity.wait_event` shows the wrong / synthesized name. The header comment in `lwlocklist.h:27-28` reinforces it: "do not forget to update the section WaitEventLWLock of src/backend/utils/activity/wait_event_names.txt."

### 3. (Often) `source/src/backend/storage/lmgr/lwlock.c`

If your lock guards a brand-new shared-memory area you allocate via `ShmemInitStruct`, you generally don't need to touch `lwlock.c` itself — `MainLWLockArray` is sized by counting `PG_LWLOCK` entries in `lwlocklist.h` at build time, and `CreateLWLocks` (in `lwlock.c`) initializes them all. The macro `FooBarLock` is then usable directly:

```c
LWLockAcquire(FooBarLock, LW_EXCLUSIVE);
```

### 4. README in the relevant subsystem

Skill §4: "README update if your subsystem has one (e.g. `src/backend/storage/buffer/README`) — add the new lock to its list of primitives." So if `FooBar` lives in, say, `src/backend/access/foobar/`, add an entry to that README explaining what the lock protects.

### 5. Struct header comment

Skill §4 again: "Header comment on the struct stating exactly which lock protects which field. Cross-reference the lock by name."

## Built-in `PG_LWLOCK` vs `RequestNamedLWLockTranche` — when to use which

| | `PG_LWLOCK` in lwlocklist.h | `RequestNamedLWLockTranche()` |
|---|---|---|
| Who can use it | Core code only (you're editing the header) | **Extensions** — called from `_PG_init` while preloaded |
| Lock count | Single lock per entry | Array of N locks, N picked at startup |
| Storage | Slot in `MainLWLockArray` | Separate tranche allocated in shmem |
| ID assignment | Fixed integer you choose | Dynamic tranche id assigned at startup |
| wait_event_names.txt | **Must update manually** | Tranche name is registered at runtime — no .txt edit needed |
| Lifecycle | Created at postmaster startup, lives forever | Same |

**Choose `PG_LWLOCK` when**: you're patching core, you want a single named lock referenced by symbol (`FooBarLock`), and the count is fixed at 1.

**Choose `RequestNamedLWLockTranche` when**: you're writing an extension (you can't edit `lwlocklist.h`), or you want an array of locks (e.g. partitioned), or the number of locks depends on a GUC.

For DSM-resident locks (allocated inside a dynamic shared memory segment, not in the static shmem area), you'd instead use `LWLockNewTrancheId()` + `LWLockInitialize()` + each attaching backend calls `LWLockRegisterTranche()`. That's a third pattern, documented in `source/src/include/storage/lwlock.h` around the `LWLockNewTrancheId` declaration.

## Things to also do

- Skill §2.2: cap simultaneous holdings under `MAX_SIMUL_LWLOCKS = 200`. A single new lock doesn't move you near that, but if your code holds it alongside many partition locks, be aware.
- Skill §2.2: don't hold across long waits — `README:43-45` says "It is therefore not a good idea to use LW locks when the wait time might exceed a few seconds."
- If `FooBarLock` will be acquired alongside other LWLocks, document the global order in the function's header comment (§4) — even though there are no partitioned-tranche order requirements for an individually-named lock, you still need a consistent order across all paths to avoid silent deadlock.

## Citations

- `source/src/include/storage/lwlocklist.h:22-32` — the rules for adding entries.
- `source/src/include/storage/lwlocklist.h:34-91` — the existing PG_LWLOCK list (last entry id 57).
- `source/src/backend/utils/activity/wait_event_names.txt` — `WaitEventLWLock` section.
- `source/src/include/storage/lwlock.h:135-139` — `RequestNamedLWLockTranche` declaration and lifecycle note.
- `source/src/backend/storage/lmgr/lwlock.c` — `CreateLWLocks`, `LWLockRegisterTranche`.
- `source/src/backend/storage/lmgr/README:43-45` — hold-time guidance.
