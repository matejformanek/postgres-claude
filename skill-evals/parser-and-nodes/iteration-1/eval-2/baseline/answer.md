# Deep-copying a Node tree — baseline

Use `copyObject(node)`. It returns a deep copy.

```c
Node *dup = (Node *) copyObject(expr);
```

(In modern PG versions there's a macro that preserves the argument type via `typeof_unqual`, so `Foo *dup = copyObject(orig)` works without a cast.)

## What it does

`copyObject` is implemented in `src/backend/nodes/copyfuncs.c`. Most of the per-node `_copyFoo` functions are auto-generated from the struct definitions in the parsenodes.h / primnodes.h / plannodes.h headers by a Perl script (`gen_node_support.pl`). It walks the struct field by field — scalar fields are copied directly, pointer-to-Node fields recurse, strings are `pstrdup`'d, lists are deep-copied.

## Gotchas

- **By-ref Datums**: `Const` nodes hold a `Datum` that might be by-reference. The copy logic uses `datumCopy` to deep-copy those — handled by a hand-written `_copyConst`.
- **Extensible nodes**: custom-scan / FDW nodes registered via the extensible-node mechanism have their own copy callback — make sure your extension registers it.
- **Memory context**: the copy is allocated in the current memory context. Switch to a longer-lived context if you need the copy to outlive the current one.
- **Stack depth**: deeply nested trees can blow the stack — though `copyObject` should call `check_stack_depth()` to ereport instead of crashing.
- **List types**: there are multiple list flavors (`T_List`, `T_IntList`, `T_OidList`). The deep-copy treats `T_List` cells as Node pointers and recurses; integer lists are copied shallowly. If you cram a non-Node pointer into a `T_List` it'll segfault during copy.
- **Roundtrip with serialization**: if you also use `nodeToString`/`stringToNode` (e.g. for storing in catalogs or shipping to parallel workers), make sure the read/write funcs match the copy funcs — otherwise you can lose fields silently.

I don't remember exact line numbers in copyfuncs.c — you'd want to look at the file to confirm specifics.
