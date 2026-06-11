# Issues — `contrib/jsonb_plpython`

Per-subsystem issue register for **jsonb_plpython**, the jsonb ↔
Python object transform extension. Single-file extension, ~518 LOC.

**Parent docs:** `knowledge/files/contrib/jsonb_plpython/jsonb_plpython.c.md`

**Source:** sweep A21-D, 2026-06-11.

## Headlines

1. **`PLyNumber_ToJsonbValue` PG_CATCH re-ereports.** Lines 364-380
   wrap `numeric_in` in `PG_TRY`, then the `PG_CATCH` arm fires a
   **fresh** `ereport(ERROR, ...)` rather than `PG_RE_THROW`. The
   original error's errcode, errdetail, and errcontext are lost.
   User sees only "could not convert value to jsonb".

2. **Python `None` dict-key silently becomes empty string.** Lines
   289-294: jsonb objects emit `""` for `None` keys with no
   warning, colliding silently with an actual `""` key.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | jsonb_plpython.c:374-379 | error-handling | likely | `PG_CATCH` arm re-ereports with new errcode; discards original numeric_in errcontext/errcode | open | files/contrib/jsonb_plpython/jsonb_plpython.c.md |
| 2026-06-11 | jsonb_plpython.c:289-294 | correctness | maybe | Python `None` dict key → empty-string jsonb key with no warning; collides with `""` key | open | files/contrib/jsonb_plpython/jsonb_plpython.c.md |
| 2026-06-11 | jsonb_plpython.c:501-508 | dead-path | nit | `cdecimal` import fallback dead since Python 3.3 (decimal C-impl now in stdlib) | open | files/contrib/jsonb_plpython/jsonb_plpython.c.md |
| 2026-06-11 | jsonb_plpython.c:388-395 | leak | nit | `numeric_is_nan` / `numeric_is_inf` ereports after Numeric allocated; tight pathological loops leak (per-call context cleanup) | open | files/contrib/jsonb_plpython/jsonb_plpython.c.md |
| 2026-06-11 | jsonb_plpython.c:167-217 | style | nit | NULL-return on `PyList_New(0)` failure inconsistent with rest of file (other branches `elog(ERROR, ...)` directly) | open | files/contrib/jsonb_plpython/jsonb_plpython.c.md |
| 2026-06-11 | jsonb_plpython.c:446-449 | error-handling | nit | `errmsg` allocates via `PLyObject_AsString` on type object; allocation inside errmsg argument is fragile | open | files/contrib/jsonb_plpython/jsonb_plpython.c.md |

## Notes

Largest PL-bridge in contrib. Type dispatch order matters: bool before
number (because `PyNumber_Check(True)` returns true). Unicode before
mapping/sequence (because Python str is both a sequence and not what
we want).

`decimal_constructor` is a permanent static set on first call; never
freed, never re-imported. Implicit assumption: the Python
interpreter is never reset within a session.

Trusted/untrusted: doesn't apply for plpython3u (untrusted only).
