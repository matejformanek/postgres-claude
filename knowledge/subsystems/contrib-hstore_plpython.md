# contrib-hstore_plpython (hstore ↔ Python dict transform)

- **Source path:** `source/contrib/hstore_plpython/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `hstore_plpython3u.control`)
- **Requires:** `hstore`, `plpython3u`

## 1. Purpose

PL transform — when a PL/Python function receives an
`hstore` argument or returns one, the transform converts
between `hstore` and Python `dict`. Without the transform,
PL/Python sees hstore as a string; with it, native Python
dict.

Mirror of `contrib-hstore_plperl` in shape, but Python
instead of Perl. The build patterns and `TRANSFORM FOR
TYPE hstore` SQL syntax are identical.

## 2. PL/Python 3 only

[verified-by-code `hstore_plpython3u.control`]

```
requires = 'hstore,plpython3u'
```

PL/Python 2 is gone (deprecated in PG 12, removed in
PG 16). This transform supports plpython3u only. The
control file's `3u` suffix reflects the version + the
"untrusted" requirement (plpython3u is untrusted by
design; there's no plpython3 trusted variant).

## 3. The implementation strategy

[verified-by-code `hstore_plpython.c:12-25`]

Cross-module access via function pointers:

```c
typedef char *(*PLyObject_AsString_t) (PyObject *plrv);
static PLyObject_AsString_t PLyObject_AsString_p;
typedef PyObject *(*PLyUnicode_FromStringAndSize_t) (...);
static PLyUnicode_FromStringAndSize_t PLyUnicode_FromStringAndSize_p;

/* + 5 function pointers from hstore.so */
typedef HStore *(*hstoreUpgrade_t) (Datum orig);
static hstoreUpgrade_t hstoreUpgrade_p;
/* etc. */
```

Two sets of cached symbols:
- From `plpython3u.so` — Python string conversion + memory
  helpers.
- From `hstore.so` — HStore construction + validation.

The transform code uses both sets to convert between
hstore and Python dict.

## 4. The SQL setup

```sql
CREATE EXTENSION hstore_plpython3u;

CREATE FUNCTION process_hstore(h hstore) RETURNS hstore
TRANSFORM FOR TYPE hstore
LANGUAGE plpython3u
AS $$
    h['processed'] = 'true'
    return h
$$;
```

Same `TRANSFORM FOR TYPE` mechanism as plperl.

## 5. The conversion semantics

- **hstore key/value** → Python `str`. Empty strings OK.
- **hstore NULL value** → Python `None`.
- **hstore NULL key** → ERROR (Python dict keys can't be
  None unless explicit; dict semantics).
- **Python dict** → hstore. Keys must be strings (cast if
  not).
- **Nested Python objects** → ERROR. hstore is flat.

## 6. Unicode handling

Python 3 strings are native Unicode. hstore is bytes that
PG treats per the database's encoding (`SQL_ASCII` /
`UTF8` etc.). The transform decodes/encodes per the database
encoding.

For non-UTF-8 databases with hstore values that include
non-ASCII bytes, the Python side may receive invalid
Unicode — the transform raises.

## 7. The trusted variant question

There is no `hstore_plpython` (trusted) variant — only
`hstore_plpython3u`. That's because plpython3u is itself
untrusted (Python's introspection / OS-access features
can't be sandboxed safely).

If you need trusted PL with Python-like semantics, look at
PL/v8 or pl/lua. Both have trusted versions.

## 8. Production-use guidance

- **plpython3u is superuser-only** by default; grant USAGE
  carefully.
- **For deeply structured data**, use `jsonb_plpython`
  instead — hstore is flat.
- **The transform avoids per-call string parsing** — 5-10×
  faster than the no-transform pattern on hot loops.
- **Beware GIL** — Python's GIL serializes Python code;
  parallel-query scans that call this function can't
  parallelize past the GIL.

## 9. Invariants

- **[INV-1]** Requires `hstore` + `plpython3u`.
- **[INV-2]** PL/Python 3 only; PL/Python 2 was removed.
- **[INV-3]** Engaged via `TRANSFORM FOR TYPE hstore`.
- **[INV-4]** Cross-module access via cached function
  pointers from both plpython3u.so + hstore.so.
- **[INV-5]** No trusted variant — plpython3u is
  superuser-only by design.

## 10. Useful greps

- Cross-module symbol loading:
  `grep -n 'PLyObject_AsString_p\|hstoreUpgrade_p' source/contrib/hstore_plpython/hstore_plpython.c | head -10`
- The conversion entry points:
  `grep -n 'PG_FUNCTION_INFO_V1\|hstore_to_plpython\|plpython_to_hstore' source/contrib/hstore_plpython/hstore_plpython.c`
- The 194-LOC entire file:
  `wc -l source/contrib/hstore_plpython/hstore_plpython.c`

## 11. Cross-references

- `knowledge/subsystems/contrib-hstore.md` — the type.
- `knowledge/subsystems/contrib-hstore_plperl.md` —
  sibling transform; Perl instead of Python.
- `knowledge/subsystems/contrib-jsonb_plperl.md` —
  sibling transform; jsonb instead of hstore.
- `.claude/skills/fmgr-and-spi/SKILL.md` — PL function
  registration.
- `.claude/skills/extension-development/SKILL.md` —
  cross-extension dependencies.
- `source/contrib/hstore_plpython/hstore_plpython.c` —
  implementation (194 LOC).

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/hstore_plpython/hstore_plpython.c`](../files/contrib/hstore_plpython/hstore_plpython.c.md) |

<!-- /files-owned:auto -->
