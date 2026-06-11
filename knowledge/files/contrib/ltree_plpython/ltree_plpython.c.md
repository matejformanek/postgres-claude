# `contrib/ltree_plpython/ltree_plpython.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~62
- **Source:** `source/contrib/ltree_plpython/ltree_plpython.c`

Tiny one-way transform-extension converting `ltree` values to Python
lists of strings (one element per level) for `plpython3u` functions
with `TRANSFORM FOR TYPE ltree`. **Unlike the other PL-bridges, no
reverse direction is provided**: there is no `plpython_to_ltree`
function. Python code receiving an `ltree` parameter gets a list,
but returning an `ltree` must go through the normal text I/O path.
[verified-by-code]

## API / entry points

- `_PG_init(void)` (line 23) — fetches only
  `PLyUnicode_FromStringAndSize` from `$libdir/PLPYTHON_LIBNAME`. No
  hstore/ltree symbols needed because the bridge only consumes
  `ltree` data, never produces it. [verified-by-code]
- `ltree_to_plpython(PG_FUNCTION_ARGS)` (line 38) — allocates a
  `PyList_New(in->numlevel)`, walks `LTREE_FIRST(in)` /
  `LEVEL_NEXT(curlevel)`, and `PyList_SetItem`s each level's name.
  `PG_FREE_IF_COPY(in, 0)` releases any detoasted copy.
  Returns `PointerGetDatum(list)`. [verified-by-code]

## Notable invariants / details

- Only one direction: ltree → Python. The decision (verifiable
  from the install SQL `ltree_plpython--1.0.sql`) is presumably
  that "list of strings" doesn't uniquely round-trip back to
  ltree (e.g. invalid characters per level need diagnostic). A
  user can `'.'.join(list)` in Python and let the standard
  `text → ltree` cast handle validation. [inferred]
- `PyList_SetItem` **steals** the reference returned by
  `PLyUnicode_FromStringAndSize`, so no `Py_DECREF` is needed in
  the loop. This is correct API usage. [verified-by-code]
- `PyList_New` failure → `errcode(ERRCODE_OUT_OF_MEMORY)` ereport.
  Same caveat as the hstore_plpython case: the actual Python
  error is swallowed. [ISSUE-error-handling: generic OOM swallows
  Python error (nit)].
- `PLyUnicode_FromStringAndSize` failure (NULL return) is **not
  checked**. `PyList_SetItem(list, i, NULL)` is documented as
  equivalent to setting None, so it doesn't crash, but the caller
  ends up with `None` in place of a level name, silently. This
  could be reached if an ltree contains non-UTF-8 bytes (which
  ltree input does not allow, but a corrupt page could). [ISSUE-
  correctness: silent None-substitution on decode failure (nit)].
- `dTHX;` and friends are absent because plpython has no
  thread-context macro — Python 3 is reference-counted but not
  multi-threaded under plpython3u (the GIL serializes everything).
  [inferred]

## Potential issues

- The asymmetry (no `plpython_to_ltree`) is **undocumented in the
  C source**. A reader expects the symmetric pair common to
  other PL-bridges. [ISSUE-undocumented-invariant: missing reverse
  direction has no comment explaining why (nit)].
- Line 53-57: tight loop with no `CHECK_FOR_INTERRUPTS()`. An
  ltree with millions of levels (artificial — input validator
  caps at 65535 levels via the 16-bit `numlevel`) would not
  respond to SIGINT mid-conversion. Bound by `numlevel`'s 16-bit
  width so worst-case 65k iterations — small enough to be
  acceptable. [ISSUE-style: no CFI in tight loop, mitigated by
  ltree's own 65k cap (nit)].
- `PG_FREE_IF_COPY` runs unconditionally after the list is built;
  no error path between alloc and free, so no leak window.
  [verified-by-code]
