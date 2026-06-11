# Issues — `contrib/auto_explain`

Per-subsystem issue register for **auto_explain**, the 1-file
backend extension that hooks the four Executor* hooks to log
slow-query EXPLAIN plans. Created 2026-06-11 by A21 sweep.

**Parent doc:** `knowledge/files/contrib/auto_explain/auto_explain.c.md`

## Headlines

1. **Full bind-parameter values are logged by default**
   (`auto_explain.c:455-456`). `log_parameter_max_length = -1` is
   "log in full". The single biggest PII / data-leak surface in
   the extension; relevant to A21 Phase D data-leak hardening.

2. **`log_level` is a GUC** (`auto_explain.c:252-262`). A
   misconfigured site that raises it to NOTICE or WARNING surfaces
   the entire plan + parameters to the client, not just the server
   log. `errhidestmt(true)` does not hide the errmsg body.

3. **Hand-rolled mini-parser for `log_extension_options`**
   (`auto_explain.c:662-829`). ~170 LOC of in-place string mangling
   intended to match the main EXPLAIN option parser "close enough".
   Divergences include no `100_000` digit-separator support.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | contrib/auto_explain/auto_explain.c:455-456 | security | likely | Full bind parameter values logged by default; PII risk on shared loggers | open | knowledge/files/contrib/auto_explain/auto_explain.c.md §Potential issues |
| 2026-06-11 | contrib/auto_explain/auto_explain.c:483-490 | security | maybe | log_level >= NOTICE surfaces plan+params over the wire to clients | open | knowledge/files/contrib/auto_explain/auto_explain.c.md §Potential issues |
| 2026-06-11 | contrib/auto_explain/auto_explain.c:474-479 | style | nit | JSON output produced by string-bracket fixup is fragile | open | knowledge/files/contrib/auto_explain/auto_explain.c.md §Potential issues |
| 2026-06-11 | contrib/auto_explain/auto_explain.c:530-532 | style | nit | OOM in GUC check hook reported as generic "invalid value" | open | knowledge/files/contrib/auto_explain/auto_explain.c.md §Potential issues |
| 2026-06-11 | contrib/auto_explain/auto_explain.c:438-449 | stale-todo | nit | "/* No support for MEMORY */" dead comment | open | knowledge/files/contrib/auto_explain/auto_explain.c.md §Potential issues |

## Notes

The PII story here is the headline: `auto_explain` is the single
most-deployed contrib extension that emits user-data byte-for-byte
to the server log. A14-class finding ("contrib that exposes data
to a lower-privilege observer than the table's GRANTs"). Worth a
shared-with-pg_stat_statements pattern doc.
