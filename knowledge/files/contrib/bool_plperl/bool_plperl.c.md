# `contrib/bool_plperl/bool_plperl.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~33
- **Source:** `source/contrib/bool_plperl/bool_plperl.c`

Tiny transform-extension that bridges SQL `bool` and Perl truth values
for `plperl` functions declared with `TRANSFORM FOR TYPE bool`. Two
`PG_FUNCTION_INFO_V1` entry points, no `_PG_init`, no state. The two
maps are SQL `bool` → Perl `&PL_sv_yes`/`&PL_sv_no` immortal SVs, and
Perl SV → C `bool` via `SvTRUE`. [verified-by-code]

## API / entry points

- `bool_to_plperl(PG_FUNCTION_ARGS)` (line 14) — returns
  `PointerGetDatum(&PL_sv_yes)` or `&PL_sv_no` based on the input
  bool. Both are Perl-interpreter-level immortal SVs so refcount
  management is intentionally skipped. [verified-by-code]
- `plperl_to_bool(PG_FUNCTION_ARGS)` (line 26) — input is `(SV *)
  PG_GETARG_POINTER(0)`; result is `PG_RETURN_BOOL(SvTRUE(in))`.
  Uses Perl's overload-aware truthiness macro (numeric 0, empty
  string, `undef` → false; everything else → true). [verified-by-code]

## Notable invariants / details

- `dTHX;` declared in every entry point because the file is compiled
  with `PERL_IMPLICIT_CONTEXT`/multiplicity assumed (plperl.h dragged
  in). Without it the immortal-SV symbols would not resolve under
  thread-context Perl builds. [inferred]
- `PG_MODULE_MAGIC_EXT(.name = "bool_plperl", .version = PG_VERSION)`
  (line 7) — uses the `_EXT` magic-cookie variant added in PG 18 for
  named/versioned shared libraries. [verified-by-code]
- Transform is registered against **trusted `plperl`** only. The
  install SQL (`bool_plperl--1.0.sql`) creates the transform for
  `language plperl`; if a user wants the same coercion for
  `plperlu` they must install the parallel `bool_plperlu`
  extension, which packages the same `.so` under a different
  control file. This is the canonical "trusted vs untrusted
  transform" split that all the PL-bridge contribs replicate.
  [from-comment in adjacent SQL files / inferred]
- No error paths. Truthiness is total over Perl SVs; the bool side
  is unconditional. [verified-by-code]

## Potential issues

- None of severity. The file is small enough that there is nothing
  to lose-track-of: no allocs (immortal SVs), no refcount changes,
  no exception path. [ISSUE-undocumented-invariant: the trusted-vs-
  untrusted split is encoded in the .control / .sql plumbing, not in
  the C source; future readers may wonder why no `plperlu` symbol is
  referenced (nit)].

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `bool_plperl`](../../../issues/bool_plperl.md)
<!-- issues:auto:end -->
