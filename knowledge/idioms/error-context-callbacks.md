# Error context callbacks — error_context_stack pattern

PostgreSQL error messages can include nested context lines —
"while reading row 42 of /tmp/import.csv" inside "while
COPYing into orders" — by registering callbacks on a global
stack. Each callback runs when an `ereport` fires (any
severity), prepending its context message to the report.
Implemented as a singly-linked stack of structures the caller
pushes onto and pops off; `error_context_stack` is the head.

Anchors:
- `source/src/include/utils/elog.h:311-316` — the struct +
  global head [verified-by-code]
- `source/src/backend/utils/error/elog.c:519` — the
  dispatch loop [verified-by-code]
- `.claude/skills/error-handling/SKILL.md` — companion skill

## The struct + the stack

```c
typedef struct ErrorContextCallback
{
    struct ErrorContextCallback *previous;
    void   (*callback) (void *arg);
    void   *arg;
} ErrorContextCallback;

extern PGDLLIMPORT ErrorContextCallback *error_context_stack;
```

[verified-by-code `elog.h:311-316`]

`error_context_stack` is a process-local head pointer. Each
callback structure has a `previous` link forming a stack;
push by setting `previous = error_context_stack;
error_context_stack = &mine`, pop by
`error_context_stack = mine.previous`.

## The push-call-pop pattern

The canonical usage in a long-running code path:

```c
ErrorContextCallback errcallback;

errcallback.callback = copy_in_error_callback;
errcallback.arg = (void *) cstate;
errcallback.previous = error_context_stack;
error_context_stack = &errcallback;

/* ... do work that might raise an error ... */

error_context_stack = errcallback.previous;
```

The callback function:

```c
static void
copy_in_error_callback(void *arg)
{
    CopyState cstate = (CopyState) arg;
    errcontext("COPY %s, line %d",
               cstate->cur_relname, cstate->cur_lineno);
}
```

The callback calls `errcontext("...")` (which expands to
`set_errcontext_domain(TEXTDOMAIN), errcontext_msg(...)`
[verified-by-code `elog.h:214`]) to push the context message
into the in-flight error report.

## How `ereport` walks the stack

When `ereport` fires, `EmitErrorReport` walks
`error_context_stack` from head to tail
[verified-by-code `elog.c:519` + `elog.c:2281`]:

```c
for (econtext = error_context_stack;
     econtext != NULL;
     econtext = econtext->previous)
    econtext->callback(econtext->arg);
```

Each callback runs in turn, with **the most-recently-pushed
callback running first**. So the top-of-stack callback's
message appears first in the CONTEXT block of the error log.

This produces nested-context-style output:

```
ERROR:  division by zero
CONTEXT:  PL/pgSQL function f() line 5 at SQL statement
          SQL statement "SELECT ..."
          COPY foo, line 42, column bar: "0"
```

## Allocation: stack-local is canonical

The `ErrorContextCallback` struct **must live in stack
memory** (or another location guaranteed to outlive any
ereport on that code path). The reason: if an ereport fires
between push and pop, the stack walks `previous` chains;
freeing the struct from underneath the walk = use-after-free.

The standard idiom puts the struct on the C stack as a
local variable. The pop happens in the normal-exit path;
abnormal exit (ereport longjmp) unwinds the C stack
naturally, but `error_context_stack` is process-global —
**it still points at the freed memory**.

This is handled by `errstart` resetting the stack pointer:

```c
error_context_stack = NULL;   /* in elog.c:449 + :2233 */
```

after an error is reported (or at recovery cleanup). The
local-stack-allocation pattern is safe because the longjmp
returns to a sigsetjmp() handler that resets the stack
before any other ereport can run.

## The set_errcontext_domain interaction

[verified-by-code `elog.h:206-216`]

> errcontext() is typically called in error context callback
> functions, not within an ereport() invocation. The
> callback function can be in a different module than the
> ereport() call, so the message domain passed in errstart()
> is not usually the correct domain for translating the
> context message. set_errcontext_domain() first sets the
> domain to be used, and errcontext_msg() passes the actual
> message.

The `errcontext` macro handles this transparently — it
expands to a `set_errcontext_domain(TEXTDOMAIN)` followed by
the actual `errcontext_msg(...)`. The domain ensures the
context message is translated using the callback module's
message catalog, not the ereport caller's.

## When to push a context callback

