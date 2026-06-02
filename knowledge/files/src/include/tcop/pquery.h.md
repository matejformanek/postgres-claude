# pquery.h

- **Source:** `source/src/include/tcop/pquery.h`
- **Depth:** skim

## Symbols

- `ActivePortal` extern global.
- `CreateQueryDesc`, `FreeQueryDesc`.
- `ProcessQuery` (one-shot ExecutorStart..End).
- `PortalStart`, `PortalSetResultFormat`, `PortalRun`, `PortalRunFetch`.
- `EnsurePortalSnapshotExists`.
- `ChoosePortalStrategy`, `FetchPortalTargetList`, `FetchStatementTargetList`.

Portal struct itself is declared in `utils/portal.h`; storage of portals
(create/drop/lookup-by-name) is in `utils/mmgr/portalmem.c`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/tcop.md](../../../../subsystems/tcop.md)
