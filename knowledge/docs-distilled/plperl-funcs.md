---
source_url: https://www.postgresql.org/docs/current/plperl-funcs.html
chapter: "45.1 PL/Perl Functions and Arguments (plperl-funcs)"
fetched_at: 2026-07-22
anchor_sha: d774576f6f0
---

# PL/Perl functions and arguments — plperl-funcs

The §45.1 value-marshalling chapter: how SQL args arrive in `@_`, how composite
and array types are represented, how to return scalars / composites / sets, and
the UTF-8 round-trip. The load-bearing cross-PL contrast: PL/Perl `return_next`
is documented as **streaming** (one row at a time), the opposite of PL/pgSQL's
materializing `RETURN NEXT` (see
`[[knowledge/docs-distilled/plpgsql-control-structures.md]]`).

## Non-obvious claims

- **Args arrive in `@_`, like any Perl sub.** "arguments are passed in `@_`, and
  a result value is returned with `return` or as the last expression evaluated
  in the function." [from-docs]
- **SQL NULL → Perl `undef`; return `undef` → SQL NULL.** "If an SQL null value
  is passed to a function, the argument value will appear as 'undefined' in
  Perl." and "to return an SQL null value from a PL/Perl function, return an
  undefined value." [from-docs] Guard args with Perl `defined`.
- **Composite-type argument = hash reference keyed by attribute name.**
  "Composite-type arguments are passed to the function as references to hashes.
  The keys of the hash are the attribute names of the composite type." [from-docs]
  e.g. `$emp->{basesalary}`.
- **Array argument = a *blessed* `PostgreSQL::InServer::ARRAY` object.** "Perl
  passes PostgreSQL arrays as a blessed `PostgreSQL::InServer::ARRAY` object.
  This object may be treated as an array reference or a string, allowing for
  backward compatibility with Perl code written for PostgreSQL versions below
  9.1." [from-docs] Multidimensional arrays are nested array-refs. The dual
  array-ref/string overload is the compatibility shim, not two representations.
- **Composite return = hash reference with the required attributes.** "return a
  reference to a hash that has the required attributes." OUT/INOUT procedure
  parameters return the same way — a hashref `{a => …, b => …}`. [from-docs]
- **Set-returning: two idioms, one STREAMS, one MATERIALIZES.**
  - `return_next(...)` per row, ending with `return` / `return undef`:
    "Usually you'll want to return rows one at a time, both to speed up startup
    time and to keep from queuing up the entire result set in memory." [from-docs]
    — i.e. streaming intent.
  - `return [ … ]` an array-ref of rows: "For small result sets, you can return
    a reference to an array…" — materializes the whole set. [from-docs]
  **Cross-PL note:** PL/pgSQL's `RETURN NEXT`/`RETURN QUERY` always tuplestore-
  materialize [verified-by-code pl_exec.c:3357/3452, see control-structures
  doc]; PL/Perl `return_next` is the one that keeps memory flat. Don't assume
  `return_next` behaves the same across the two languages.
- **Every value crosses a UTF-8 boundary.** "Arguments will be converted from
  the database's encoding to UTF-8 for use inside PL/Perl, and then converted
  from UTF-8 back to the database encoding upon return." [from-docs] So all
  args are text-form, UTF-8, per call — the same string round-trip cost the
  §45.2 "Data Values" page summarizes.
- **Boolean is a footgun without a TRANSFORM.** Booleans default to text `'t'`/
  `'f'`, and Perl treats the string `'f'` as **true** — so a naive `if ($bool)`
  is wrong. The docs recommend the `bool_plperl` extension via `CREATE
  TRANSFORM`. [from-docs]
- **`strict` is opt-in via `plperl.use_strict` GUC or in-body `use strict;`.**
  [from-docs]
- **Trusted `plperl` vs untrusted `plperlu`.** `plperlu` (PL/PerlU) lifts the
  Safe-compartment restrictions (filesystem, `require`, etc.); `plperl` is the
  sandboxed trusted language. [from-docs]

## Links into corpus

- `[[knowledge/docs-distilled/plpgsql-control-structures.md]]` — the
  MATERIALIZING `RETURN NEXT` this page's streaming `return_next` contrasts with.
- `[[knowledge/docs-distilled/plperl-under-the-hood.md]]` — §45.8, the trusted
  Safe compartment behind `plperl` vs `plperlu`.
- `[[knowledge/docs-distilled/plperl-builtins.md]]` — `spi_*`, `$_SHARED`, and
  the built-in helpers that complement this arg/return model.
- `[[knowledge/docs-distilled/xfunc-c.md]]` / skill `fmgr-and-spi` — the C-level
  fmgr contract these Perl conventions sit on top of; `collation.md` for the
  UTF-8/encoding boundary.

## Verification note

Value-marshalling behavioral chapter; all arg/return/encoding claims quoted
[from-docs] @ current. The materialize-vs-stream cross-PL contrast is anchored
on the [verified-by-code] `pl_exec.c` tuplestore cites in the companion
control-structures doc @ `d774576f6f0`.
