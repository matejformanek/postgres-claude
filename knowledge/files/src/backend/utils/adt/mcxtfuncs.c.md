# src/backend/utils/adt/mcxtfuncs.c

## Purpose

Two SQL functions for memory-context introspection:
1. `pg_get_backend_memory_contexts()` — SRF over the calling backend's own
   MemoryContext tree (`TopMemoryContext` and all descendants), returning
   per-context name, ident, type, level, path, totalspace, nblocks,
   freespace, freechunks, used_bytes.
2. `pg_log_backend_memory_contexts(pid)` — sends `PROCSIG_LOG_MEMORY_CONTEXT`
   to another backend / auxiliary process, causing it to log its memory
   contexts at the next `CHECK_FOR_INTERRUPTS()`.

## Role in PG

- `pg_get_backend_memory_contexts` only walks **the calling backend's
  own** contexts — no cross-backend introspection. (Compare with
  `pg_log_backend_memory_contexts`, which signals another backend to
  log to the server log.)
- Backs the `pg_backend_memory_contexts` system view.

## Key functions

- `int_list_to_array(list)` (`mcxtfuncs.c:50-66`) — helper to build the
  ancestor-chain `int4[]` column.
- `PutMemoryContextsStatsTupleStore(tupstore, tupdesc, context,
  context_id_lookup)` (`:72-179`) — emits one row. Calls
  `context->methods->stats(context, NULL, NULL, &stat, true)` to harvest
  counters. Special-cases "dynahash"-named contexts: relabels with the
  ident (the hash table name), à la `MemoryContextStatsPrint`
  (`:119-123`). Truncates `ident` to
  `MEMORY_CONTEXT_IDENT_DISPLAY_SIZE = 1024` via `pg_mbcliplen`
  (`:139-143`) — important because some idents are SQL query strings.
- `pg_get_backend_memory_contexts(PG_FUNCTION_ARGS)` (`:185-251`).
  Non-recursive BFS over the tree starting at `TopMemoryContext`;
  context_ids assigned breadth-first so context_id of long-lived
  contexts stays stable across calls (`:206-214`).
- `pg_log_backend_memory_contexts(pid)` (`:266-310`).
  `BackendPidGetProc(pid)` then fallback to `AuxiliaryPidGetProc(pid)`,
  then `SendProcSignal(pid, PROCSIG_LOG_MEMORY_CONTEXT, procNumber)`.
  Returns `false` (with WARNING) on missing PID or send failure so
  `SELECT pg_log_backend_memory_contexts(pid) FROM
  pg_stat_activity` continues even if a backend exits mid-loop.

## State / globals

None.

## Phase D notes

- **Self-only introspection**: `pg_get_backend_memory_contexts`
  exposes the *calling* backend's contexts. There's no way to inspect
  another backend's contexts directly from SQL — the signal path
  forces the target to log to the server log, so the data ends up in
  log files (subject to the configured `log_destination`).
- **Default ACL**: per pg_proc.dat, `pg_log_backend_memory_contexts`
  is declared with `proacl => '{POSTGRES=X}'` (superuser-only by
  default; comment on `:257-260` says so explicitly: "By default,
  only superusers are allowed … to issue this request at an unbounded
  rate would cause lots of log messages and which can lead to denial
  of service. Additional roles can be permitted with GRANT.")
  `pg_get_backend_memory_contexts` has no explicit ACL (PUBLIC EXECUTE)
  but only reveals the caller's own state, so info disclosure surface
  is null.
- **Ident truncation**: `MEMORY_CONTEXT_IDENT_DISPLAY_SIZE = 1024`
  with `pg_mbcliplen` ensures the result row doesn't blow up on a huge
  query string used as context ident — and respects multibyte
  boundaries. Good.
- **Signal vs lock-free**: comment at `:280-288` documents the race —
  `BackendPidGetProc` might return non-NULL just before the target
  exits, so `SendProcSignal` may target a stale PID. Treated as
  benign: "since this mechanism is usually used to debug a backend …
  consuming lots of memory, that it might end on its own first and
  its memory contexts are not logged is not a problem."

## Potential issues

- [ISSUE-info-disclosure: `pg_get_backend_memory_contexts` exposes
  every context's `name` and `ident` — for `ExecutorState` contexts
  the ident is often the SQL query text. If a SECURITY DEFINER
  function calls `pg_get_backend_memory_contexts`, the calling
  role sees the SECURITY DEFINER body's query text in the result.
  Self-reflection, but worth flagging. (low)]
- [ISSUE-dos: `pg_log_backend_memory_contexts` is rate-limit-free.
  An admin who GRANTs EXECUTE to a broader role for monitoring opens
  a log-flood DoS. Comment notes the risk (`:257-260`); enforcement
  is by ACL alone (low if ACL stays tight)]
- [ISSUE-correctness: `context->methods->stats(context, NULL, NULL,
  &stat, true)` (`:107`) is called inside the SRF — for very large
  trees this is O(contexts) per call; cumulative malloc inside the
  callbacks could trigger additional context creation (`stats`
  must be allocator-quiet, which is documented elsewhere). (low)]
