---
path: src/interfaces/ecpg/preproc/descriptor.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 367
depth: deep
---

# `descriptor.c` — preprocessor (compile-time) side of SQL descriptor areas

## Purpose

This is the **ECPG preprocessor** half of SQL descriptor support
(`ALLOCATE/DEALLOCATE DESCRIPTOR`, `GET/SET DESCRIPTOR`, and SQLDA).
It runs at *preprocess time* (when `ecpg` translates an embedded-SQL
`.pgc` file into C), not at runtime. Its job is twofold: (1) keep a
preprocess-time registry of named descriptors and which connection each
is bound to so the translator can warn about referencing an unknown
descriptor `[verified-by-code: descriptor.c:72-153]`; and (2) emit the
C source that, at runtime, will call into ecpglib — `ECPGget_desc_header`,
`ECPGget_desc`, `ECPGset_desc_header`, `ECPGset_desc`
`[verified-by-code: descriptor.c:160,179,212,273]`. The actual work of
those runtime calls lives in the companion file documented at
[[knowledge/files/src/interfaces/ecpg/ecpglib/descriptor.c.md]]. Mnemonic:
this file *writes the C call*, the ecpglib file *is what that call does*.
The `GET/SET DESCRIPTOR ... <item> = <var>` clauses arrive here as a
linked list of `assignment` structs built by `push_assignment`, are
consumed when an `output_*` emitter walks them, then freed via
`drop_assignments` `[verified-by-code: descriptor.c:18-42,161-169]`.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `push_assignment(var, value)` | `descriptor.c:20` | Pushes one `GET/SET DESCRIPTOR` item (`ECPGdtype` + target var name) onto the module-static `assignments` list; `mm_strdup`s the var name `[verified-by-code: descriptor.c:23-28]`. |
| `add_descriptor(name, connection)` | `descriptor.c:74` | Registers a named descriptor (only if `name[0]=='"'`, i.e. a string literal) at preprocess time, prepending to `descriptors` list `[verified-by-code: descriptor.c:79-90]`. |
| `drop_descriptor(name, connection)` | `descriptor.c:93` | Unlinks + frees a registered descriptor; warns (not errors) if not found `[verified-by-code: descriptor.c:110-121]`. |
| `lookup_descriptor(name, connection)` | `descriptor.c:124` | Finds a registered descriptor; can lazily bind a connectionless descriptor to a connection `[verified-by-code: descriptor.c:140-145]`; warns + returns NULL if absent. |
| `output_get_descr_header(desc_name)` | `descriptor.c:155` | Emits `ECPGget_desc_header(...)`; only `ECPGd_count` is a valid header item `[verified-by-code: descriptor.c:160-171]`. |
| `output_get_descr(desc_name, index)` | `descriptor.c:174` | Emits `ECPGget_desc(...)` plus a per-item `get_dtype` + `ECPGdump_a_type` dump, terminated by `ECPGd_EODT` `[verified-by-code: descriptor.c:179-204]`. |
| `output_set_descr_header(desc_name)` | `descriptor.c:207` | Emits `ECPGset_desc_header(...)`; same `ECPGd_count`-only rule as the GET header `[verified-by-code: descriptor.c:212-223]`. |
| `output_set_descr(desc_name, index)` | `descriptor.c:268` | Emits `ECPGset_desc(...)`; classifies each item into not-implemented / cannot-be-set / settable `[verified-by-code: descriptor.c:278-316]`. |
| `descriptor_variable(name, input)` | `descriptor.c:331` | Returns a fixed (non-dynamically-allocated) `struct variable` of type `ECPGt_descriptor`; at most 2 (input/output) per statement `[verified-by-code: descriptor.c:331-343]`. |
| `sqlda_variable(name)` | `descriptor.c:345` | Builds a transient `struct variable` of type `ECPGt_sqlda` via `loc_alloc` (statement-lifetime) `[verified-by-code: descriptor.c:353-366]`. |

## Internal landmarks

- **`assignments` list (module static)** — `descriptor.c:18`; the
  push/drop pair at `descriptor.c:20-42` is the GET/SET item accumulator.
- **`drop_assignments()`** — `descriptor.c:31`; frees the whole list, called
  at the end of every `output_*` emitter `[verified-by-code: descriptor.c:169,201,221,317]`.
- **`ECPGnumeric_lvalue(name)`** — `descriptor.c:44`; guards that a header
  `COUNT` target has a numeric/integer type, else `mmerror(... ET_ERROR ...)`
  "variable must have a numeric type" `[verified-by-code: descriptor.c:49-64]`.
- **`descriptors` list (module static)** — `descriptor.c:72`; the
  preprocess-time descriptor registry walked by add/drop/lookup.
- **`descriptor_item_name(itemcode)`** — `descriptor.c:226`; maps `ECPGdtype`
  enum values to their SQL spelling (`CARDINALITY`, `DATA`, `OCTET_LENGTH`,
  etc.) for use in `mmfatal` diagnostics `[verified-by-code: descriptor.c:226-266]`.
