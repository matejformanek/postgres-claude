---
path: src/interfaces/ecpg/preproc/type.c
anchor_sha: 02f699c14163
loc: 730
depth: deep
---

**Last verified commit:** `02f699c14163` — re-verified + re-pinned 2026-06-30 by pg-quality-auditor AUDIT mode after anchor-bump `4abf411e2328..02f699c14163` (triggering commit: 7f5e0b22e5ea "Fix null-pointer crash in ECPG compiler", Tom Lane). Prior pin `e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa`.

# `type.c` — ECPG preprocessor host-variable type model and C-code emitter

## Purpose
This file is the ECPG preprocessor's type subsystem. It builds and duplicates the
in-memory representation of host-variable C types (`struct ECPGtype` and its
member lists `struct ECPGstruct_member`), and — its larger half — emits the C
source that the generated program passes to the ecpglib runtime to describe each
host variable. The `ECPGdump_a_*` family walks a type tree and prints, per leaf,
a fixed 5-field tuple (type-tag, variable reference, varchar/size, array size,
offset-to-next-element) that ecpglib's variadic argument parser consumes at
runtime. It also holds the enum→string translators `get_type`/`get_dtype` that
turn `ECPGttype`/`ECPGdtype` codes into their literal `ECPGt_*`/`ECPGd_*`
identifiers in the output, plus the matching type-tree teardown
(`ECPGfree_type`/`ECPGfree_struct_member`).

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `ECPGstruct_member_dup` | `type.c:13` | Deep-copies a member list; recurses into nested struct/union/array members `[verified-by-code]` `type.c:22-47` |
| `ECPGmake_struct_member` | `type.c:53` | Appends a `{name(copied), type(pointer kept)}` node to the end of `*start`; name is `mm_strdup`'d, type stored by pointer `[from-comment]` `type.c:51`, `type.c:60-69` |
| `ECPGmake_simple_type` | `type.c:72` | Allocates a leaf `ECPGtype`; `counter` only meaningful for varchar/bytea `[from-comment]` `type.c:81` |
| `ECPGmake_array_type` | `type.c:87` | Wraps an element type as `ECPGt_array`, storing element in `u.element` `[verified-by-code]` `type.c:89-91` |
| `ECPGmake_struct_type` | `type.c:97` | Builds `ECPGt_struct`/`ECPGt_union` node; dups member list, records `type_name` and `struct_sizeof` `[verified-by-code]` `type.c:100-104` |
| `ECPGdump_a_type` | `type.c:219` | Top-level type dumper; does hidden-variable shadowing checks then dispatches on `type->type` (array/struct/union/char_variable/descriptor/default) `[verified-by-code]` `type.c:227-382` |
| `ECPGfree_struct_member` | `type.c:621` | Walks and frees a member list, freeing each `name` and recursing via `ECPGfree_type` `[verified-by-code]` `type.c:623-631` |
| `ECPGfree_type` | `type.c:635` | Recursive type-tree teardown; frees `type_name`, `size`, `struct_sizeof`, then the node `[verified-by-code]` `type.c:637-671` |
| `get_dtype` | `type.c:675` | Translates `ECPGdtype` (descriptor item code) to its `ECPGd_*` string; used by descriptor.c emit paths `[verified-by-code]` `type.c:677-727` |

`ECPGdump_a_type` is the only `ECPGdump_a_*` symbol with external linkage; the
two recursive helpers (`ECPGdump_a_simple`, `ECPGdump_a_struct`) are `static`
(forward-declared at `type.c:212-216`).
<!-- def-line cites in this doc shifted +1 vs prior pin: 7f5e0b22e5ea added one
line inside ECPGstruct_member_dup's ECPGt_array arm (null-pointer crash fix);
only symbol-def lines and the dup/make_struct_member bodies moved, interior cites
from type.c:51 onward are unchanged. -->

## Internal landmarks
- **The output-format contract** — the block comment at `type.c:198-211`
  documents the 5-field tuple every leaf emits: `type-tag, reference, size,
  arrsize, offset`. This is the wire contract with ecpglib's variadic reader.
- **`ECPGdump_a_simple`** `type.c:391` — the leaf emitter. Three early-out tags
  (`ECPGt_NO_INDICATOR` `type.c:398`, `ECPGt_descriptor` `type.c:402`,
  `ECPGt_sqlda` `type.c:404`) print canned tuples; everything else builds a
  `variable` reference string and an `offset` (sizeof) string in a big `switch`
  on type `type.c:411-535`. The pointer-vs-`&` decision for char/varchar/bytea/
  default hinges on `arrsize`/`varcharsize` being a positive (or non-"0")
  literal and `size == NULL` `type.c:425-431`, `type.c:457-475`, `type.c:526-531`.
- **`ECPGdump_a_struct`** `type.c:561` — "penetrate a struct and dump the
  contents." Chooses `.` vs `->` member access by `atoi(arrsize) == 1`
  `type.c:572-575`; builds parallel prefixes for the data struct and the
  indicator struct, then loops members calling `ECPGdump_a_type` at brace level
  `-1` `type.c:592-609`. Member-count mismatch between data and indicator structs
  is reported (too few `type.c:605-607`, too many `type.c:611-613`).
- **`get_type`** `type.c:110` — enum→string for `ECPGttype`; default arm raises
  `unrecognized variable type code` `type.c:191`.
