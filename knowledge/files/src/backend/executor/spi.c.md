# spi.c

- **Source:** `source/src/backend/executor/spi.c` (3404 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (connect/finish + execute + cursor + snapshot policy)

## Purpose

Server Programming Interface — the in-backend API that procedural
languages (`plpgsql`, `plperl`, `plpython`, `pltcl`, …) and built-in
commands like `EXPLAIN` use to execute SQL "from inside" a running
backend. Provides connect/finish lifecycle, parse/plan/execute,
cursors, and a per-call memory and snapshot regime that isolates each
nested SPI invocation from its callers. [from-comment] `:1-13`

## The SPI stack

Backend-global state, all in `spi.c`:

| Symbol | File:line | Role |
|---|---|---|
| `SPI_processed` | `:45` | API global: rowcount of most recent SPI_execute_* |
| `SPI_tuptable` | `:46` | API global: result tuptable pointer |
| `SPI_result` | `:47` | API global: most recent error / status code |
| `_SPI_stack` | `:49` | Array of `_SPI_connection` frames |
| `_SPI_current` | `:50` | Points into `_SPI_stack[_SPI_connected]` |
| `_SPI_stack_depth` | `:51` | Allocated size |
| `_SPI_connected` | `:52` | Top index, -1 when unconnected |

Comment at `:39-44` is candid: "These global variables are part of the
API for various SPI functions (a horrible API choice, but it's too
late now). To reduce the risk of interference between different SPI
callers, we save and restore them when entering/exiting a SPI nesting
level." Each `_SPI_connection` frame saves the outer values of
`SPI_processed / SPI_tuptable / SPI_result` and restores them in
`SPI_finish`.

## Connect / finish

### `SPI_connect_ext(options)` `:101`

1. Enlarge `_SPI_stack` if full (start at 16, double); palloc'd in
   `TopMemoryContext`. `:106-127`
2. Push a new frame, `_SPI_current = &_SPI_stack[++_SPI_connected]`. `:131-134`
3. Capture `connectSubid = GetCurrentSubTransactionId()` — used by
   `AtEOSubXact_SPI` to roll back this frame if the subxact aborts. `:141`
4. Set `atomic = !(options & SPI_OPT_NONATOMIC)`. `:143`
5. Create two AllocSet memory contexts: `procCxt` and `execCxt`. **The
   parent depends on atomicity**: atomic → `TopTransactionContext`,
   non-atomic → `PortalContext` so contexts survive transaction
   boundaries during `CALL` with `COMMIT/ROLLBACK`. `:149-167`
6. Save outer API globals, zero current ones, `MemoryContextSwitchTo(procCxt)`. `:145-176`

`SPI_connect()` `:95` is the no-options variant.

### `SPI_finish()` `:183`

Switch back to saved context; `MemoryContextDelete(execCxt)` then
`MemoryContextDelete(procCxt)` — this is the bulk-free that releases
everything allocated during the SPI call. Restore outer
`SPI_processed/tuptable/result`. Pop the stack. `:191-216`

## Internal transaction control

`SPI_commit` / `SPI_rollback` (with `_and_chain` variants) → static
`_SPI_commit` `:228` / `_SPI_rollback` `:333`. Both:

- Refuse if `_SPI_current->atomic` (must have used
  `SPI_OPT_NONATOMIC` at connect). `:239`
- Refuse if `IsSubTransaction()` — PL exception blocks must be
  resolved by their owners. `:254`
- `HoldPinnedPortals` + `ForgetPortalSnapshots` before
  `CommitTransactionCommand` / `AbortCurrentTransaction`. `:269-273`
- Immediately `StartTransactionCommand` after; on `_and_chain`,
  restore previously saved transaction characteristics. `:282`
- Wrapped in `PG_TRY` / `PG_CATCH` so a commit error aborts and
  re-throws under a fresh xact. `:263-317`

## Execute / prepare API surface

The user-facing exports `:597-859` are thin façades that build an
`SPIExecuteOptions` and call the workhorse `_SPI_execute_plan` `:2399`:

| Façade | File:line | Notes |
|---|---|---|
| `SPI_execute` | `:597` | Parse + plan + execute a one-shot SQL string |
| `SPI_execute_extended` | `:638` | Same with explicit params/options |
| `SPI_execute_plan` | `:673` | Re-use a previously SPI_prepared plan |
| `SPI_execute_plan_extended` | `:712` | With options |
| `SPI_execute_plan_with_paramlist` | `:734` | With ParamListInfo |
| `SPI_execute_snapshot` | `:774` | Snapshot/crosscheck — for RI triggers |
| `SPI_execute_with_args` | `:813` | Convenience: parse+plan+args |
| `SPI_prepare` / `SPI_prepare_*` | `:861-975` | Build a `_SPI_plan` via the plancache |
| `SPI_keepplan` / `SPI_saveplan` | `:977, 1004` | Move a temp plan to long-lived |

## `_SPI_execute_plan` snapshot policy `:2434-2476`

The richest part of the file. Four distinct behaviors are enumerated
in the comment at `:2435-2454`:

1. `snapshot != Invalid, read_only` → push exactly the given snap.
2. `snapshot != Invalid, !read_only` → push a copy, bump command-ID
   before each querytree.
3. `snapshot == Invalid, read_only` → use the Portal snapshot (or
   ActiveSnapshot if different) for queries that need one.
4. `snapshot == Invalid, !read_only` → in atomic mode take a fresh
   snapshot per user command and bump CID per querytree; in
   non-atomic mode use the Portal snapshot unmodified.

"`snapshot != InvalidSnapshot` implies an atomic execution context."
[from-comment] `:2458-2459`. Asserted at `:2464`.

The loop then walks `plan->plancache_list`, for each `CachedPlanSource`
either re-uses the cached plan or runs parse-analysis (oneshot path
`:2509+`), then `_SPI_pquery` `:2874` to run via the Portal machinery.

## Cursors

`SPI_cursor_open*` family `:1446-1576` → static `SPI_cursor_open_internal`
`:1578`. Wraps the prepared plan in a `Portal`, registers it under the
given name, and returns the Portal pointer. `SPI_cursor_fetch / move /
close` `:1807-1872` defer to `_SPI_cursor_operation` `:3007` which
sets up a `PortalRunFetch` against the SPI tuptable receiver.

`SPI_cursor_find(name)` `:1795` is a direct `GetPortalByName` lookup.

`SPI_scroll_cursor_fetch / move` `:1836, 1851` exist as a stricter
variant that errors if the underlying portal is not scrollable.

## Tuple / datum helpers

Mostly trivial accessors over `HeapTuple` / `TupleDesc`:
`SPI_fname / fnumber / getvalue / getbinval / gettype / gettypeid`
`:1176-1326`. Memory helpers `SPI_palloc / repalloc / pfree /
datumTransfer / copytuple / returntuple / freetuple / freetuptable`
`:1048-1442` all forward to standard mmgr APIs but in `_SPI_current
->procCxt` so the returned value survives the eventual `SPI_finish`
of an inner caller (important: SPI callers expect the result to outlive
nested SPI use).

## Ephemeral named relations

`SPI_register_relation` `:3297` / `SPI_unregister_relation` `:3331` /
`SPI_register_trigger_data` `:3364` — register transition tables
(`OLD`/`NEW` for AFTER triggers) into the current SPI frame's
`queryEnv` so subsequent SPI queries can reference them by name.

## Invariants

- All public SPI entry points except `SPI_connect*` call
  `_SPI_begin_call` `:3077` which checks `_SPI_connected >= 0`,
  asserts the stack pointer, and (`use_exec=true`) switches into
  `_SPI_current->execCxt`. `_SPI_end_call` `:3101` restores. [verified-by-code]
- Memory allocated in `execCxt` survives until next `SPI_execute_*` or
  `SPI_finish`. Memory in `procCxt` survives until `SPI_finish` of
  this frame. Callers that need longer-lived results must
  `SPI_palloc` (which uses the *outer* caller's context via savedcxt). [verified-by-code]
- The two SPI-context choice between TopTransactionContext and
  PortalContext is **only** about whether contexts cross COMMIT
  boundaries — non-atomic frames need PortalContext because
  TopTransactionContext is destroyed at xact end. [from-comment]
  `:149-160`
- `SPI_processed` / `SPI_tuptable` are saved+restored at each
  connect/finish — never trust them after a nested SPI call returns. [from-comment] `:39-44`
- Inside `_SPI_commit` / `_SPI_rollback` the frame is protected from
  deletion by `internal_xact = true`; without that, the
  `AtEOXact_SPI` callback would tear it down mid-commit. `:266`

## Cross-refs

- `knowledge/idioms/spi.md` (if/when written) — caller patterns.
- `knowledge/files/src/backend/executor/execMain.c.md` — SPI runs
  queries via the standard executor entry points it documents.
- `knowledge/files/src/backend/utils/mmgr/portalmem.c.md` — the
  Portal lifecycle that backs SPI cursors and non-atomic SPI memory.
- `knowledge/idioms/memory-contexts.md` — procCxt / execCxt are
  textbook example contexts.
- `source/src/include/executor/spi.h`, `spi_priv.h` — public + internal
  surface; `_SPI_connection` lives in spi_priv.h.

## Tags

- [verified-by-code] every entry-point cite, the stack layout, the
  begin/end-call discipline.
- [from-comment] the four-way snapshot policy at `:2435-2454`, the
  "horrible API choice" admission at `:39-44`, atomic-vs-non-atomic
  context choice at `:149-160`.
