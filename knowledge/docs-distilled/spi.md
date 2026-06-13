---
source_url: https://www.postgresql.org/docs/current/spi.html
fetched_at: 2026-06-13T19:50:00Z
anchor_sha: e18b0cb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Server Programming Interface — overview (internals ch. 47.1)

SPI is the in-backend API for running SQL from C (the parser/planner/executor
behind a simplified surface). Every PL handler is an SPI client. This distills
the *overview* contract; the function reference pages (SPI_execute, SPI_prepare,
…) are separate. Pairs with the `fmgr-and-spi` skill and `idioms/spi.md`.

## Non-obvious claims

- **Lifecycle is bracketed:** `SPI_connect()` before any SPI call, `SPI_finish()`
  after. SPI calls are only valid inside that bracket. [from-docs]
- **🔑 Two memory contexts.** During SPI the *procedure* (caller) context and the
  *upper executor* context are distinct. Anything you want to survive past
  `SPI_finish()` must be allocated/copied into the **upper executor context** via
  `SPI_palloc` / `SPI_repalloc` / `SPI_copytuple` / `SPI_returntuple`; the
  ordinary per-call SPI result memory is reclaimed on `SPI_finish`. Cleanup
  helpers: `SPI_pfree`, `SPI_freetuple`, `SPI_freetuptable`. [from-docs] Getting
  this wrong is the classic "tuple freed under me" SPI bug.
- **Error handling is non-local (longjmp).** On a failed SPI command, control does
  **not** return to your C function with an error code — the whole
  (sub)transaction is rolled back via `ereport(ERROR)`/longjmp. To *recover*, the
  caller must wrap the risky call in its own subtransaction
  (BeginInternalSubTransaction / PG_TRY). [from-docs] This is the most common SPI
  surprise for people expecting C-style return-code error handling.
- **Return convention:** nonnegative result (or in the global `SPI_result`) on
  success; negative / NULL on failure. The result set lands in the global
  `SPI_tuptable` (with `SPI_processed` row count). [from-docs]
- **Read-only vs read-write execution** is an explicit parameter on the execute
  calls — read-only calls reuse the caller's snapshot and forbid data-modifying
  commands; read-write calls take a fresh snapshot per command. This is also how
  visibility of just-made changes is controlled (ch. 47.5). [from-docs]
- **Transaction control inside SPI** (`SPI_commit`, `SPI_rollback`) is allowed only
  in contexts where it's legal (e.g. procedures / top-level PL blocks), not inside
  a surrounding query. `SPI_start_transaction` is **obsolete** — don't use in new
  code. [from-docs]
- **Header:** `#include "executor/spi.h"`. [from-docs]

## Links into corpus

- Per-file: [[knowledge/files/src/backend/executor/spi.c.md]]
  (the implementation of every SPI_* entry point + the two-context dance).
- Idiom: [[knowledge/idioms/spi.md]] (the working patterns / recipes),
  [[knowledge/idioms/fmgr.md]] (the C function surface SPI clients live in),
  [[knowledge/idioms/catalog-conventions.md]].
- Siblings: `knowledge/docs-distilled/plhandler.md` (PL handlers are the canonical
  SPI consumers), `knowledge/docs-distilled/xfunc-c.md`.
