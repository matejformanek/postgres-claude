# Deep-copying a Node tree

## The right tool: `copyObject(p)`

```c
Node *dup = (Node *) copyObject(expr);
```

`copyObject` is the canonical deep-copy entry point. Defined as a macro in `source/src/include/nodes/nodes.h:228-233` — when the compiler supports `typeof_unqual`, the macro casts the result back to the argument type so you don't need a manual `(Foo *)` cast:

```c
Foo *dup = copyObject(orig);    /* type-preserved */
```

Underneath, the macro calls `copyObjectImpl(const void *)` in `source/src/backend/nodes/copyfuncs.c:176-212`. (`knowledge/files/src/backend/nodes/copyfuncs.c.md`.)

## What it actually does

`copyObjectImpl` is a big `switch (nodeTag(from))` over every `T_*` tag, dispatching to per-node `_copyFoo` functions. Most of those bodies are **generated** by `gen_node_support.pl` and live in the included `copyfuncs.funcs.c`. The file itself only hand-writes:

- Field-copy macros: `COPY_SCALAR_FIELD`, `COPY_NODE_FIELD`, `COPY_BITMAPSET_FIELD`, `COPY_STRING_FIELD`, `COPY_ARRAY_FIELD`, `COPY_POINTER_FIELD`, `COPY_LOCATION_FIELD` (`copyfuncs.c:29-62`).
- Hand-written specials for `Const`, `A_Const`, `ExtensibleNode`, `Bitmapset` (`:72-167`).
- The dispatch switch via `#include "copyfuncs.switch.c"` (`:176-212`).

For each node type the generated `_copyFoo` walks each field according to the macro family — scalar fields are straight-assigned; `Node *` fields recurse via `copyObject`; strings are `pstrdup`'d; bitmapsets go through `bms_copy`; lists are deep-copied. The result is a fully independent tree allocated in the current memory context — scribble away.

## Gotchas

### 1. By-ref Datums (`Const` nodes)

The hand-written `_copyConst` (`copyfuncs.c:72-105`) is the only path that knows whether a `Const`'s `constvalue` is by-value or by-reference. For by-ref non-null Datums it calls `datumCopy`, which `pmemcpy`s the value into the current memory context. A generic generated copy could not know this. If you ever add a node holding a raw `Datum` you'll likely need `pg_node_attr(custom_copy_equal)` and a hand-written copier.

### 2. `A_Const` value union

`_copyA_Const` (`:107-144`) dispatches on the embedded `Value` tag (`T_Integer`/`T_Float`/`T_Boolean`/`T_String`/`T_BitString`) — copies the active union member. If you stash a value-node in your own struct, make sure the right union arm is copied.

### 3. Extensible nodes

`_copyExtensibleNode` (`:146-161`) looks up the extension-registered `nodeCopy` callback. Custom-scan / FDW / extension authors register their methods via `RegisterExtensibleNodeMethods`; if you forget, copy is a no-op or crashes. See `knowledge/files/src/backend/nodes/extensible.c.md`.

### 4. List flavors

`copyObjectImpl` dispatches `T_List` to `list_copy_deep` (recursive node-copy on every cell), but `T_IntList` / `T_OidList` / `T_XidList` to a shallow `list_copy` because their cells hold raw integers, not pointers (`copyfuncs.c:191-203`). If you accidentally store a non-`Node *` pointer in a `T_List` and copy the parent tree, copyObject will try to treat it as a Node and segfault or corrupt memory. Use the right list flavor or wrap your scalar in a value-node (`Integer`, `String`, …) from `src/include/nodes/value.h`.

### 5. Stack-depth guard

`copyObjectImpl` calls `check_stack_depth()` at the top (`:185`). On deeply-nested expression trees (`x OR x OR x OR …` to thousands of levels) it will `ereport(ERROR)` with stack-too-deep rather than crashing. Good for safety but means `copyObject` is **not** safe in critical sections / spinlock regions / signal handlers — any path that can throw is forbidden there.

### 6. Memory context

The copy is allocated in `CurrentMemoryContext`. If you want the duplicate to outlive the current context, do an explicit `MemoryContextSwitchTo(longer_lived_cxt)` before the `copyObject` call. (See `knowledge/idioms/memory-contexts.md` for the broader pattern.)

### 7. The roundtrip contract

`copyObject(stringToNode(nodeToString(p)))` is load-bearing — plan caching, rule storage, parallel-worker plan shipping all depend on it. If you add a node type and forget to keep the copy/out/read funcs in sync (e.g. you `pg_node_attr(no_read)` but the node ends up in a stored tree), you silently corrupt plans. (`knowledge/idioms/node-types-and-lists.md:58-69`.)

## Summary

For 95% of cases:

```c
Foo *dup = copyObject(orig);
```

…is correct, allocates in the current context, recurses through every `Node *` field, and handles lists / strings / bitmapsets without you thinking about it. The gotchas above only bite when you (a) add new node types with by-ref or extensible content, (b) misuse list flavors, (c) need to call from a no-throw region, or (d) work on deeply pathological trees.
