# ProcessUtility hook chain — extending non-DML execution

Every non-DML SQL statement — CREATE, DROP, ALTER, VACUUM,
TRUNCATE, COPY, GRANT, etc. — passes through `ProcessUtility`
in `src/backend/tcop/utility.c`. Extensions intercept this via
the `ProcessUtility_hook` function pointer, which lets them
observe, modify, or replace the standard handling. The
chained-hook pattern (each extension wraps the previous hook +
finally calls `standard_ProcessUtility`) is the canonical
mechanism for SQL-level DDL extensions.

Anchors:
- `source/src/backend/tcop/utility.c:72` —
  ProcessUtility_hook global [verified-by-code]
- `source/src/backend/tcop/utility.c:504-525` —
  ProcessUtility entry + hook dispatch [verified-by-code]
- `source/src/backend/tcop/utility.c:548` —
  standard_ProcessUtility [verified-by-code]
- `source/src/backend/tcop/utility.c:1094` —
  ProcessUtilitySlow [verified-by-code]
- `knowledge/idioms/event-trigger-firing.md` — companion
- `knowledge/idioms/cache-invalidation-registration.md` —
  companion (DDL triggers inval)
- `.claude/skills/extension-development/SKILL.md` — companion
- `.claude/skills/bgworker-and-extensions/SKILL.md` — companion

## The entry + dispatch

[verified-by-code `utility.c:504-525`]

```c
void
ProcessUtility(PlannedStmt *pstmt, const char *queryString,
               bool readOnlyTree, ProcessUtilityContext context,
               ParamListInfo params, QueryEnvironment *queryEnv,
               DestReceiver *dest, QueryCompletion *qc)
{
    /* sanity checks */
    Assert(IsA(pstmt, PlannedStmt));
    Assert(pstmt->commandType == CMD_UTILITY);
    Assert(queryString != NULL);

    if (ProcessUtility_hook)
        (*ProcessUtility_hook) (pstmt, queryString, readOnlyTree,
                                context, params, queryEnv, dest, qc);
    else
        standard_ProcessUtility(pstmt, queryString, readOnlyTree,
                                context, params, queryEnv, dest, qc);
}
```

The dispatch is one branch: hook installed → call hook; else
call standard.

## The chained-hook pattern

Extensions typically install their hook like this:

```c
static ProcessUtility_hook_type prev_hook = NULL;

void
_PG_init(void)
{
    prev_hook = ProcessUtility_hook;
    ProcessUtility_hook = my_process_utility;
}

static void
my_process_utility(PlannedStmt *pstmt, ...)
{
    /* pre-processing — observe / modify the statement */
    if (is_special_case(pstmt)) {
        do_my_thing(pstmt);
        return;
    }

    /* chain to next */
    if (prev_hook)
        prev_hook(pstmt, queryString, ...);
    else
        standard_ProcessUtility(pstmt, queryString, ...);

    /* post-processing */
}
```

Each extension wraps the previous hook value at load time;
final extension's hook is the entry. Standard is the leaf.

## ProcessUtilityContext — where the call originated

[from `utility.c`]

```c
typedef enum
{
    PROCESS_UTILITY_TOPLEVEL,       /* direct from client */
    PROCESS_UTILITY_QUERY,          /* nested in a query */
    PROCESS_UTILITY_QUERY_NONATOMIC, /* nested, non-atomic */
    PROCESS_UTILITY_SUBCOMMAND,     /* explicit subcommand */
} ProcessUtilityContext;
```

The hook receives this so it can distinguish:
- A `CREATE TABLE` from the client.
- A `CREATE TABLE AS SELECT` issuing it internally.
- A subcommand from another DDL (e.g., ALTER TABLE which adds
  a constraint).

Extensions often only care about TOPLEVEL.

## ProcessUtilitySlow — the catalog-modifying path

[verified-by-code `utility.c:1094`]

After basic command-tag dispatching, `standard_ProcessUtility`
calls `ProcessUtilitySlow` for the "real" catalog-modifying
commands. The slow path:
1. Calls `EventTriggerDDLCommandStart` (start event triggers).
2. Switches on the statement type, invoking the appropriate
   `tablecmds.c` / `extension.c` / `view.c` etc. handler.
3. Each handler updates catalogs.
4. Calls `EventTriggerSQLDrop` / `EventTriggerDDLCommandEnd` /
   `EventTriggerTableRewrite` as appropriate.

