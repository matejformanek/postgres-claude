# Issues — `contrib/bool_plperl`

Per-subsystem issue register for **bool_plperl**, the SQL bool ↔ Perl
truth-value transform extension. Single-file extension, ~33 LOC.

**Parent docs:** `knowledge/files/contrib/bool_plperl/bool_plperl.c.md`

**Source:** sweep A21-D, 2026-06-11.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | bool_plperl.c (whole file) | undocumented-invariant | nit | Trusted-vs-untrusted split is encoded in `.control`/`.sql` only; no C-source comment explains why no `plperlu` symbol is referenced | open | files/contrib/bool_plperl/bool_plperl.c.md |

## Notes

The file is small enough that the surface area is essentially nil:
two functions, immortal Perl SVs, no allocations, no exception path.
The "trusted/untrusted" pattern (parallel `bool_plperlu` extension
packaging the same `.so` under a different control file) is the
cross-PL-bridge pattern; readers chasing it should consult the
adjacent `bool_plperlu/` directory in source.
