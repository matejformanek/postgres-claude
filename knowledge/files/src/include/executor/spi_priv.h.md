# spi_priv.h

- **Source:** `source/src/include/executor/spi_priv.h` (105 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (whole file)

## Purpose

Private header for `spi.c`. Defines the internal SPI connection-context
struct and the magic number for plan validation.

## Structures

- `_SPI_PLAN_MAGIC = 569278163` — sentinel in `SPIPlanPtr` to detect use
  of a freed plan or arbitrary pointer cast.
- `_SPI_connection` — one entry on the SPI call stack:
  - `processed`, `tuptable` — current results.
  - `execSubid` — subxact in which the call started; abort handler clears
    state on subxact rollback.
  - `procCxt` — per-call MemoryContext (lifetime = SPI_finish).
  - `execCxt` — used during one executor invocation; child of procCxt.
  - `connectSubid`, `queryEnv`, `atomic`, `plan_owner`, …

## SPI plan layout

`_SPI_plan` — wraps a list of `CachedPlanSource`s (one per parsetree of the
input query string). Lifecycle managed via plancache (utils/cache/plancache.c)
and a per-plan ResourceOwner.

## Tags

- [verified-by-code] struct definitions + magic number.
- [from-comment] file header.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
