---
source_url: https://www.postgresql.org/docs/current/server-start.html
fetched_at: 2026-07-08
anchor_sha: 4c75cc786301
chapter: "§19.3 Starting the Database Server (+ §19.3.1 failure / §19.3.2 client-connection problems)"
maps_to_skills: [build-and-run, debugging, process-lifecycle]
maps_to_corpus: [knowledge/subsystems/main.md, knowledge/docs-distilled/kernel-resources.md, knowledge/docs-distilled/connect-estab.md, knowledge/docs-distilled/runtime-config-connection.md]
---

# Starting the database server — postmaster bring-up + failure taxonomy (§19.3)

The postmaster (`postgres`) startup path and the exact error strings that map to
kernel/config causes. The interlock file and the bind/IPC failures below all
originate in backend C, cited at the anchor SHA.

## Non-obvious claims

- **The single-instance interlock is `postmaster.pid` in `$PGDATA`.**
  `DIRECTORY_LOCK_FILE "postmaster.pid"` (`miscinit.c:61`) is written by
  `CreateDataDirLockFile` (`miscinit.c:1465`) `[verified-by-code]`. It holds the
  postmaster PID + a shmem key so a second `postgres` on the same dir refuses to
  start. It is written in *multiple steps* (`miscinit.c:1333` note
  `[verified-by-code]`), so a torn/partial file is a known transient state, not
  necessarily corruption. `[from-docs]`
- **`postgres` must NOT run as root** and needs `-D $PGDATA` (or the `PGDATA`
  env var); run in foreground for debugging, or via `pg_ctl start -l logfile`
  which backgrounds + redirects. `[from-docs]`
- **"could not bind ... Address already in use" = port clash, not a PG bug.**
  The string is `errmsg("could not bind %s address \"%s\": %m")`
  (`pqcomm.c:617`) `[verified-by-code]`, followed by a HINT to check for another
  postmaster on the port and a `FATAL: could not create any TCP/IP sockets`.
  `Permission denied` on the same bind = a privileged/reserved port. `[from-docs]`
- **`shmget` / `semget` failures are *kernel-limit* messages, not disk.**
  `FATAL: could not create shared memory segment ... shmget(...)` means SysV
  `SHMMAX` too small (only when `shared_memory_type = sysv`, since modern PG uses
  anonymous `mmap` — see `kernel-resources.md`); `FATAL: could not create
  semaphores: No space left on device ... semget(...)` is the SysV semaphore
  limit `SEMMNS`, *despite* the misleading "No space left on device" wording.
  `[from-docs]`
- **Client "Connection refused" vs "No such file or directory" split the
  diagnosis cleanly.** TCP `Connection refused` → server not running, or
  `listen_addresses` doesn't include the client's route (default `localhost`
  only). Unix-socket `... /tmp/.s.PGSQL.5432 ... No such file or directory` →
  the client's socket-dir guess disagrees with the server's
  `unix_socket_directories`. `[from-docs]`
- **Listen surface is three GUCs:** `listen_addresses` (TCP interfaces),
  `port` (default 5432), `unix_socket_directories` (local socket path). All are
  read from `postgresql.conf` at startup. `[from-docs]`

## Links into corpus

- [[knowledge/subsystems/main.md]] — process-startup dispatch; the postmaster
  main loop this page's failures abort out of.
- [[knowledge/docs-distilled/kernel-resources.md]] — the SysV/POSIX
  shmem+semaphore sizing behind the `shmget`/`semget` failures.
- [[knowledge/docs-distilled/connect-estab.md]] — what happens *after* a
  successful bind: accept → fork → backend.
- [[knowledge/docs-distilled/runtime-config-connection.md]] —
  `listen_addresses` / `port` / `unix_socket_directories` GUC detail.
