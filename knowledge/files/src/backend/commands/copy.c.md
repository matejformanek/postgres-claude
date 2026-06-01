# copy.c

- **Source path:** `source/src/backend/commands/copy.c`
- **Lines:** 1142
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `copy.h`, `copyapi.h`, `copyfrom_internal.h`, `copyfrom.c`, `copyfromparse.c`, `copyto.c`.

## Purpose

"Implements the COPY utility command." [from-comment, copy.c:3-4] This file is the **option-parsing and dispatch layer** — it owns `DoCopy` (the entry from `ProcessUtility`), reads/validates every `WITH (option ...)` choice, performs permission checks on the target relation, and then hands off to `copyfrom.c` for COPY FROM or `copyto.c` for COPY TO. Format-specific parsing/serialisation lives in `copyfromparse.c` / `copyto.c` (text, CSV, binary).

## Public surface

- `DoCopy` (63) — utility entry. Determines direction (FROM vs TO), opens the relation with the right lock (`RowExclusiveLock` for FROM into a table; `AccessShareLock` for TO from a table; FROM/TO a query has no relation), calls `ProcessCopyOptions`, then invokes either `BeginCopyFrom` + `CopyFrom` + `EndCopyFrom` (in copyfrom.c) or `BeginCopyTo` + `DoCopyTo` + `EndCopyTo` (in copyto.c).
- `defGetCopyHeaderOption` (396), `defGetCopyOnErrorChoice` (479), `defGetCopyRejectLimitOption` (514), `defGetCopyLogVerbosityChoice` (541) — DefElem extractors for COPY-specific options.
- `ProcessCopyOptions` (581) — **the central options validator**. ~480 lines: enforces mutual exclusivity (`BINARY` vs `CSV`, `FREEZE` only with FROM into a freshly-truncated table, `HEADER MATCH` requires text/CSV, etc.), parses delimiter/quote/escape, validates encoding compatibility.
- `CopyGetAttnums` (1068) — translate the `(col1, col2, ...)` column-list AST into an integer attnum list, validating uniqueness and existence.

## COPY's interaction with bulk-insert machinery

When COPY FROM hits a plain (non-partitioned, no row-level triggers, no volatile defaults) table, it takes a fast path through `heap_multi_insert` (via the tableam `multi_insert` callback) — that's why `copyfrom.c` builds a `CopyMultiInsertBuffer` per result-relation and flushes 1000-row batches. The handoff is in `copyfrom.c:CopyFrom`, not here.

## Format-extension architecture (PG 18)

The Custom Copy Format API (`copyapi.h`) lets extensions register a format other than `text`/`csv`/`binary`. Format implementations supply a `CopyFromRoutine` (for FROM) or `CopyToRoutine` (for TO) of function pointers; `copy.c`'s option parser dispatches on `format` to set these. The built-in routines are `CopyFromTextLikeRoutine` / `CopyToTextLikeRoutine` (text and CSV share state), `CopyFromBinaryRoutine` / `CopyToBinaryRoutine`, `CopyToJsonRoutine`. [verified-by-code, copyto.c:201, copyfrom.c:158]

## Tests

- `src/test/regress/sql/copy.sql`, `copy2.sql`, `copydml.sql`, `copyselect.sql`, `copyencoding.sql`, `binary.sql`.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