- **`struct_no_indicator`** `type.c:9` — file-static sentinel member used when an
  indicator struct runs short, so the data walk can continue emitting
  `ECPGt_NO_INDICATOR` leaves `type.c:579-580`, `type.c:600-607`.
- **`indicator_set` macro** `type.c:7` — shorthand for "an indicator exists and
  is not the NO_INDICATOR sentinel," gating the indicator-shape checks in
  `ECPGdump_a_type` `type.c:264`, `type.c:310`, `type.c:330`, `type.c:351`,
  `type.c:371`.

## Invariants & gotchas
- **Name copied, type aliased.** `ECPGmake_struct_member` copies `name` but
  stores `type` by pointer `[from-comment]` `type.c:51`. So a single `ECPGtype`
  can be shared; this is why `ECPGstruct_member_dup` exists and why
  `ECPGfree_type` recursion must match the dup structure exactly.
- **`arrsize` is mutated in place.** `ECPGdump_a_simple` may `strcpy(arrsize,
  "1")` when `atoi(arrsize) < 0 && !size` `type.c:541-542`. The repeated
  "Allocate for each, as there are code-paths where the values get stomped on"
  comments at `type.c:322-324`, `type.c:344-347`, `type.c:364-367` exist
  precisely because the dumper writes through its char* arguments — callers must
  pass fresh `mm_strdup` buffers, not shared literals.
- **Brace level `-1` disables shadowing checks.** `ECPGdump_a_type` only does the
  hidden-local-variable lookup when `brace_level >= 0` `type.c:229`;
  `ECPGdump_a_struct` always calls with `-1` `type.c:594,597` because struct
  members are not independent host variables.
- **Nested arrays rejected.** Array-of-array is a parse error
  (`nested arrays are not supported (except strings)` `type.c:269`); the free
  path treats it as an internal error `type.c:644-645`.
- **Bare union cannot be dumped.** `ECPGt_union` at the top level is a hard error
  `type.c:317-318` — a union must be cast to a concrete member type first.
- **`char *` array offset special case.** For an array of `char *` (varcharsize
  "0"), the offset uses `sizeof(char *)` not `sizeof(char)` `type.c:464-472`.
- **Sentinel pointer comparisons drive struct-indicator pairing.** The walk
  distinguishes `&struct_no_indicator` (don't advance) from real members (advance
  and check for underflow) by pointer identity `type.c:600-607`.

## Cross-refs
- ecpglib runtime consumers of the emitted tuples and the `ECPGt_*` tags:
  [[knowledge/files/src/interfaces/ecpg/ecpglib/execute.c.md]] (parses the
  variadic type descriptors at runtime),
  [[knowledge/files/src/interfaces/ecpg/ecpglib/data.c.md]],
  [[knowledge/files/src/interfaces/ecpg/ecpglib/descriptor.c.md]] (descriptor
  item codes from `get_dtype`),
  [[knowledge/files/src/interfaces/ecpg/ecpglib/typename.c.md]] (runtime
  `ecpg_type_name`; preproc-side `ecpg_type_name` used at `type.c:533`).
- Sibling preproc files: `preproc_extern.h` (declares these symbols, plus
  `mm_alloc`/`mm_strdup`/`mmerror`/`mmfatal`/`find_variable`/`base_yyerror`,
  included at `type.c:5`); `variable.c` (defines `find_variable` and the
  `struct variable` used in shadowing checks `type.c:225,234`); `type.h`
  (defines `struct ECPGtype`, `struct ECPGstruct_member`, `enum ECPGttype`,
  `IS_SIMPLE_TYPE`, `ecpg_no_indicator`).

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-overflow: `atoi`-based array-size sniffing silently misreads large or
  expression sizes]** `type.c:425-426`, `type.c:457-460`, `type.c:526-527` —
  the pointer-vs-`&` decision relies on `atoi(arrsize)`/`atoi(varcharsize)`.
  Any non-numeric size expression (a macro or `sizeof(...)`) yields `atoi == 0`,
  and the `strcmp(..., "0") != 0` guard is the only fallback. This is a known,
  long-standing heuristic rather than a fresh bug, but it is a fragile,
  undocumented invariant: sizes that are C expressions rather than integer
  literals are classified purely by whether their text equals `"0"`. `[inferred]`
- **[ISSUE-leak: minor static-string clarity, not an actual leak]** `type.c:451`,
  `type.c:471` — `sizeof_name`/`struct_name` are assigned string literals and
  never freed (correct), but `struct_name` at `type.c:409` is declared without
  initializer and only set inside the varchar/bytea arm; it is used only in that
  same arm, so no use-before-set occurs. No defect — noted to preempt a false
  positive on review. `[verified-by-code]`
- **[ISSUE-doc-drift: `get_type`/`get_dtype` inconsistent `break` after `return`]**
  `type.c:153-156`, `type.c:163-165`, `type.c:712-714`, `type.c:723-724` — most
  arms have a dead `break;` after `return`, but `ECPGt_varchar`, `ECPGt_bytea`,
  `ECPGd_ret_length`, `ECPGd_cardinality` omit it. Harmless (unreachable either
  way) but the inconsistency is pure noise that a `-Wunreachable-code` pass would
  flag. `[verified-by-code]`
