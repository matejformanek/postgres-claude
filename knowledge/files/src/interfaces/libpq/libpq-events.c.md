# libpq-events.c

- **Source path:** `source/src/interfaces/libpq/libpq-events.c`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 212 lines

## Purpose

Implementation of the libpq events plugin API declared in `libpq-events.h`. Six public functions, no internal helpers.

## Behavior notes

### `PQregisterEventProc` (lines 39-91)

- Rejects null `proc`/`conn`/`name`, or empty name string (line 46-47).
- **Refuses re-registration of the same proc** on a conn (lines 49-53); the proc address doubles as the unique key for `PQinstanceData`. [verified-by-code]
- Grows the `events` array by doubling, starting at 8 (line 60). On malloc/realloc failure returns 0 — but the partial bookkeeping from a prior call is preserved.
- Copies the name via `strdup` (line 74). If strdup fails, the function returns false **but leaves `nEvents` already incremented and the new event slot half-initialized** — see Phase D below. [verified-by-code]
- Fires `PGEVT_REGISTER` synchronously (line 83-88). If the plugin returns 0, the registration is rolled back: `nEvents--` and the name is freed.

### `PQsetInstanceData` / `PQinstanceData` (lines 97-135)

Linear scan over `events[]` looking for matching proc address. Returns false / NULL if not found. O(n) in number of registered procs (small in practice).

### `PQresultSetInstanceData` / `PQresultInstanceData` (lines 141-177)

Same linear-scan logic, but over the **result's** events array, which is a snapshot of the conn's events at the time the result was constructed.

### `PQfireResultCreateEvents` (lines 184-211)

For each event on the result, fire RESULTCREATE if `resultInitialized` is false. Sets the flag on success; on failure (proc returns 0) leaves the flag false and accumulates a return-false but **keeps firing remaining events** (no short-circuit). [verified-by-code, lines 193-208]

## Plugin trust boundary (Phase D)

Plugins are loaded into the libpq process and run with full access to:

- The `PGconn` pointer (every event hands one over except RESULTDESTROY).
- Through `PGconn` (cast to `struct pg_conn` via libpq-int.h), all credential fields: `pgpass`, `sslpassword`, `oauth_token`, `scram_*_key`, `connhost[i].password`.
- All buffered query data (`inBuffer`/`outBuffer`).
- The trace `FILE *Pfdebug` (could redirect or write to).

Registration is not authenticated — any code linked into the process can call `PQregisterEventProc`. Plugins are part of the application's TCB by definition.

[ISSUE-libpq-events-001 — maybe] Partial-failure rollback in `PQregisterEventProc` is incomplete: when `strdup(name)` fails (line 74-76), the function returns false but has already advanced `nEvents` (line 80 ordering is OK actually — let me re-read). Re-checking: nEvents is incremented at line 80, *after* the strdup check at line 75-76. So strdup failure correctly returns before the increment. **However**, if `strdup` succeeds but `proc(PGEVT_REGISTER, ...)` returns 0, the rollback at lines 84-87 uses `conn->nEvents--` then frees `events[conn->nEvents].name` — correct. Verdict: no bug, but the control flow is fragile.

[ISSUE-libpq-events-002 — maybe] `PGEVT_RESULTDESTROY` is documented in the header but **not fired anywhere in this file**. It must fire from `PQclear` in fe-exec.c. The asymmetry — create/copy here, destroy elsewhere — is easy to miss when reviewing event-lifecycle changes.

[ISSUE-libpq-events-003 — maybe] No `PQunregisterEventProc`. Once registered, a proc lives until `PQfinish`. Plugins that want to detach (e.g. before unloading a shared library) can't. Comment at libpq-events.h doesn't mention this constraint.

[ISSUE-libpq-events-004 — maybe] `PQregisterEventProc` synchronously fires PGEVT_REGISTER while `nEvents` already points at the new slot. A plugin that re-enters libpq during its REGISTER callback (e.g. calling `PQinstanceData`) will find itself in the events list mid-init. Whether this is intended is unclear.

## Tally

`[verified-by-code]=4 [from-comment]=0 [maybe]=4`
