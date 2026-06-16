# `contrib/hstore_plperl/hstore_plperl.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~156
- **Source:** `source/contrib/hstore_plperl/hstore_plperl.c`

Transform-extension bridging the `hstore` type and Perl hashes for
`plperl` functions with `TRANSFORM FOR TYPE hstore`. Loads five
function pointers from `$libdir/hstore` at `_PG_init` time so the
bridge does not depend on hstore's linker-visible symbols (avoids
double-init). One direction copies HStore key/value pairs into a
newly-allocated `HV`; the other walks a hash, builds a `Pairs[]`
array, and calls `hstoreUniquePairs` / `hstorePairs` to assemble the
HStore on the fly. [verified-by-code]

## API / entry points

- `_PG_init(void)` (line 35) — fetches `hstoreUpgrade`,
  `hstoreUniquePairs`, `hstorePairs`, `hstoreCheckKeyLen`,
  `hstoreCheckValLen` via `load_external_function("$libdir/hstore",
  ...)`. Calls use `missing_ok = true`'s **opposite**: third arg is
  `true` which actually means "report errors" (the bool name in
  `load_external_function` is `signalNotFound`). If hstore is not
  installed the load aborts. [verified-by-code]
- `hstore_to_plperl(PG_FUNCTION_ARGS)` (line 64) — copies each
  HStore pair, `pnstrdup`s the key and value, builds a Perl HV via
  `hv_store`, returns `PointerGetDatum(newRV((SV *) hv))` (a
  reference to the hash). NULL values map to `newSV(0)` (Perl
  `undef`). [verified-by-code]
- `plperl_to_hstore(PG_FUNCTION_ARGS)` (line 97) — input is an SV,
  dereferenced through `SvROK` until a non-ref; rejects anything
  other than `SVt_PVHV` with `ERRCODE_FEATURE_NOT_SUPPORTED`.
  Iterates `hv_iternext`, calling `sv2cstr` on each key/value and
  `hstoreCheckKeyLen`/`hstoreCheckValLen` to enforce hstore's
  length cap. `pcount = hstoreUniquePairs(...)` deduplicates,
  `hstorePairs` builds the final HStore. [verified-by-code]

## Notable invariants / details

- `hstoreUpgrade_p` is fetched at init but **never used** in this
  file. The pointer is loaded defensively in case the v1-on-disk
  format ever shows up here; since transforms only see decompressed
  Datums, it's effectively dead. [inferred] [ISSUE-dead-path:
  `hstoreUpgrade_p` unused (nit)].
- `StaticAssertVariableIsOfType` blocks (lines 25-29) catch the
  classic bug where the local typedef drifts from the real hstore
  function signature. This is the right pattern for the
  `load_external_function` indirection — without it a mismatch
  would only blow up at runtime. [verified-by-code]
- Trusted/untrusted: only registered for `plperl`. Mirrors the
  `bool_plperl` pattern; an `hstore_plperlu` parallel extension
  provides the same for untrusted. [inferred]
- `sv2cstr` allocates a palloc'd C string in the caller's
  memory context; the result is then `pstrdup`'d into `pairs[i].key`
  even though `sv2cstr` already returns palloc memory. The double-
  copy is wasteful but harmless — the original buffer leaks into
  the per-call context which is reset after the function returns.
  [verified-by-code]
- `newRV` returns a reference SV whose refcount is 1; Perl owns the
  HV after `hv_store`. The Postgres caller treats the SV pointer
  as opaque and frees nothing — refcounts are released when the
  plperl interpreter unwinds. [inferred]

## Potential issues

- Lines 130-133: `sv2cstr(HeSVKEY_force(he))` palloc's key buffer,
  then `pstrdup(key)` allocates again, and `needfree = true` will
  cause `hstoreUniquePairs` to pfree only the second copy. The first
  copy leaks until the caller's memory context resets. [ISSUE-leak:
  duplicate key palloc, both copies live until context reset; in a
  tight loop calling plperl_to_hstore with huge hashes this could
  accumulate (nit)].
- Lines 145-146: same pattern for values — `sv2cstr` then `pstrdup`.
  [ISSUE-leak: same as above for values (nit)].
- The `signalNotFound = true` argument to `load_external_function`
  is correct but easy to misread because most callers pass `false`
  / `true` meaning "missing-OK". [ISSUE-style: bool literal would
  read better as a named flag (nit)].

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `hstore_plperl`](../../../issues/hstore_plperl.md)
<!-- issues:auto:end -->
