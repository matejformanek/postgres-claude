---
path: src/interfaces/ecpg/preproc/variable.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 712
depth: deep
---

# `variable.c` — ECPG preprocessor host-variable & typedef symbol tables

## Purpose
This file is the ECPG preprocessor's symbol-table layer for C host variables.
It maintains the global linked list of declared host variables
(`allvariables`), resolves an embedded `:hostvar` reference string (including
`.field`, `->field`, and `[subscript]` decoration) to a `struct variable` with
a correctly attached `ECPGtype` (`new_variable` / `find_variable` and the
`find_struct*` helpers), tears variables and typedefs down by C brace level on
scope exit (`remove_variables` / `remove_typedefs`), manages the per-statement
input/output argument lists that drive code generation (`argsinsert` /
`argsresult`, `add_variable_to_*`, `dump_variables`), and provides assorted
type/typedef utilities (`get_typedef`, `check_indicator`, `adjust_array`)
`[verified-by-code]` variable.c:1-712.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `new_variable` | variable.c:22 | Alloc a `struct variable`, `mm_strdup` the name, push onto `allvariables` head. |
| `find_variable` | variable.c:234 | Top-level resolver for a CVARIABLE string; dispatches to `find_simple`/`find_struct`; `mmfatal` if undeclared (variable.c:311). |
| `remove_typedefs` | variable.c:316 | Free all `types` entries with `brace_level >= brace_level` on scope exit. |
| `remove_variables` | variable.c:350 | Free all `allvariables` entries at/above `brace_level`; first unlinks them from every cursor's arg lists (variable.c:362-403). |
| `argsinsert` / `argsresult` | variable.c:427-428 | Global per-request input/output argument lists. |
| `reset_variables` | variable.c:430 | Free + null both `argsinsert` and `argsresult`. |
| `add_variable_to_head` | variable.c:455 | Prepend `{var,ind}` arg (list dumped from the end). |
| `add_variable_to_tail` | variable.c:467 | Append `{var,ind}` arg via O(n) walk. |
| `remove_variable_from_list` | variable.c:485 | Unlink first arg matching `var`, free it. |
| `dump_variables` | variable.c:516 | Recurse to list end then `ECPGdump_a_type` each elem; frees elems when `mode != 0`. |
| `check_indicator` | variable.c:545 | Validate an indicator's `ECPGtype` is integer (recurses struct/union/array). |
| `get_typedef` | variable.c:578 | Lookup in `types`; `mmfatal` unless `noerror`. |
| `adjust_array` | variable.c:595 | Normalize dimension/length for arrays, pointers, varchar/bytea/char, structs. |

## Internal landmarks
- `allvariables` — file-static head of the host-variable list, variable.c:7;
  pushed at head in `new_variable` variable.c:31-32, walked linearly in
  `find_simple` variable.c:211-215 `[verified-by-code]`.
- `loc_nstrdup` — static helper that `loc_alloc`s a NUL-terminated copy of a
  substring; comment says it "probably belongs in util.c" variable.c:9-20
  `[from-comment]`. Used to carve out base-name/field prefixes (e.g.
  variable.c:58, 167, 282).
- Field/struct resolution: `find_variable` (variable.c:234) detects the first
  of `.[-` via `strpbrk` (variable.c:242), scans matching `]` for subscripts
  (variable.c:252-268), and routes to `find_struct` (variable.c:160) or the
  inline `var[n]` case (variable.c:282-298). `find_struct_member`
  (variable.c:48) recurses for sub-fields, re-scanning brackets at each level
  (variable.c:90-103).
- Scope/brace-level handling: both `remove_typedefs` and `remove_variables`
  use the `>= brace_level` test to drop entries when a C block closes
  (variable.c:326, 360). `brace_level` is stamped at creation in `new_variable`
  (variable.c:29) and propagated through struct-member lookups (e.g.
  variable.c:179, 189, 200).
- Cursor cross-cleanup: `remove_variables` walks the global `cur` cursor list
  and prunes any `argsinsert`/`argsresult` entries whose `->variable` is being
  freed (variable.c:365-403), preventing dangling pointers from outliving the
  variable `[verified-by-code]`.
- `dump_variables` is the codegen sink: tail-recurses so output order matches
  source order (list built at head), then calls `ECPGdump_a_type`
  (variable.c:531-536); deletes-as-it-goes when `mode != 0` (variable.c:539-540).

## Invariants & gotchas
- **Two allocator families.** `new_variable`/`add_variable_to_*` use
  `mm_alloc`/`mm_strdup` (variable.c:25-27, 458, 471); `loc_nstrdup` uses
  `loc_alloc` (variable.c:15). The `remove_*` paths call plain `free` /
  `ECPGfree_type` (variable.c:411-413, 336-343). `loc_alloc`'d prefixes
  (e.g. variable.c:167, 282) are intentionally never freed — they live in the
  preprocessor's location-arena and are reclaimed in bulk `[inferred]`.
- **`mmfatal` ends the program.** `find_variable` and friends terminate on a
  malformed/undeclared reference (variable.c:113, 139, 174, 286, 311), so
  callers may assume a non-NULL result. The function header documents this
  (variable.c:232) `[from-comment]`.
- **`var[n]->field` is unsupported by design.** The comment at variable.c:276-280
  notes the `var[n]` branch assumes no further decoration; pointer-to-pointer
  vars are rejected elsewhere (`adjust_array`, variable.c:620-626) `[from-comment]`.
- **No multidimensional arrays / >2-level pointers.** `adjust_array` hard-fails
  these (variable.c:604, 612, 621, 629, 632, 646, 708) `[verified-by-code]`.
- `find_struct` dereferences `p` from `find_variable` without a NULL check
  (variable.c:168-173) — safe only because `find_variable` `mmfatal`s rather
  than returning NULL `[inferred]`.

## Cross-refs
- [[type.c]] — `ECPGmake_simple_type`, `ECPGmake_array_type`,
  `ECPGmake_struct_type`, `ECPGfree_type`, `ECPGfree_struct_member` are all
  consumed here (variable.c:72-77, 411, 335).
- [[ecpg-dump]] / `type.c` — `ECPGdump_a_type` is the codegen call in
  `dump_variables` (variable.c:534).
- [[preproc_extern.h]] — declares these functions plus the globals `types`,
  `cur`, `base_yyout` referenced here (variable.c:5).
- [[pgc.l]] / scanner — produces the CVARIABLE strings `find_variable` parses
  (header comment, variable.c:222-224).
- [[ecpg.addons]] / `gram` actions — primary callers of `find_variable`,
  `add_variable_to_*`, `dump_variables`, `reset_variables`.
- `util.c` — intended future home of `loc_nstrdup` (variable.c:9).

## Potential issues
- **[ISSUE-undocumented-invariant: find_struct_member bracket scan can run off
  the end on malformed input]** `variable.c:90` — the bracket-matching loop
  `for (count = 1, end = next + 1; count; end++)` has no `'\0'` guard, unlike
  the equivalent loop in `find_variable` which checks `case '\0'`
  (variable.c:262-264). A struct-member reference with an unmatched `[` would
  read past the string terminator here. Severity: low (input is a scanner-
  validated CVARIABLE, and the matching `find_variable` path already rejects
  unmatched brackets before recursion is reached), but the asymmetry is a real
  latent footgun. `[inferred]`
- **[ISSUE-stale-comment: loc_nstrdup "probably belongs in util.c"]**
  `variable.c:9` — long-standing TODO-flavored comment; the helper is still
  only used in this file. Cosmetic. `[from-comment]`
