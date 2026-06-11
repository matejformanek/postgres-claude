# `contrib/jsonb_plperl/jsonb_plperl.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~309
- **Source:** `source/contrib/jsonb_plperl/jsonb_plperl.c`

Transform-extension bridging `jsonb` and Perl scalars/arrays/hashes
for `plperl` functions with `TRANSFORM FOR TYPE jsonb`. Larger than
the hstore bridge because jsonb has a recursive structure (objects /
arrays / four scalar types) and because Perl's type system is loose
(IV vs UV vs NV vs PV) so the SV → JsonbValue side must dispatch on
multiple SV flags. Unlike `hstore_plperl`, no `_PG_init` is needed
because all callees are core-backend symbols (jsonb infrastructure +
numeric I/O). [verified-by-code]

## API / entry points

- `jsonb_to_plperl(PG_FUNCTION_ARGS)` (line 287) — `Jsonb_to_SV` on
  the container root; returns `PointerGetDatum(sv)`. [verified-by-code]
- `plperl_to_jsonb(PG_FUNCTION_ARGS)` (line 300) — wraps an
  `SV_to_JsonbValue` call with a fresh `JsonbInState`, then
  `JsonbValueToJsonb`. [verified-by-code]

### Internal helpers

- `JsonbValue_to_SV(JsonbValue *jbv)` (line 19) — scalar jbv types to
  Perl SVs. `jbvNumeric` round-trips through `numeric_out` then
  `SvNV` (Perl float). `jbvBool` likewise via `SvNV` of the
  immortal SV. `jbvNull` → `newSV(0)`. [verified-by-code]
- `Jsonb_to_SV(JsonbContainer *jsonb)` (line 61) — iterator walks
  the container. The rawScalar-array case unwraps the one-element
  dummy array that jsonb uses to wrap top-level scalars. Object →
  HV with `hv_store`; array → AV with `av_push`; returns
  `newRV` of the container. [verified-by-code]
- `SV_to_JsonbValue(SV *in, ...)` (line 176) — dereferences
  `SvROK` recursively, then switches on `SvTYPE`. `SVt_PVAV` and
  `SVt_PVHV` recurse via `AV_to_JsonbValue` / `HV_to_JsonbValue`.
  Default branch tests `SvUOK`/`SvIOK`/`SvNOK`/`SvPOK` in order;
  rejects inf and NaN explicitly (lines 235, 239). [verified-by-code]

## Notable invariants / details

- Boolean round-trip is **lossy on output**: jbvBool → Perl
  `newSVnv(SvNV(... &PL_sv_yes/no))` produces a float 1.0 or 0.0,
  not a Perl Boolean. Going back through `plperl_to_jsonb`, the
  result is `SvNOK` and lands as `jbvNumeric` 1 or 0 — not jbvBool.
  This is **intentional** because Perl has no native boolean type
  prior to 5.36's `builtin::true/false`. [verified-by-code]
  [ISSUE-correctness: jsonb true/false → Perl 1/0 → jsonb 1/0 is a
  silent type erosion across the transform; documented in plperl
  docs but easy to trip over (maybe)].
- Numeric round-trip on the in side **lifts through Perl float**:
  `numeric_out` → cstring → `cstr2sv` → `SvNV` → `newSVnv`. Loses
  precision for `numeric` values that don't fit in IEEE 754 double.
  Documented as a known limitation (line 206 comment for UV case
  alludes to the same problem). [verified-by-code]
- `SvUOK` (unsigned IV) branch (line 201) converts via text rather
  than direct int64 → numeric because Perl UV may be 64-bit and
  PG's `int64_to_numeric` is signed-only. [verified-by-code]
- `palloc_object(JsonbValue)` (line 279) at top level is required
  so the `JsonbInState->result` survives the function's stack
  frame; `JsonbValueToJsonb` will read it after `SV_to_JsonbValue`
  returns. [verified-by-code]
- Trusted/untrusted: registered only for `plperl`. `jsonb_plperlu`
  parallel install handles untrusted. [inferred]
- No `PG_TRY/CATCH` blocks. If a `DirectFunctionCall1(numeric_out, …)`
  errors mid-recursion, the partial Perl-SV graph leaks (the
  refcount-1 SVs are not chained into the interpreter root set).
  These leak into the per-call memory context only via cstring
  buffers; the SVs themselves leak the Perl arena until interpreter
  destruction. [inferred] [ISSUE-leak: ereport mid-traversal leaks
  intermediate SVs into Perl arena; bounded by interpreter
  lifetime (nit)].

## Potential issues

- Lines 33, 50: `newSVnv(SvNV(cstr2sv(str)))` — the intermediate SV
  from `cstr2sv` has refcount 1 and is **never released**. Same on
  the bool branch. Tiny per-call leak in the Perl arena, bounded by
  the plperl interpreter lifetime (re-init only at session end).
  [ISSUE-leak: cstr2sv intermediate SVs leak per scalar (nit)].
- Line 209: `SvPV_nolen(in)` on a UV-valued SV produces a string;
  no `pfree` because Perl owns the buffer, but the subsequent
  `numeric_in` call may ereport on overflow (UV > 1e1000 unlikely
  but possible if Perl was built with `long double`). [ISSUE-
  correctness: UV → text → numeric path inherits numeric_in
  errors; user sees "invalid input syntax for type numeric"
  rather than a hint about the UV range (nit)].
- Line 261 has a vestigial `XXX` comment requesting better error
  detail. [ISSUE-stale-todo: comment-only since at least PG 11
  (nit)].
- Line 269: `pushJsonbValue(... is_elem ? WJB_ELEM : WJB_VALUE, &out)`
  passes the address of a stack-local `JsonbValue`. `pushJsonbValue`
  copies the struct internally so this is safe, but contributes to
  the asymmetry with the top-level branch (which palloc's). [ISSUE-
  style: top-level vs nested allocation asymmetry warrants a
  comment (nit)].
