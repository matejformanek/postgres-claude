# Issues — `src/tools`

Per-subsystem issue register. See `knowledge/issues/README.md` for the
tag convention, severity scale, and workflow.

**Parent subsystem doc:** (no single subsystem doc; per-file docs under
`knowledge/files/src/tools/`). Covers the developer build/format tooling:
`pg_bsd_indent` (the vendored C indenter behind `pgindent`), `ifaddrs`, etc.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-16 | src/tools/pg_bsd_indent/args.c:182-183 | correctness | maybe | `set_profile()` calls `snprintf("%s/%s", getenv("HOME"), prof)` with no NULL check; if `HOME` is unset, `%s` of NULL is UB (glibc prints "(null)", other libcs may crash). Reachable only running `pg_bsd_indent` directly with no `-P` and no `HOME` (`pgindent` always passes `-npro`). | open | knowledge/files/src/tools/pg_bsd_indent/args.c.md §Potential issues |
| 2026-06-16 | src/tools/pg_bsd_indent/indent.c:1219 | correctness | maybe | `bakcopy()` does `sprintf(bakfile, "%s.BAK", p)` into fixed `char bakfile[MAXPGPATH]` (indent.c:63); an input basename within ~4 bytes of `MAXPGPATH` overflows. Only on the in-place-edit path (input named, no output file); `pgindent` passes short temp names. Unchecked `sprintf` into a fixed buffer. | open | knowledge/files/src/tools/pg_bsd_indent/indent.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

- `pg_bsd_indent` is a vendored fork of FreeBSD `usr.bin/indent` (version
  `2.1.3`). Both findings above are inherited-from-upstream latent issues in a
  developer-only batch tool, not backend code; severity is `maybe` because the
  vulnerable paths are not exercised by `pgindent`'s invocation (`-npro`, short
  temp filenames). They are recorded for completeness, not as action items.
- The directory's heuristics (single forward pass, limited lookahead) mean most
  "pgindent did something weird" reports are *behavioural*, not bugs — see the
  per-file docs' gotchas (box-comment detection, `is_func_definition` K&R blind
  spot, `specials[]`/`typenames[]` sort invariants).
