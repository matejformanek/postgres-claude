---
path: src/interfaces/ecpg/preproc/type.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 236
depth: read
---

# `type.h` — ECPG preprocessor's type-representation and grammar-symbol struct zoo

## Purpose
This header is the shared internal type vocabulary of the ECPG preprocessor
(`ecpg`), the tool that translates embedded-SQL C (`.pgc`) into plain C. It
defines the recursive `struct ECPGtype` that models a C/host-variable type
(simple, array, struct/union) plus its `ECPGstruct_member` member-list, and the
prototypes of the `ECPGmake_*` constructors / `ECPGfree_*` destructors /
`ECPGdump_a_type` emitter that build and serialize those types `[verified-by-code type.h:9-66]`.
Beyond the type model, it is the catch-all home for ~20 small grammar-symbol
helper structs used throughout the bison grammar and supporting `.c` files
(cursors, prepared statements, `WHENEVER` actions, `-D` define list, variable
list, descriptors, etc.) `[verified-by-code type.h:78-234]`. Note the prompt's
"~190 LOC / only the ECPGtype structs" framing undercounts: the file is 236
lines and most of it is the grammar-symbol structs, not the type model.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `struct ECPGtype` (fwd decl) | `type.h:9` | Forward decl so `ECPGstruct_member` can point at it before full def |
| `struct ECPGstruct_member` | `type.h:10-15` | `{name, type, next}` — singly-linked member list for struct/union types |
| `struct ECPGtype` | `type.h:17-33` | Core recursive type node; see Internal landmarks for layout |
| `ECPGmake_struct_member()` | `type.h:36-37` | Appends a member onto a `**start` list head `[from-comment type.h:35: "Everything is malloced."]` |
| `ECPGmake_simple_type()` | `type.h:38` | Constructs a simple/varchar type from an `ECPGttype` + size string + counter |
| `ECPGmake_array_type()` | `type.h:39` | Wraps an element type as an array of given size |
| `ECPGmake_struct_type()` | `type.h:40-43` | Builds a struct/union type from a member list `rm` |
| `ECPGstruct_member_dup()` | `type.h:44` | Deep-copies a member list |
| `ECPGfree_struct_member()` | `type.h:47` | Frees a member list |
| `ECPGfree_type()` | `type.h:48` | Frees a type tree |
| `ECPGdump_a_type()` | `type.h:61-66` | Emits the C runtime arg tuple (type-tag, ref, arrsize, size, …); contract in comment `type.h:50-60` |
| `struct ECPGtemp_type` | `type.h:69-73` | Lightweight `{type, name}` pair |
| `ecpg_type_name()` | `type.h:75` | `extern`; maps an `ECPGttype` to its name string |
| `enum WHEN_TYPE` | `type.h:78-87` | `WHENEVER` action codes (see landmarks) |
| `struct when` | `type.h:89-94` | A `WHENEVER` handler `{code, command, str}` |
| `struct index` | `type.h:96-101` | Array index pair `{index1, index2, str}` |
| `struct su_symbol` | `type.h:103-107` | struct/union symbol `{su, symbol}` |
| `struct prep` | `type.h:109-114` | `PREPARE` info `{name, stmt, type}` |
| `struct exec` | `type.h:116-120` | `EXECUTE` info `{name, type}` |
| `struct this_type` | `type.h:122-130` | Parser's working type record (storage, enum, str, dimension, index, sizeof) |
| `struct _include_path` | `type.h:132-136` | `-I` include-path list node |
| `struct cursor` | `type.h:138-150` | Declared cursor; carries 4 `arguments` lists (insert/result, in/out-of-scope) + `opened` flag |
| `struct declared_list` | `type.h:152-157` | `DECLARE STATEMENT` list node |
| `struct typedefs` | `type.h:159-166` | A typedef entry `{name, type, struct_member_list, brace_level, next}` |
| `struct _defines` | `type.h:180-187` | Macro define-list node; see Invariants for the `cmdvalue`/`used` semantics |
| `struct variable` | `type.h:190-196` | Host-variable list node `{name, type, brace_level, next}` |
| `struct arguments` | `type.h:198-203` | `{variable, indicator, next}` — host var + its indicator |
| `struct descriptor` | `type.h:205-210` | SQL descriptor `{name, connection, next}` |
| `struct assignment` | `type.h:212-217` | `SET DESCRIPTOR` assignment `{variable, value:ECPGdtype, next}` |
| `enum errortype` | `type.h:219-222` | `{ET_WARNING, ET_ERROR}` |
| `struct fetch_desc` | `type.h:224-227` | `FETCH` descriptor `{str, name}` |
| `struct describe` | `type.h:230-233` | `DESCRIBE` info `{input, stmt_name}` |

