# Portable identifiers — names that break macOS clang or Windows

PostgreSQL builds on a wide compiler/OS matrix. Two compiler frontends
reserve identifiers that look perfectly innocent in plain C:

- **Apple clang in Objective-C / Objective-C++ mode** reserves a small set
  of Objective-C keywords. PG itself is C, but extension modules and a few
  PG header consumers (e.g. macOS-side bgworker shims, ECPG-generated code
  compiled into ObjC++ apps) hit this. Field names like `id`, `Class`,
  `SEL`, `BOOL`, `typeid`, `nil` will fail to compile when the header is
  included from an `.mm` file.
- **Windows `<windows.h>` / `winnt.h`** brings in a flood of `#define`s
  and typedefs for the Win32 ABI. Field names like `BOOL`, `BYTE`,
  `WORD`, `DWORD`, `HANDLE`, `IN`, `OUT`, `OPTIONAL` get macro-replaced
  by token soup before the C compiler even sees them.

PG headers must use field names that survive both. Existing PG nodes have
already done the work of choosing safe names; the right move when adding
a new field is to follow the existing precedent rather than re-discover
the conflict from a CI failure on a different OS.

Origin: sesvars Phase 3 (2026-06-17) lost ~30 min when a new Expr field
called `typeid` failed to compile on macOS. Renamed to `vartype` — fine
everywhere. The 30 min would have been zero if `git grep typeid
src/include/nodes/` had been run before naming the field.

Anchors:
- `source/src/include/nodes/primnodes.h:391-405` — `Param` node, the
  canonical precedent for "I want a type OID field on an Expr node"
- `source/src/include/c.h:589-602` — PG's bool handling, deliberately
  via `<stdbool.h>` so it doesn't fight Win32 `BOOL`
- `source/src/include/port/win32_port.h` — the Windows porting shim

## Objective-C reserved words (macOS clang)

The full list of identifiers clang treats as keywords when compiling
Objective-C / Objective-C++:

| Identifier | Role in ObjC |
|---|---|
| `id` | generic object pointer type |
| `Class` | class object type |
| `SEL` | selector type |
| `IMP` | method-implementation pointer |
| `BOOL` | ObjC boolean (signed char) |
| `nil` | nil object literal |
| `Nil` | nil class literal |
| `YES` | true literal |
| `NO` | false literal |
| `self` | current object pointer |
| `super` | superclass invocation marker |
| `_cmd` | current selector inside method body |
| `IBAction` | Interface Builder action marker |
| `IBOutlet` | Interface Builder outlet marker |
| `typeid` | C++ RTTI keyword (ObjC++ inherits) |

`typeid` is C++ (RTTI), not strictly ObjC — but ObjC++ inherits the C++
keyword set, so a header that's safe for plain ObjC can still break in
ObjC++. PG cares about ObjC++ because it's a common embedding mode for
macOS GUI apps that link to libpq.

[unverified] — this list is the union of Apple's docs and what's been
seen in PG CI; there is no canonical PG-side enumeration. Treat it as
"likely full" but spot-check against an Apple reference when adding a
field with a borderline name.

## Windows `winnt.h` reserved words

A subset of the Win32 symbols that have bitten PG or its extensions:

| Identifier | Win32 role |
|---|---|
| `BOOL` | typedef int |
| `BYTE` | typedef unsigned char |
| `WORD` | typedef unsigned short |
| `DWORD` | typedef unsigned long |
| `HANDLE` | typedef void * |
| `FAR` | legacy far-pointer macro (now empty) |
| `NEAR` | legacy near-pointer macro (now empty) |
| `IN` | macro for parameter-direction annotation |
| `OUT` | macro for parameter-direction annotation |
| `OPTIONAL` | macro for parameter-direction annotation |

`IN` / `OUT` / `OPTIONAL` are particularly nasty because they're `#define`
to nothing — a struct field named `IN` literally disappears at preprocess
time, with a cryptic syntax error as the only signal.

[unverified] for the exact enumeration; the authoritative source is
Microsoft's `winnt.h`. The PG porting shim
`src/include/port/win32_port.h` plus `src/include/port/win32.h` paper
over many of these conflicts at the C level, but a PG-defined struct
field still has to dodge them.

## Precedent renames in PG

When PG wants "a type OID on an expression node", the canonical field
names are:

- `paramtype` on `Param` (not `typeid`)
  [verified-by-code `source/src/include/nodes/primnodes.h:398`]
- `paramtypmod` on `Param` (not `typmod`)
  [verified-by-code `source/src/include/nodes/primnodes.h:400`]
- `paramcollid` on `Param` (not `collid`)
  [verified-by-code `source/src/include/nodes/primnodes.h:402`]
- `paramkind` on `Param` (not `kind`)
  [verified-by-code `source/src/include/nodes/primnodes.h:396`]
