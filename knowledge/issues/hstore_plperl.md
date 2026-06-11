# Issues — `contrib/hstore_plperl`

Per-subsystem issue register for **hstore_plperl**, the hstore ↔ Perl
hash transform extension. Single-file extension, ~156 LOC.

**Parent docs:** `knowledge/files/contrib/hstore_plperl/hstore_plperl.c.md`

**Source:** sweep A21-D, 2026-06-11.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | hstore_plperl.c:130-133 | leak | nit | `sv2cstr` palloc'd then `pstrdup`'d again for key; both copies live until per-call context reset | open | files/contrib/hstore_plperl/hstore_plperl.c.md |
| 2026-06-11 | hstore_plperl.c:145-146 | leak | nit | Same duplicate-palloc pattern for values | open | files/contrib/hstore_plperl/hstore_plperl.c.md |
| 2026-06-11 | hstore_plperl.c:14 | dead-path | nit | `hstoreUpgrade_p` is fetched at init but never used | open | files/contrib/hstore_plperl/hstore_plperl.c.md |
| 2026-06-11 | hstore_plperl.c:38-52 | style | nit | `load_external_function` `signalNotFound = true` bool arg easy to misread (looks like "missing-OK") | open | files/contrib/hstore_plperl/hstore_plperl.c.md |

## Notes

The `StaticAssertVariableIsOfType` blocks (lines 25-29) are the right
defensive pattern for the `load_external_function` indirection used by
all the cross-module PL-bridges — if hstore's API drifts the build
fails. Same pattern reused in hstore_plpython, jsonb_plpython.

Trusted/untrusted: this extension installs only for `plperl`; the
parallel `hstore_plperlu` packages the same `.so` for untrusted Perl.
