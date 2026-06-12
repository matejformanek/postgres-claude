---
path: src/interfaces/ecpg/ecpglib/descriptor.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 1008
depth: deep
---

# `descriptor.c` — ECPG runtime for SQL DESCRIPTOR AREAs (ALLOCATE/DEALLOCATE/GET/SET/DESCRIBE)

## Purpose
Implements the libecpg runtime backing the SQL dynamic-descriptor statements
(`ALLOCATE DESCRIPTOR`, `DEALLOCATE DESCRIPTOR`, `GET DESCRIPTOR`,
`SET DESCRIPTOR`, and `DESCRIBE`). A descriptor wraps a `PGresult` plus a list
of `descriptor_item`s; the named descriptors live on a per-thread singly-linked
list keyed by a `pthread_key_t` so each thread sees its own set
(descriptor.c:22-51) [verified-by-code]. `GET DESCRIPTOR` reads metadata/data
out of the wrapped result via `PQ*` accessors and the variadic item-dispatch
loop; `SET DESCRIPTOR` builds up `descriptor_item`s to feed into a later
`EXECUTE ... USING SQL DESCRIPTOR`. `DESCRIBE` runs `PQdescribePrepared` and
parks the result into either a descriptor or an SQLDA.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `bool ECPGget_desc_header(int lineno, const char *desc_name, int *count)` | descriptor.c:84 | Returns field count (`PQnfields`) of the descriptor's result; sets `sqlerrd[2]=1` |
| `bool ECPGget_desc(int lineno, const char *desc_name, int index, ...)` | descriptor.c:234 | Variadic GET DESCRIPTOR item reader; `index` is 1-based field number |
| `bool ECPGset_desc_header(int lineno, const char *desc_name, int count)` | descriptor.c:589 | Sets `desc->count` |
| `bool ECPGset_desc(int lineno, const char *desc_name, int index, ...)` | descriptor.c:621 | Variadic SET DESCRIPTOR item writer; creates/updates a `descriptor_item` by `num==index` |
| `bool ECPGdeallocate_desc(int line, const char *name)` | descriptor.c:764 | Unlinks named descriptor from thread list and frees it |
| `bool ECPGallocate_desc(int line, const char *name)` | descriptor.c:808 | Allocates descriptor + empty `PGresult`, pushes onto thread list head |
| `struct descriptor *ecpg_find_desc(int line, const char *name)` | descriptor.c:848 | Linear lookup by name on thread list; raises `ECPG_UNKNOWN_DESCRIPTOR` if absent |
| `bool ECPGdescribe(int line, int compat, bool input, const char *connection_name, const char *stmt_name, ...)` | descriptor.c:863 | DESCRIBE OUTPUT into descriptor or SQLDA; DESCRIBE INPUT is unsupported (descriptor.c:872-877) |

## Internal landmarks
- **Per-thread descriptor list**: `descriptor_key`/`descriptor_once`,
  `get_descriptors`/`set_descriptors`, and `descriptor_destructor` →
  `descriptor_deallocate_all` registered as the TLS destructor
  (descriptor.c:22-51, 796-806). Thread exit frees the whole list.
- **`ecpg_result_by_descriptor`** (descriptor.c:54-62): convenience wrapper that
  `ecpg_find_desc`-es and returns `desc->result` (the `PGresult` GET reads from).
- **Item type dispatch (GET)**: the big `switch (type)` in `ECPGget_desc`
  (descriptor.c:295-468) routes each `ECPGd_*` item to `get_int_item` /
  `get_char_item`, or stashes `ECPGd_data`/`ECPGd_indicator` into a local
  `data_var` (descriptor.c:108-225, 297-321) for a deferred `ecpg_store_result`
  at descriptor.c:519. `ECPGd_ret_length`/`ECPGd_ret_octet` loop over tuples and
  may `ecpg_auto_alloc` an array (descriptor.c:421-461).
- **`RETURN_IF_NO_DATA`** macro (descriptor.c:227-232, `#undef` at 587): guards
  data/indicator/ret-length items against an empty result, doing `va_end`
  before raising.