- **SET DESCRIPTOR item classification** — `descriptor.c:278-316`: three
  buckets — not-implemented (`CARDINALITY`, datetime interval code/precision,
  `PRECISION`, `SCALE`) `[verified-by-code: descriptor.c:280-287]`;
  cannot-be-set (`KEY_MEMBER`, `NAME`, `NULLABLE`, `OCTET_LENGTH`,
  `RETURNED_LENGTH`, `RETURNED_OCTET_LENGTH`) `[verified-by-code: descriptor.c:289-297]`;
  settable (`DATA`, `INDICATOR`, `LENGTH`, `TYPE`) `[verified-by-code: descriptor.c:299-311]`.
- **GET DESCRIPTOR item warnings** — `descriptor.c:185-195`: `NULLABLE`
  always warns "nullable is always 1", `KEY_MEMBER` warns "key_member is
  always 0" `[verified-by-code: descriptor.c:187-192]`.
- **`MAX_DESCRIPTOR_NAMELEN` + static `varspace[2]`** — `descriptor.c:330-339`;
  the comment at `descriptor.c:323-328` justifies skipping dynamic allocation:
  at most two descriptor variables (input + output) per statement.

## Invariants & gotchas

- **String-literal-only registration.** `add_descriptor`, `drop_descriptor`,
  and `lookup_descriptor` all early-return when `name[0] != '"'`
  `[verified-by-code: descriptor.c:79-80,99-100,129-130]`. Descriptor names
  given as host variables (not string constants) are silently *not* tracked —
  the preprocess-time existence checks simply don't apply to them. This is the
  reason the file header comment exists `[from-comment: descriptor.c:6-7]`.
- **Lookup mutates state.** `lookup_descriptor` can rewrite a registered
  descriptor's `connection` field in place when called with a connection for a
  descriptor previously registered with none `[verified-by-code: descriptor.c:140-145]`.
  A read-named "lookup" has a write side effect.
- **Missing descriptor is a warning, not an error.** All three of
  `drop_descriptor`, `lookup_descriptor` use `ET_WARNING`
  `[verified-by-code: descriptor.c:119,121,149,151]`, so preprocessing
  continues and emits runtime calls anyway; the failure surfaces at runtime.
- **`whenever_action` bitmask is positional.** GET/SET *header* emitters pass
  `3` `[verified-by-code: descriptor.c:171,223]`; the data emitters pass
  `2 | 1` `[verified-by-code: descriptor.c:204,320]`. The `whenever_action`
  argument is a flags word, not a count.
- **`descriptor_variable` returns a pointer into function-static storage.**
  `varspace`/`descriptor_names` are `static` `[verified-by-code: descriptor.c:334-339]`,
  so the returned `struct variable *` is shared across calls for the same
  `input` slot and the name is `strlcpy`'d over on each call
  `[verified-by-code: descriptor.c:341]` — only valid because at most two live
  per statement.
- **SET item kinds differ between fatal and continue.** Not-implemented and
  cannot-be-set items call `mmfatal` (aborts preprocessing)
  `[verified-by-code: descriptor.c:285,295]`, whereas the GET-side `NULLABLE`/
  `KEY_MEMBER` cases only warn `[verified-by-code: descriptor.c:188,191]`.
- **`str_zero` churn.** `output_get_descr` / `output_set_descr` `mm_strdup("0")`
  then immediately `free` it per item, passing it as the `arr_str_siz` arg to
  `ECPGdump_a_type` `[verified-by-code: descriptor.c:183-199,304-309]` — an
  ECPGdump_a_type calling-convention requirement, not a real allocation need.

## Cross-refs

- [[knowledge/files/src/interfaces/ecpg/ecpglib/descriptor.c.md]] — the
  **runtime** counterpart; the `ECPGget_desc*`/`ECPGset_desc*` calls this file
  emits are implemented there.
- `src/interfaces/ecpg/preproc/preproc_extern.h` — declares the public
  symbols above, plus `mm_alloc`/`mm_strdup`/`loc_alloc`/`loc_strdup`,
  `find_variable`, `whenever_action`, `base_yyout`, `get_dtype`,
  `mmerror`/`mmfatal` `[verified-by-code: descriptor.c:12]`.
- `src/interfaces/ecpg/preproc/type.c` / `type.h` — `ECPGdump_a_type`,
  `get_dtype`, `struct ECPGtype`, the `ECPGt_*` / `ECPGd_*` enums consumed here.
- `src/interfaces/ecpg/preproc/variable.c` — `find_variable`,
  `struct variable` (the `descriptor_variable` / `sqlda_variable` builders here
  produce these for the rest of the preprocessor).

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-correctness: lookup_descriptor leaks/overwrites connection on lazy bind]** `descriptor.c:143` — when a connectionless registered descriptor is later looked up *with* a connection, `i->connection = mm_strdup(connection)` overwrites the (NULL) field with no free of any prior value. Benign here because the prior value is always NULL on this path (the `!i->connection` guard at `descriptor.c:140` ensures it), so not an actual leak; flagged only as a place where the invariant ("only bind when currently NULL") is load-bearing and unguarded against future edits. Low severity / likely a non-issue.