- **Long-running loops** that process row-N-of-many. Push at
  loop start, update the per-row identifier, errors get
  "while processing row N" automatically.
- **Recursive descent over user data** — push per
  recursion level so the error stack shows the parse path.
- **PL/pgSQL function call** — every PL/pgSQL frame pushes a
  context. Errors include the function name + line.
- **COPY** — per-line context for "row 42 column 3" errors.

## When NOT to push

- For one-shot operations where the surrounding code is
  obvious from the error message itself. Adds clutter.
- For callbacks that allocate or call back into the same
  subsystem — the callback runs in the ereport context, with
  limited stack and possibly inside a critical section.
  Cheap and side-effect-free is the rule.
- Inside a hot per-tuple loop — per-tuple push/pop has
  measurable overhead. Push once at scan-start, update the
  per-tuple state, pop at scan-end.

## Callback rules

- **Don't allocate in the callback** unless trivially small;
  the ereport may already be near-OOM.
- **Don't call into other subsystems** that may themselves
  ereport — risk of recursion.
- **Don't acquire locks** in the callback.
- **Cheap string formatting only** — `errcontext("...",
  format args...)` is the entirety of a well-behaved callback.

## Common review-time concerns

- **Pop in BOTH normal and error paths.** The standard `PG_TRY`/
  `PG_CATCH` block isn't needed for the local-stack approach
  because the longjmp-then-error-handler clears the stack.
  But if the struct is on the heap, you need explicit cleanup.
- **The struct outlives the push.** Stack-local works because
  push and pop happen in the same function. Cross-function
  pushes need heap allocation + manual cleanup.
- **Callback runs at any ereport severity.** Including
  `NOTICE` / `INFO`. If you only want the context on ERROR,
  the callback should check `geterrcode()`.

## Invariants

- **[INV-1]** Top-of-stack callback runs first; messages
  appear in push-order (newest first).
- **[INV-2]** The struct must outlive any ereport on this
  code path. Stack-local is the canonical pattern.
- **[INV-3]** `errstart` clears `error_context_stack`;
  this is the safety net for longjmp unwind.
- **[INV-4]** Callbacks should be cheap and side-effect-free
  — no allocation, no locking, no recursion.
- **[INV-5]** `errcontext` macro sets the message domain
  for translation; use it (not bare `errcontext_msg`).

## Useful greps

- All callback registration sites:
  `grep -RIn 'error_context_stack =' source/src/backend | head -30`
- All callback function definitions:
  `grep -RIn '_error_callback\b' source/src/backend | head -20`
- The dispatch loop:
  `grep -n 'error_context_stack' source/src/backend/utils/error/elog.c | head -5`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/commands/copyfromparse.c`](../files/src/backend/commands/copyfromparse.c.md) | — | canonical consumer (COPY emits per-line context) |
| [`src/backend/utils/error/elog.c`](../files/src/backend/utils/error/elog.c.md) | 519 | dispatch loop |
| [`src/backend/utils/error/elog.c`](../files/src/backend/utils/error/elog.c.md) | — | implementation; the EmitErrorReport dispatch loop |
| [`src/include/utils/elog.h`](../files/src/include/utils/elog.h.md) | 311 | the struct + global head |
| [`src/include/utils/elog.h`](../files/src/include/utils/elog.h.md) | — | public API + struct |
| [`src/pl/plpgsql/src/pl_exec.c`](../files/src/pl/plpgsql/src/pl_exec.md) | — | heavy user (per-function-frame context) |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-error-code`](../scenarios/add-new-error-code.md)
- [`integrate-with-plpgsql`](../scenarios/integrate-with-plpgsql.md)

<!-- /scenarios:auto -->

## Cross-references

- `.claude/skills/error-handling/SKILL.md` — ereport + PG_TRY
  + error-context skill; this idiom plugs into it.
- `.claude/skills/coding-style/SKILL.md` — error-message
  composition style; context messages follow the same rules.
- `knowledge/idioms/sinvaladt-broadcast.md` — adjacent
  cross-module pattern (different mechanism, similar
  callback-on-event flavor).
- `source/src/include/utils/elog.h` — public API + struct.
- `source/src/backend/utils/error/elog.c` — implementation;
  the `EmitErrorReport` dispatch loop.
- `source/src/backend/commands/copyfromparse.c` — canonical
  consumer (COPY emits per-line context).
- `source/src/pl/plpgsql/src/pl_exec.c` — heavy user
  (per-function-frame context).