## Internal landmarks
- `struct ECPGtype` layout `[verified-by-code type.h:17-33]`: tagged by
  `enum ECPGttype type` (the discriminant), with overloaded string fields whose
  meaning depends on the tag — `size` is element count for arrays but maxsize
  for varchar `[from-comment type.h:22-23]`; `struct_sizeof` holds the sizeof
  string for structs `[from-comment type.h:24-25]`. The `union u` is
  `element` (array element type) XOR `members` (struct member list)
  `[verified-by-code type.h:26-31]`. Trailing `int counter` `[type.h:32]`.
- `enum WHEN_TYPE` value family `[verified-by-code type.h:78-87]`:
  `W_NOTHING, W_CONTINUE, W_BREAK, W_SQLPRINT, W_GOTO, W_DO, W_STOP` — the set
  of `WHENEVER <condition> <action>` clauses ecpg supports.
- `enum errortype` `[type.h:219-222]`: `ET_WARNING`, `ET_ERROR`.
- The `ECPGttype` and `ECPGdtype` enums referenced throughout are NOT defined
  here — they are pulled in via `#include "ecpgtype.h"` `[verified-by-code type.h:7]`.
  `ECPGttype` is used at `type.h:19,36,38,41,75,125`; `ECPGdtype` at `type.h:215`.

## Invariants & gotchas
- `[from-comment type.h:35]` "Everything is malloced." — all `ECPGmake_*`
  output and the structs hung off it are heap-allocated; pair every make with
  the corresponding `ECPGfree_*` (`type.h:46-48`).
- `struct ECPGtype` is a tagged union: reading `u.element` vs `u.members` is
  only valid per the `type` discriminant `[verified-by-code type.h:18,26-31]`.
  Treating a struct type's `u` as `element` (or vice versa) is undefined.
- The string fields (`size`, `struct_sizeof`) are overloaded by type tag
  `[from-comment type.h:20-25]`; their interpretation is not self-describing
  from the field alone — callers must branch on `type`.
- `struct _defines` ordering/ownership rules `[from-comment type.h:168-179]`:
  `name`/`value` are separately-malloc'd; `cmdvalue` typically is NOT malloc'd
  (it points at command-line storage), and is kept separate so multi-file runs
  can revert define state to the command-line baseline. `used` is NULL except
  while expanding the macro, where it points at the prior scan buffer to block
  recursive expansion — and must be reset to NULL on return.
- `ECPGdump_a_type`'s emitted tuple order is contract, documented at
  `type.h:50-60`: `type-tag, reference-to-variable, arrsize, size, …`; the
  consumer ecpglib runtime depends on this argument order.
- Member-list and most list structs use a forward `next` pointer and are built
  head-first (`**start` in `ECPGmake_struct_member` `[type.h:36-37]`).

## Cross-refs
- [[src/interfaces/ecpg/preproc/type.c]] — the consumer/implementer of the
  `ECPGmake_*` / `ECPGfree_*` / `ECPGdump_a_type` prototypes declared here.
- [[src/interfaces/ecpg/preproc/variable.c]] — builds `struct variable` /
  `struct arguments` lists and walks `ECPGtype` trees.
- [[src/interfaces/ecpg/ecpglib/...]] — runtime that consumes the `ECPGt_*`
  argument tuples emitted by `ECPGdump_a_type`; the `ECPGttype`/`ECPGdtype`
  enums it shares come from `ecpgtype.h`.
- `src/interfaces/ecpg/preproc/ecpgtype.h` — defines `enum ECPGttype` and
  `enum ECPGdtype` included at `type.h:7`.
- The bison grammar (`preproc.y` / `ecpg.trailer` / `ecpg.header`) — primary
  user of the grammar-symbol structs (`cursor`, `prep`, `when`, `this_type`, …).

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
No correctness defects. One conservative maintainability note:

- **[ISSUE-cohesion: header mixes two unrelated concerns]** `type.h:78-234` —
  the file's name and top half are the `ECPGtype` type model, but the bottom
  ~155 lines are an unrelated grab-bag of grammar-symbol structs (cursors,
  defines, descriptors, WHENEVER, etc.) with no module boundary. This is a
  long-standing ecpg layout choice, not a bug, but the filename undersells the
  scope and any consumer pulling `type.h` for the type model also drags in the
  whole grammar struct set.
