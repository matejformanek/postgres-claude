# Issues — `contrib/test_decoding`

Per-subsystem issue register for **test_decoding**, the reference
logical-decoding output plugin. Created 2026-06-11 by A21 sweep.

**Parent doc:** `knowledge/files/contrib/test_decoding/test_decoding.c.md`

## Headlines

1. **No GUC; no superuser check.** All configuration is per-slot
   via output_plugin_options. The plugin itself is harmless data
   transformation; the access surface is the slot itself.

2. **Streaming mode deliberately hides change contents** until
   commit (test_decoding.c:911-915). Test consumers that expect to
   see tuple data in stream_change get just "streaming change for
   TXN N" — by design, but users copying this as a template
   typically want to see the data.

3. **Inconsistent txndata cleanup**: commit pfrees explicitly;
   commit_prepared / rollback_prepared don't (relies on
   ctx->context reset). Cosmetic.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | contrib/test_decoding/test_decoding.c:680 | correctness | nit | Default `Assert(false)` for unknown action; partial output in release builds | open | knowledge/files/contrib/test_decoding/test_decoding.c.md §Potential issues |
| 2026-06-11 | contrib/test_decoding/test_decoding.c:329 | leak | nit | 2PC txndata not pfree'd; relies on context cleanup at txn end | open | knowledge/files/contrib/test_decoding/test_decoding.c.md §Potential issues |
| 2026-06-11 | contrib/test_decoding/test_decoding.c:171 | leak | maybe | begin_prepare allocates txndata; filter_prepare-true mid-decode leaks | open | knowledge/files/contrib/test_decoding/test_decoding.c.md §Potential issues |
| 2026-06-11 | contrib/test_decoding/test_decoding.c:518 | style | nit | SQL_STR_DOUBLE(ch, false) ignores legacy backslash mode | open | knowledge/files/contrib/test_decoding/test_decoding.c.md §Potential issues |
| 2026-06-11 | contrib/test_decoding/test_decoding.c:765 | undocumented-invariant | nit | Text output may contain embedded NULs from binary message payloads | open | knowledge/files/contrib/test_decoding/test_decoding.c.md §Potential issues |
| 2026-06-11 | contrib/test_decoding/test_decoding.c:184-273 | style | nit | Long if-else option parser; should be a name→handler table | open | knowledge/files/contrib/test_decoding/test_decoding.c.md §Potential issues |
| 2026-06-11 | contrib/test_decoding/test_decoding.c:166 | undocumented-invariant | nit | TestDecodingData lifetime tied to ctx->context; not obvious to copy-paste authors | open | knowledge/files/contrib/test_decoding/test_decoding.c.md §Potential issues |

## Notes

test_decoding's primary value is as a reference implementation —
patches that change it touch downstream plugins by signal-effect.
Output format breakage shows up loudly because the regression
suite under `sql/` consumes the textual output directly.
