---
path: src/include/fe_utils/simple_list.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 71
depth: read
---

# `src/include/fe_utils/simple_list.h`

- **File:** `source/src/include/fe_utils/simple_list.h` (71 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Minimal singly-linked-list facilities for frontend code that needs to accumulate OIDs,
strings, or pointers without the backend's `List` machinery (which depends on palloc/memory
contexts). Used heavily by pg_dump (e.g. `--table`/`--schema` include/exclude lists). The
header comment is explicit that the support is "very primitive compared to the backend's List
facilities, but it's all we need." Implementation in `src/fe_utils/simple_list.c`.
`[from-comment]` (:5-7)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `SimpleOidListCell` / `SimpleOidList` | :20-30 | OID list (head/tail). |
| `SimpleStringListCell` / `SimpleStringList` | :32-44 | String list; cell embeds the string as a FLEXIBLE_ARRAY_MEMBER + a `touched` flag. |
| `SimplePtrListCell` / `SimplePtrList` | :46-56 | Void-pointer list. |
| `simple_oid_list_append` / `_member` / `_destroy` | :58-60 | OID list ops. |
| `simple_string_list_append` / `_member` / `_destroy` | :62-64 | String list ops. |
| `simple_string_list_not_touched` | :66 | Return the first never-matched string (for "pattern matched nothing" warnings). |
| `simple_ptr_list_append` / `_destroy` | :68-69 | Pointer list ops. |

## Internal landmarks

- `SimpleStringListCell` stores its string **inline** via `char val[FLEXIBLE_ARRAY_MEMBER]`
  (`:37`) — one allocation per cell, no separate strdup — plus a `touched` bool (`:35`) set
  when the entry is matched by `simple_string_list_member`. `[verified-by-code]`
- `simple_string_list_not_touched` (`:66`) walks for the first cell with `touched == false`;
  pg_dump uses it to warn that a `-t`/`-n` pattern matched no objects. `[inferred]`
- OID and pointer lists keep both `head` and `tail` (`:26-30`, `:52-56`) so append is O(1). `[verified-by-code]`

## Invariants & gotchas

- These lists have **no `_member` for the pointer variant** (`:68-69`) — only append/destroy.
  Membership search is provided only where a tool needs it (OID, string). `[verified-by-code]`
- All cells are `pg_malloc`'d and freed by the matching `_destroy`; there is no per-element
  free, so callers must not hold cell pointers after `_destroy`. Frontend convention
  (`pg_malloc`/`pg_free`, no contexts). `[inferred]`

## Cross-refs

- Implementation: `src/fe_utils/simple_list.c` (covered in the A11 sweep —
  [[knowledge/files/src/fe_utils/simple_list.c]]).
- Backend analogue (for contrast): `knowledge/idioms/node-types-and-lists.md`.

## Potential issues

None — primitive, well-scoped list header; the `touched`-flag semantics are the only subtlety
and are documented.
