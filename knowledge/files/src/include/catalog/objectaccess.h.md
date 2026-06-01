# objectaccess.h

- **Source path:** `source/src/include/catalog/objectaccess.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Object access hooks." Declares the `object_access_hook` extension point and the per-event Invoke* macros that conditionally fire it. Used by sepgsql and any auditing extension.

## Key declarations

- `ObjectAccessType` enum: `OAT_POST_CREATE`, `OAT_DROP`, `OAT_POST_ALTER`, `OAT_NAMESPACE_SEARCH`, `OAT_FUNCTION_EXECUTE`, `OAT_TRUNCATE`.
- `ObjectAccessPostCreate`, `ObjectAccessDrop`, `ObjectAccessPostAlter`, `ObjectAccessNamespaceSearch` arg-structs (carry per-event subflags).
- `object_access_hook` — the pointer extensions install into.
- `InvokeObjectPostCreateHook[Arg]`, `InvokeObjectDropHook[Arg]`, `InvokeObjectPostAlterHook[Arg]`, `InvokeNamespaceSearchHook`, `InvokeFunctionExecuteHook`, `InvokeObjectTruncateHook` macros — guarded by `if (object_access_hook != NULL)`. Plus `*Str` variants for bootstrap-time string-named objects.

## Tally

`[verified-by-code]=1 [inferred]=1`
