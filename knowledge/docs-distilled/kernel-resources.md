---
source_url: https://www.postgresql.org/docs/current/kernel-resources.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§19.4 Managing Kernel Resources"
maps_to_skills: [build-and-run, debugging, bgworker-and-extensions]
maps_to_corpus: [knowledge/subsystems/storage-buffer.md, knowledge/docs-distilled/runtime-config-resource.md, knowledge/docs-distilled/server-shutdown.md]
---

# Managing kernel resources — shmem, semaphores, huge pages, OOM (§19.4)

The postmaster-startup resource surface: how PG maps shared memory, how many
semaphores it needs, and the Linux OOM-killer / IPC-cleanup traps a backend
hacker hits when the cluster won't start.

## Non-obvious claims

- **Shared memory is a hybrid by default.** PG allocates "a very small amount of
  System V shared memory" (a tiny SysV segment used only as an nattach guard
  against stale-segment collisions) plus a "much larger amount of anonymous
  `mmap` shared memory" for `shared_buffers`. `shared_memory_type` can force a
  single large SysV region instead. `[from-docs]` This is why modern PG rarely
  needs the huge `SHMMAX` tuning old docs demanded.
- **Semaphores are counted, not guessed.** `num_os_semaphores` ≈
  `max_connections + autovacuum_worker_slots + max_wal_senders +
  max_worker_processes + overhead`, allocated by the kernel in **sets of 16 with
  a 17th sentinel** (hence SEMMSL ≥ 17, SEMMNI ≥ ceil(n/16)). Read the exact
  number *before* starting with `postgres -D $PGDATA -C num_os_semaphores`.
  `[from-docs]` POSIX semaphores (Linux, FreeBSD) sidestep the SysV `SEMMNS`
  limits; other platforms use SysV.
- **Huge pages cut TLB misses on large `shared_buffers`.** `huge_pages=try`
  (default) / `on` (fail-to-start if unavailable) / `off`; size via
  `huge_page_size`. Pre-compute the need with
  `postgres -D $PGDATA -C shared_memory_size_in_huge_pages` and pre-allocate via
  `vm.nr_hugepages`. `[from-docs]`
- **The OOM killer killing the postmaster is catastrophic** (it takes down every
  connection). Two mitigations: disable overcommit (`vm.overcommit_memory=2`),
  and protect the supervisor via the startup-script env vars
  **`PG_OOM_ADJUST_FILE=/proc/self/oom_score_adj`** + **`PG_OOM_ADJUST_VALUE`**
  so the postmaster gets a protective score while *child* backends stay killable
  (a runaway backend should die, not the whole cluster). `[from-docs]`
- **systemd `RemoveIPC=on` silently corrupts parallel query.** If the OS `postgres`
  user isn't a *system* user (UID < `SYS_UID_MAX`), logind removes its SysV/POSIX
  IPC objects on logout, breaking DSM segments. Fix: create it with `useradd -r`
  / `adduser --system`, or set `RemoveIPC=no`. `[from-docs]` A genuinely
  non-obvious cause of intermittent parallel-worker failures.
- **File-descriptor + socket-queue limits:** `max_files_per_process` caps
  per-backend fds to avoid system-wide exhaustion; raise `fs.file-max` and
  `net.core.somaxconn` (default 128) on high-concurrency dedicated servers.
  `[from-docs]`

## Links into corpus

- [[knowledge/subsystems/storage-buffer.md]] — `shared_buffers` is the mmap
  region this page sizes.
- [[knowledge/docs-distilled/runtime-config-resource.md]] —
  `shared_memory_type` / `dynamic_shared_memory_type` / `huge_pages` GUC detail.
- [[knowledge/docs-distilled/server-shutdown.md]] — the IPC-cleanup contract a
  SIGKILL'd postmaster breaks (why stale semaphores block the next start).
</content>
