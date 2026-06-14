---
path: src/interfaces/ecpg/pgtypeslib/pgtypeslib_extern.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 45
depth: read
---

# `pgtypeslib_extern.h` — internal (non-installed) header for pgtypeslib helpers

## Purpose
Tiny private header shared inside the ECPG `pgtypeslib` runtime. It pulls in
`pgtypes_error.h` (the `PGTYPES_*` error codes), defines the `PGTYPES_TYPE_*`
format-selector constants and the `PGTYPES_FMT_NUM_MAX_DIGITS` scratch-buffer
size used by `pgtypes_fmt_replace`, declares the `union un_fmt_comb` discriminated
value, and prototypes the three internal helpers (`pgtypes_fmt_replace`,
`pgtypes_alloc`, `pgtypes_strdup`). It is **not** part of the installed public
ECPG API — the public surface lives in the `pgtypes_*.h` headers. `[verified-by-code]`

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `PGTYPES_TYPE_NOTHING` … `PGTYPES_TYPE_UINT_LONG` | extern.h:12-24 | format-selector tags for `pgtypes_fmt_replace`; the `replace_type` switch keys `[verified-by-code]` |
| `PGTYPES_FMT_NUM_MAX_DIGITS` (40) | extern.h:26 | scratch buffer size for numeric formatting in common.c `[verified-by-code]` |
| `union un_fmt_comb` | extern.h:28-36 | members: `str_val`, `uint_val`, `char_val`, `luint_val`, `double_val`, `int64_val` |
| `pgtypes_fmt_replace` | extern.h:38 | prototype; impl in [[common.c]] |
| `pgtypes_alloc` | extern.h:42 | prototype; zero-filling alloc, impl in [[common.c]] |
| `pgtypes_strdup` | extern.h:43 | prototype; impl in [[common.c]] |

## Invariants & gotchas
- The `PGTYPES_TYPE_*` constants and the `union un_fmt_comb` member set must stay
  in lock-step with the switch in `pgtypes_fmt_replace` (common.c:37). Adding a
  selector here without a matching case there falls through to the `default`
  no-op. `[inferred]`
- `PGTYPES_TYPE_UINT_LONG` (extern.h:24) is defined but, at this anchor, has **no
  corresponding case** in `pgtypes_fmt_replace` (common.c) and the `luint_val`
  union member is likewise unused there — dead/aspirational entries. `[verified-by-code]`
- Internal header: guarded by `_ECPG_PGTYPESLIB_EXTERN_H`; must not be exposed to
  client code (no `PGTYPES`-prefixed public symbols declared here). `[verified-by-code]`

## Cross-refs
- [[common.c]] — the sole implementer of all three prototyped helpers and the
  consumer of every `PGTYPES_TYPE_*` / `un_fmt_comb` member.
- [[dt.h]] — sibling internal header (date/time macro side).
- [[pgtypes_error.h]] — `PGTYPES_*` error codes pulled in at extern.h:6.

## Potential issues
`PGTYPES_TYPE_UINT_LONG` / `luint_val` are declared but unreferenced by the
format-replace switch at this anchor (a benign loose end, flagged below).