- **Locale dance** (descriptor.c:493-534): forces `LC_NUMERIC=C` (via
  `uselocale`/`setlocale`) around `ecpg_store_result` so the DB's `.` decimal is
  parsed correctly, then restores.
- **Item type dispatch (SET)**: `ECPGset_desc` finds-or-creates a
  `descriptor_item` by `num` (descriptor.c:633-649), then loops the varargs
  filling `data`/`indicator`/`length`/`precision`/`scale`/`type`
  (descriptor.c:689-735). `set_desc_attr` (descriptor.c:600-618) frees the old
  `data` and installs the new (handling bytea binary length).
- **`descriptor_free`** (descriptor.c:744-762): frees every item's `data`, each
  item, then `name`, `PQclear(result)`, and the descriptor itself.
- **`ECPGdescribe` SQLDA path** (descriptor.c:939-998): builds compat or native
  SQLDA, frees the prior SQLDA chain via `desc_next`, `PQclear`s the result.

## Invariants & gotchas
- Descriptors are **per-thread**, not per-connection, despite the
  `ecpg_find_desc` comment "Find descriptor ... in the connection"
  (descriptor.c:847). Lookup/alloc/dealloc all go through the TLS list. A
  descriptor name allocated in one thread is invisible to another
  [verified-by-code, descriptor.c:40-51, 825, 843].
- `ECPGallocate_desc` does **not** check for a pre-existing same-named
  descriptor — it pushes a new node onto the list head unconditionally
  (descriptor.c:825-843). A second ALLOCATE of the same name shadows (does not
  replace) the first; `ecpg_find_desc`/`ECPGdeallocate_desc` then match the most
  recent one first. Re-allocating the same name without deallocating leaks the
  earlier node until thread exit [inferred from descriptor.c:779-790, 825].
- `index` in `ECPGget_desc` is 1-based and validated `1..PQnfields`
  (descriptor.c:264-269); it is decremented to 0-based at descriptor.c:272 before
  use in `PQ*` accessors.
- All `va_arg` exit paths must `va_end(args)` — the code is careful to do so on
  every early return (descriptor.c:258, 267, 326, ...). The varargs ABI for GET
  vs SET vs DESCRIBE differs; `ECPGdescribe` deliberately skips 8 trailing args
  per variable (descriptor.c:906-917).
- `ecpg_find_desc` returning NULL already raised `ECPG_UNKNOWN_DESCRIPTOR`; most
  callers just propagate `false`/break without re-raising
  (descriptor.c:592-595, 629-631, 926-927).
- `descriptor_item->data` is freed by both `set_desc_attr` (on overwrite) and
  `descriptor_free`; `ecpg_free` tolerates NULL (descriptor.c:616, 753).

## Cross-refs
- [[execute.c]], [[sqlda.c]], [[data.c]]
- also: `ecpg_store_result` / `ecpg_store_input` / `ecpg_auto_alloc` (execute path),
  `ecpg_build_compat_sqlda` / `ecpg_build_native_sqlda` ([[sqlda.c]]).

## Potential issues
- **[ISSUE-leak: ECPGset_desc leaks `var` when item already had no slot? — NO]**
  Re-examined: `var` (descriptor.c:651) is freed on every exit
  (descriptor.c:695, 731, 737); not a leak. Listed only to record it was checked.
- **[ISSUE-robustness: ignored `set_int_item` return]** `descriptor.c:706-722` —
  the `ECPGd_indicator/length/precision/scale/type` cases call `set_int_item`
  and discard its `bool` result, so a non-numeric host-var type silently raises
  `ECPG_VAR_NOT_NUMERIC` inside `set_int_item` yet `ECPGset_desc` continues the
  loop and ultimately returns `true`. By contrast the GET side checks every
  `get_int_item` return. Low severity (the raise still sets sqlca), but the
  success/failure signal is inconsistent with the rest of the file
  [verified-by-code, descriptor.c:706-722 vs 334-349].