Why "slow": the fast path handles trivial commands (e.g.,
SET, BEGIN, COMMIT) without going through the event-trigger
machinery.

## The protocol-level path

[from `postgres.c` + `commands/portalcmds.c`]

For a simple query message:
```
exec_simple_query → exec_run_utility → ProcessUtility
```

For a parse/bind/execute:
```
exec_execute_message → portal->utilityStmt → ProcessUtility
```

Both paths converge on `ProcessUtility`; extensions catch all.

## Common extension uses

- **Audit logging** (pgaudit) — log every DDL with details.
- **Schema-level access control** — reject unauthorized
  CREATE/DROP.
- **DDL replication** (BDR-style, repmgr) — capture for
  forwarding.
- **Custom command rewriting** — e.g. CREATE EXTENSION
  validation, multi-tenant isolation.
- **Query plan tracking** — pg_stat_statements catches normal
  queries via planner_hook + ExecutorStart_hook, but DDL
  needs ProcessUtility_hook.

## The readOnlyTree flag

```c
bool readOnlyTree;
```

True if the parsetree was supplied from a cached PlannedStmt
and SHOULD NOT be modified. Extensions that mutate the parse
tree must copy it first if readOnlyTree is true.

Most extensions don't mutate; they observe. The flag matters
mostly for DDL-replication extensions that need to deparse
the immutable original.

## Interaction with EventTriggers

[per `event-trigger-firing` companion]

ProcessUtility_hook and EventTriggers are TWO distinct
extensibility points:
- **ProcessUtility_hook** — C-level, runs in every backend
  on every utility statement.
- **EventTrigger** — SQL-level, fires PL/pgSQL functions on
  specific DDL events.

ProcessUtility_hook can intercept BEFORE EventTriggers run;
EventTriggers run inside `ProcessUtilitySlow`.

## When the hook isn't called

[from-code `utility.c`]

A few utility paths bypass ProcessUtility entirely:
- Internal catalog ops via `simple_heap_*` direct.
- `pg_class.relhastriggers` recompute.
- Bootstrap mode (`InitProcessing == B_BOOTSTRAP`).
- Some recovery-only paths.

For client-issued SQL: always goes through ProcessUtility.

## Common review-time concerns

- **Always chain previous hook** — don't break the extension
  stack.
- **Restore hook on _PG_fini** if cleanup is supported.
- **readOnlyTree respect** — copy before mutation.
- **TOPLEVEL vs nested context** — most extensions only want
  TOPLEVEL.
- **EventTriggers run INSIDE the hook's chain** — order
  matters.
- **Use ProcessUtility_hook for INTERCEPT; EventTriggers for
  ROUTING SQL handlers.**

## Invariants

- **[INV-1]** ProcessUtility_hook is a global function pointer
  + standard fallback.
- **[INV-2]** Extensions chain via prev_hook capture in
  _PG_init.
- **[INV-3]** standard_ProcessUtility is the leaf.
- **[INV-4]** ProcessUtilitySlow handles catalog mutations
  + EventTrigger firing.
- **[INV-5]** readOnlyTree forbids parse-tree mutation
  without copy.

## Useful greps

- The hook + dispatch:
  `grep -n 'ProcessUtility_hook\|standard_ProcessUtility' source/src/backend/tcop/utility.c | head -10`
- Chain example users:
  `grep -RIn 'ProcessUtility_hook_type prev' source/contrib | head -10`
- ProcessUtilityContext switch:
  `grep -n 'PROCESS_UTILITY_TOPLEVEL\|PROCESS_UTILITY_QUERY' source/src/backend | head -10`

## Cross-references

- `knowledge/idioms/event-trigger-firing.md` — fires from
  inside ProcessUtilitySlow.
- `knowledge/idioms/cache-invalidation-registration.md` —
  DDL → invalidate.
- `knowledge/idioms/cached-plan-invalidation.md` — DDL
  invalidates plans.
- `knowledge/idioms/ddl-deparse-via-event-triggers.md` —
  capturing DDL for replication.
- `knowledge/subsystems/tcop.md` — tcop subsystem.
- `.claude/skills/extension-development/SKILL.md` —
  installing hooks.
- `.claude/skills/bgworker-and-extensions/SKILL.md` —
  hook stacking conventions.
- `source/src/backend/tcop/utility.c:504` — entry.
- `source/src/include/tcop/utility.h` — public API.