- `array_typeid` / `element_typeid` on `ArrayExpr` (qualified, not bare
  `typeid`) [verified-by-code `source/src/include/nodes/primnodes.h:1409,
  1413`]
- `row_typeid` on `RowExpr` (qualified)
  [verified-by-code `source/src/include/nodes/primnodes.h:1453`]
- `consttype`, `consttypmod`, `constcollid` on `Const` (qualified with
  the node name as prefix)
  [verified-by-code `source/src/include/nodes/primnodes.h`]

The pattern is clear: **prefix the field with the node-name root**.
`Param` has `paramtype`/`paramid`/`paramkind`; `Const` has `consttype`;
`ArrayExpr` qualifies further with `element_*` / `array_*`. Bare `type`,
`id`, `kind` are avoided everywhere on Expr-flavored nodes.

PG's `bool` deliberately comes from `<stdbool.h>` (not a typedef in
`c.h`) so it doesn't fight Win32 `BOOL` at typedef-redefinition time
[verified-by-code `source/src/include/c.h:589-602`].

## When this triggers

A new typedef field gets added to a node struct that is `#include`d (a)
into ECPG, (b) by extensions on macOS, (c) by anything that pulls
`<windows.h>` first on MSVC builds. Specifically:

- `src/include/nodes/primnodes.h` — pulled into the world; any field
  here must be portable.
- `src/include/nodes/parsenodes.h` — same.
- `src/include/nodes/parsenodes.h` siblings for utility statements —
  same, though slightly less consumed.
- New backend-only structs in `src/include/<subsystem>/*.h` that no
  extension is expected to include — lower risk, but still pulled in by
  ECPG preprocessor in some configurations.

CI catches the failures, but the round-trip is ≥ 20 min on a green box
and longer when you have to debug. Catching at field-naming time is
free.

## How to avoid

Three cheap steps before naming a new field on a node struct:

1. **Grep the proposed name across the whole tree.**

   ```bash
   git -C source grep -n 'typeid\|\bid\b\|\bClass\b' src/include/nodes/
   ```

   If existing code uses the bare form, the name is safe. If existing
   code prefixes it (`paramtype`, `consttype`, etc.), follow suit.

2. **Look at the sibling fields on the same node and on parallel
   nodes.** If `Param` has `paramtype`, your new Param-like node should
   have `<yourprefix>type`. Don't invent.

3. **For names that look ObjC-ish or Win32-ish, prefer the qualified
   form by default.** "Free" verbosity now saves a CI cycle later.

The reverse direction (renaming an existing PG field because of a new
collision) is much more expensive: every walker, every `_outNode` /
`_readNode` / `_copyNode` / `_equalNode` / `_jumbleNode` generated stub
references the field by name via macros from `gen_node_support.pl`, and
extensions on PGXN reference it too. Get the name right at birth.

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/include/c.h`](../files/src/include/c.h.md) | 589 | PG's bool handling, deliberately via <stdbool.h> so it doesn't fight Win32 BOOL |
| [`src/include/c.h`](../files/src/include/c.h.md) | — | bool definition and the comment block explaining why PG uses <stdbool.h> |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 391 | Param node, the canonical precedent for "I want a type OID field on an Expr node" |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 396 | paramkind on Param (not kind) [verified-by-code ] |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 398 | paramtype on Param (not typeid) [verified-by-code ] |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 400 | paramtypmod on Param (not typmod) [verified-by-code ] |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 402 | paramcollid on Param (not collid) [verified-by-code ] |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 1409 | array_typeid / element_typeid on ArrayExpr (qualified, not bare typeid) [verified-by-code , 1413] |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 1453 | row_typeid on RowExpr (qualified) [verified-by-code ] |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | — | consttype, consttypmod, constcollid on Const (qualified with the node name as prefix) [verified-by-code ] |
| [`src/include/port/win32_port.h`](../files/src/include/port/win32_port.md) | — | Windows porting shim |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-node-type`](../scenarios/add-new-node-type.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/node-types.md` — what shape the new struct should
  have (parse-tree vs Expr-flavored) before you start naming fields.
- `knowledge/idioms/node-types-and-lists.md` — the NodeTag / List
  machinery the field will participate in.
- `knowledge/idioms/catalog-conventions.md` — naming conventions for
  catalog columns (similar discipline, different namespace).
- `source/src/include/port/win32_port.h` — Windows porting shim.
- `source/src/include/c.h` — `bool` definition and the comment block
  explaining why PG uses `<stdbool.h>`.

## Open questions / unverified

- Whether clang in plain Objective-C (not ObjC++) reserves `typeid`
  [unverified]. PG's experience is via ObjC++ embedding, where the C++
  keyword set applies regardless.
- The exact set of `<windows.h>` macros that change between SDK
  versions [unverified]. Treat the table above as a known-bad floor,
  not a complete list.
