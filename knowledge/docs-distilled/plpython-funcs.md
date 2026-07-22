---
source_url: https://www.postgresql.org/docs/current/plpython-funcs.html
chapter: "46.2 PL/Python Functions (plpython-funcs)"
fetched_at: 2026-07-22
anchor_sha: d774576f6f0
---

# PL/Python functions — plpython-funcs

The §46.2 chapter on how a PL/Python function body is wrapped, how args are
exposed, how `None`↔NULL works, and — the load-bearing bit — how set-returning
functions can **stream via `yield`/a generator**, unlike PL/pgSQL's
materializing `RETURN NEXT`.

## Non-obvious claims

- **The body is wrapped in a generated Python function; args are exposed BOTH as
  named globals AND in the `args` list.** "When the function is called, its
  arguments are passed as elements of the list `args`; named arguments are also
  passed as ordinary variables to the Python script." [from-docs] The generated
  wrapper looks like `def __plpython_procedure_pymax_23456(): …` with the SQL
  parameter names bound as globals.
- **Scoping gotcha from that wrapping:** because parameters are module-level
  globals in the generated function, reassigning a parameter name inside a
  nested block requires a Python `global` declaration first — a direct
  consequence of how the body is embedded, not a language quirk you'd expect.
  [from-docs]
- **`None` ↔ SQL NULL, both directions.** "PL/Python translates Python's `None`
  into the SQL null value." [from-docs] For **procedures**, the result "must be
  `None`" (end without `return`, or bare `return`) or an error is raised — a
  procedure may not return a value.
- **Set-returning functions may STREAM via a generator (`yield`).** A SETOF/TABLE
  PL/Python function can `return` any iterable (sequence, iterator) **or**
  `yield` rows from a generator. [from-docs] The generator form does not
  necessarily buffer the whole set in Python — contrast PL/pgSQL `RETURN NEXT`,
  which always tuplestore-materializes [verified-by-code pl_exec.c:3357/3452,
  see `[[knowledge/docs-distilled/plpgsql-control-structures.md]]`]. This makes
  PL/Python (and PL/Perl `return_next`) the streaming-capable set-returning PLs
  and PL/pgSQL the materializing one — a genuine cross-PL semantic split.
- **Composite return = a dict, a sequence, or an object with named attributes.**
  A composite/row result can be produced as a Python dict keyed by column name,
  a sequence in column order, or any object exposing the columns as attributes.
  [from-docs]
- **Python 3 only: `plpython3u`.** The Python 2 variants (`plpythonu`,
  `plpython2u`) are gone in current PG; only the untrusted `plpython3u` exists
  (PL/Python is untrusted-only — there is no trusted `plpython`). [from-docs,
  inferred — the examples use `plpython3u` exclusively]

## Links into corpus

- `[[knowledge/docs-distilled/plpgsql-control-structures.md]]` — the
  MATERIALIZING `RETURN NEXT` that the `yield`/generator form contrasts with.
- `[[knowledge/docs-distilled/plpython-sharing.md]]` — §46.3, the `SD`/`GD`
  state that lives in the per-function execution environment described here.
- `[[knowledge/docs-distilled/plpython-data.md]]` — §46.5, the detailed
  Python↔SQL type mapping behind the arg/return conversions summarized here.
- `[[knowledge/docs-distilled/plperl-funcs.md]]` — the sibling PL's streaming
  `return_next`; both differ from PL/pgSQL.
- Skill `fmgr-and-spi` — the SRF ValuePerCall/Materialize modes the generator vs
  return-iterable forms map onto at the C level.

## Verification note

Behavioral chapter; arg-exposure, `None`↔NULL, generator-streaming, and
composite-return claims quoted [from-docs] @ current. The materialize-vs-stream
cross-PL contrast is anchored on the [verified-by-code] `pl_exec.c` tuplestore
cites in the control-structures doc @ `d774576f6f0`. Python-3-only is [inferred]
from the exclusive `plpython3u` usage.
