# auxprocess.c

- **Source:** `source/src/backend/postmaster/auxprocess.c` (141 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## Purpose

Common init shared by aux processes (bgwriter, walwriter, walreceiver,
startup, checkpointer, archiver, walsummarizer). They do NOT do the full
`InitPostgres()` dance — no database connection — but they need just enough
to use LWLocks and shared memory. [from-comment] `:34-39`

## `AuxiliaryProcessMainCommon` (`:41-126`)

Sequence after fork:

1. `MemoryContextDelete(PostmasterContext)` — release the recyclable memory
   inherited from postmaster. `:46-50`
2. `init_ps_display(NULL)`.
3. `InitAuxiliaryProcess()` — allocate a `PGPROC` slot in the
   `AuxiliaryProcs` array (separate from the regular `PGPROC` array). `:67`
4. `BaseInit()` — basic per-backend init.
5. `HOLD_INTERRUPTS()` around `ProcSignalInit` + `InitLocalDataChecksumState`
   to avoid absorbing a barrier before checksum state is local-initialized.
   `:77-99`
6. `InitializeProcessXLogLogicalInfo` (must follow `ProcSignalInit` so the
   process participates in barriers). `:107`
7. `CreateAuxProcessResourceOwner` — aux processes don't run xacts but still
   need a resowner for buffer pins. `:114`
8. `pgstat_beinit` + `pgstat_bestart_initial` / `pgstat_bestart_final`.
9. Registers `ShutdownAuxiliaryProcess` via `before_shmem_exit` — releases
   any LWLocks at exit.
10. `SetProcessingMode(NormalProcessing)`.

## ShutdownAuxiliaryProcess (`:135-141`)

`LWLockReleaseAll`, `ConditionVariableCancelSleep`, `pgstat_report_wait_end`.
Critical only on error exit.

## Caller pattern

Every aux Main function (BackgroundWriterMain, WalWriterMain,
CheckpointerMain, PgArchiverMain, WalSummarizerMain, StartupProcessMain) calls
`AuxiliaryProcessMainCommon()` as its first non-Assert action.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
