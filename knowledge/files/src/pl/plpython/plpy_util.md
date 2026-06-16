# plpy_util (plpy_util.c + plpy_util.h)

Covers `source/src/pl/plpython/plpy_util.c` (119 LOC) and `source/src/pl/plpython/plpy_util.h` (17 LOC).

Source pin: `4b0bf0788b0`.

## One-line summary

Four PGDLLEXPORT helpers that move strings across the Python ↔ PG encoding boundary: `PLyUnicode_Bytes` (Python str → PG-encoded `bytes` object), `PLyUnicode_AsString` (Python str → palloc'd C string), `PLyUnicode_FromString` and `PLyUnicode_FromStringAndSize` (C string → Python str). UTF-8 is the unconditional intermediate because Python's codec set is a strict subset of PG's (notably missing EUC_TW).

## Public API / entry points

All four are `PGDLLEXPORT`, declared in `plpy_util.h`:

- `PLyUnicode_Bytes(PyObject *unicode) -> PyObject *` — encode to server encoding, return new `bytes` object (caller owns ref) [verified-by-code: `source/src/pl/plpython/plpy_util.c:18-73`].
- `PLyUnicode_AsString(PyObject *unicode) -> char *` — same, but return `pstrdup`'d C string in the current memory context [verified-by-code: `source/src/pl/plpython/plpy_util.c:80-88`].
- `PLyUnicode_FromStringAndSize(const char *s, Py_ssize_t size) -> PyObject *` — decode server-encoded bytes into a Python str (caller owns ref) [verified-by-code: `source/src/pl/plpython/plpy_util.c:94-113`].
- `PLyUnicode_FromString(const char *s) -> PyObject *` — `strlen`-based wrapper around `FromStringAndSize` [verified-by-code: `source/src/pl/plpython/plpy_util.c:115-119`].

## Key invariants

- **UTF-8 is the unconditional intermediate.** Even when the server encoding matches Python's expected encoding, the code path runs `PyUnicode_AsUTF8String` first, then `pg_any_to_server(..., PG_UTF8)` [from-comment: `source/src/pl/plpython/plpy_util.c:38-45`]. The comment explicitly names EUC_TW as the reason: PG supports it, CPython does not.
- **`pg_any_to_server` short-circuits when src encoding == server encoding.** The "free if pg_any_to_server allocated memory" check at `:68` is `if (utf8string != encoded) pfree(encoded)` — `pg_any_to_server` returns its input pointer unchanged when no conversion is needed. This is a documented `mb/mbutils.c` contract; relying on it here is fine.
- **`PLyUnicode_AsString` always palloc's a new copy via `pstrdup`** [verified-by-code: `source/src/pl/plpython/plpy_util.c:84`]. The caller doesn't have to worry about the Python `bytes` object's lifetime; the returned char* lives until the surrounding memory context is reset. Used heavily in plpy_spi.c (e.g. `:91`, `:203`).
- **Reference ownership comment is part of the contract.** Every function header explicitly says who owns the resulting PyObject ref (caller for `Bytes` / `FromString*`, no transfer for `AsString` since it returns a C string) [from-comment: `source/src/pl/plpython/plpy_util.c:14-17, 75-79, 90-93`]. Violating this is the #1 source of refcount leaks in C-extension Python code.
- **`PG_TRY`/`PG_CATCH` around `pg_any_to_server` only when conversion is needed** [verified-by-code: `source/src/pl/plpython/plpy_util.c:46-60`]. If `pg_any_to_server` throws (invalid byte sequence for server encoding), the `bytes` Python object must be DECREF'd before re-throw. When server encoding IS UTF-8, the call is skipped and no PG_TRY is needed.

## Notable internals

### Why UTF-8 intermediate hides a perf hit

A `PLyUnicode_AsString` call on an N-byte ASCII string does:

1. `PyUnicode_AsUTF8String` — N-byte allocation in Python heap.
2. `pg_any_to_server(..., PG_UTF8)` — returns input pointer unchanged on UTF-8 server, OR converts via `pg_do_encoding_conversion` (which itself does another allocation).
3. `pstrdup` of the result — third allocation in current PG context.
4. `Py_DECREF(bytes)` — free step 1.

Result: 2 allocations + 1 free for an ASCII string on a UTF-8 server. Not a bug, but explains why `plpy.execute("SELECT $1", ["very_long_string"])` is measurably slower than plpgsql `EXECUTE`. The cost scales linearly with argument size, so for a few-KB payload it disappears; for MB-sized inputs it shows up.

### Empty `bytes` object on empty Python str

[verified-by-code: `source/src/pl/plpython/plpy_util.c:65`] — `PyBytes_FromStringAndSize(encoded, strlen(encoded))` uses `strlen`, which means embedded NULs in the encoded bytes are silently truncated. PG strings are NUL-terminated by definition (no NUL bytes in valid TEXT), so this is correct in practice — but it does mean that a Python `b"\x00"` shipped through these helpers ends up as an empty string. The check upstream is "did the user pass a str?" — `bytes`-typed args go through different conversion in plpy_typeio.c.

### `PLyUnicode_FromStringAndSize` doesn't use `size` after conversion

[verified-by-code: `source/src/pl/plpython/plpy_util.c:100-110`] — when `pg_server_to_any` does convert (i.e. server encoding ≠ UTF-8), the result goes to `PyUnicode_FromString` (the NUL-terminated variant) instead of `FromStringAndSize`. This is again the "NUL-terminated by convention" assumption. Only when no conversion happens does it use `size`. Subtle but correct: the converted UTF-8 string from `pg_server_to_any` IS NUL-terminated.

## Cross-references

- `source/src/backend/utils/mb/mbutils.c` — `pg_any_to_server`, `pg_server_to_any`, `GetDatabaseEncoding`. The "returns input pointer unchanged when no conversion needed" contract is what makes the `pfree`-conditional at `:68` safe.
- `source/src/include/mb/pg_wchar.h` — `PG_UTF8` constant.
- `plpy_typeio.c` (not in this slice) — the type I/O glue that's the main caller of these helpers.
- `plpy_spi.c.md` (this sweep) — calls `PLyUnicode_AsString` to convert query strings and type-name strings.
- A10-1 plperl: `sv2cstr` is the spiritual equivalent for Perl strings; uses similar UTF-8-then-pg_any_to_server idiom.
- pltcl.c (this sweep): `utf_u2e` / `utf_e2u` are even simpler — Tcl strings are always UTF-8 by design, so no Python-style intermediate is needed.

<!-- issues:auto:begin -->
- [Issue register — `plpython`](../../../../issues/plpython.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-memory: `PLyUnicode_AsString` doubles allocator pressure on hot paths (nit)]** — `source/src/pl/plpython/plpy_util.c:80-88`. Every call does PyUnicode→bytes→pstrdup, leaving the bytes refcount to be reaped by `Py_XDECREF`. For loops over large result sets this is measurable. Not a correctness issue; would be a non-trivial refactor to expose a "borrow the bytes" variant since the caller doesn't generally know how long it'll need the result.
- **[ISSUE-correctness: embedded NUL handling silently truncates (likely)]** — `source/src/pl/plpython/plpy_util.c:65, 84`. A Python str containing `\x00` produces a server-encoded bytes object whose length is `strlen(encoded)`, not the encoded length. PG TEXT can't contain NULs anyway, but a user-facing function that accepts a Python str arg and round-trips it through `PLyUnicode_AsString` will silently lose data past the first NUL. Worth a comment if not a fix.
- **[ISSUE-defense-in-depth: no length cap on input (audit-gap, maybe)]** — `source/src/pl/plpython/plpy_util.c:18-73`. A multi-GB Python str gets allocated twice (UTF-8 bytes + server-encoded bytes) before any size sanity check. Backend OOM is the natural limit. Hardening would add an explicit `MaxAllocSize` guard with a clearer error message.
- **[ISSUE-api-shape: `PLyUnicode_Bytes` returns a *bytes* but most callers immediately stringify (api-shape, nit)]** — `source/src/pl/plpython/plpy_util.c:18-73`. Every call site in plpy_spi.c uses it only to extract a C string. The bytes intermediate exists so that the encoding step happens once; an inlined variant could skip the bytes-PyObject construction. Micro-optimization, not a real issue.
