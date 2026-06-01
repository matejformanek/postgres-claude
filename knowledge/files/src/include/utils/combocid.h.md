# combocid.h

- **Source path:** `source/src/include/utils/combocid.h`
- **Lines:** 28
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `backend/utils/time/combocid.c`, `access/htup.h` (where `HeapTupleHeaderGetCmin/Cmax` *prototypes* live, per comment lines 17-21)

## Purpose

Tiny header exposing only the parallel-worker / xact-end interface of combocid.c. `HeapTupleHeaderGetCmin` / `HeapTupleHeaderGetCmax` prototypes are deliberately housed in `access/htup.h` because they replaced macro definitions that used to live there. [from-comment, combocid.h:17-21]

## Exported functions

- `AtEOXact_ComboCid(void)` — wipe per-xact state.
- `RestoreComboCIDState(char *)` — parallel worker side.
- `SerializeComboCIDState(Size maxsize, char *start_address)` — parallel leader side.
- `EstimateComboCIDStateSpace(void)` — sizing.

## Cross-references

- Full deep-dive at `knowledge/files/src/backend/utils/time/combocid.c.md`.

## Confidence tag tally

`[verified-by-code]=1 [from-comment]=1 [from-readme]=0 [inferred]=0 [unverified]=0`
