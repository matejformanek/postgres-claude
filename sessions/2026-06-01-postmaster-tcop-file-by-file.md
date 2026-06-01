# Session — postmaster + tcop file-by-file

- **Date:** 2026-06-01
- **Commit:** `ef6a95c7c64`
- **Scope:** Per-file docs for every `.c` in `src/backend/postmaster/`
  (plus `storage/ipc/pmsignal.c` because the task brief listed `pmsignal.c`)
  and every `.c` in `src/backend/tcop/`, with corresponding headers in
  `src/include/{postmaster,tcop}/`.

## What was produced

41 per-file docs under `knowledge/files/src/...`:

- 16 postmaster `.c` (incl. pmchild.c, pmsignal.c) — `postmaster.c` and
  `launch_backend.c` deep-read, most others read.
- 7 tcop `.c` — `postgres.c` deep-read, rest read.
- 17 headers — proctypelist.h, interrupt.h, auxprocess.h, dest.h, cmdtag.h,
  tcopprot.h read; others skim.

## What was flagged

1. The brief asked for separate `archiver.c` and `pgarch.c`. Only `pgarch.c`
   exists in the current tree — it is the archiver. Noted in
   `pgarch.c.md`.
2. `pmsignal.c` lives under `src/backend/storage/ipc/`, not `postmaster/`.
   Documented at the real path.
3. `pmchild.c` was not in the explicit list but is the slot allocator the
   postmaster uses on every accept; documented anyway because both
   `postmaster.c.md` and `pmsignal.c.md` reference it.
4. `checkpointer.h` may not exist as a separate header in this tree;
   prototypes live in `bgwriter.h` and `xlog.h`. Noted in the .h doc.

## Conventions applied

- Standard per-file template: source path, last-verified commit, depth,
  purpose paragraph, key entry points table, control flow / invariants,
  interactions, headers. Citation tags `[from-comment]`, `[verified-by-code]`,
  `[from-code]`, `[inferred]` as in the subsystem-documenter contract.
- Mirrored paths under `knowledge/files/src/...`.
- `progress/files-examined.md` got 41 new rows.

## Load-bearing facts surfaced

- `postmaster.c:14-23` — postmaster deliberately stays out of shared memory.
  Cited in postmaster.c.md, pmsignal.c.md, bgworker.c.md.
- `proctypelist.h` is the canonical X-macro table of `BackendType` →
  `main_fn` + `shmem_attach`. Documented in full.
- `B_LOGGER` is the only aux with `shmem_attach=false`
  (`proctypelist.h:46`). Cited in syslogger.c.md and proctypelist.h.md.
- `BackendInitialize`'s "no shmem touched yet" requirement
  (`backend_startup.c:128-139`) — load-bearing for SIGTERM-during-startup
  handling. Cited in backend_startup.c.md.
- `PostgresMain`'s sigsetjmp landing pad + per-iteration `MessageContext`
  reset (`postgres.c:4483-4594, :4628-4629`). Cited in postgres.c.md.

## Open questions

- Detailed `pmState` transition diagram is worth a separate data-structure
  doc.
- Extended-query bind/describe path inside `postgres.c` is only sketched —
  a query-lifecycle deep-doc would pay off.
- The full walsummary algorithm (across `walsummarizer.c`,
  `backup/walsummary.c`, `common/blkreftable.c`) is deferred to a
  backup-subsystem write-up.
