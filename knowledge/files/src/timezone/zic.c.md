---
path: src/timezone/zic.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 4022
depth: read
---

# src/timezone/zic.c

## Purpose

The **zone-information compiler** — a standalone command-line tool that reads
IANA `.zi` source files (the `Rule`/`Zone`/`Link`/`Leap` text database) and
emits the compiled TZif binary files that `localtime.c::tzload` later reads at
runtime. A near-verbatim copy of upstream tzcode `zic.c`, built as a frontend
program (`#include "postgres_fe.h"`, `zic.c:11`). PG ships it so the build can
compile the bundled `tzdata` into `<sharedir>/timezone/` during `make`/`ninja`;
it is **not** part of any running backend. Lowest runtime-relevance of the
`src/timezone` files, but it is the producer side of the TZif trust boundary
that `localtime.c` consumes. `[verified-by-code]`

## Public symbols

| Symbol | Site | Role |
|---|---|---|
| `int main(int argc, char **argv)` | `zic.c:680` | Entry point; parses options, reads input files, links/compiles zones |

Everything else is `static`. `zic --version` prints `PG_VERSION` (`:701`), not
the upstream zic version — a PG-local patch.

## Internal landmarks

- **Option parsing** (`zic.c:709-815`): `-d outdir` (default `data`), `-l`/`-p`
  (localtime / posixrules links), `-L leapsecfile`, `-t tzdefault`, `-b
  slim|fat` (data-size mode), `-r timerange`, `-v` (noise/lint), `-P` (print
  abbrevs). Duplicate single-value options are hard errors.
- **Input model**: `infile` (`:1271`) tokenizes each line via `getfields`
  (`:3722`) and dispatches by leading keyword to `inrule`/`inzone`/`inzcont`/
  `inlink`/`inleap`/`inexpires` (`:1482-1832`). Parsed records accumulate in the
  global `rules`/`zones`/`links` arrays (`:290-306`).
- **`associate`** (`:1186`) — binds each zone's rule-name to its `struct rule`
  set, sorting rules with `rcomp` (`:1179`).
- **`outzone`** (`:2949`) — the heart: for each zone, materializes the full
  transition list across the rule years, then calls `writezone`.
- **`writezone`** (`:2084`) — serializes the in-memory transitions into the TZif
  on-disk format (the 32-bit then 64-bit blocks + the trailing POSIX TZ string
  via `stringzone`, `:2814`). The exact inverse of `localtime.c::tzloadbody`.
- **`dolink`** (`:1032`) — implements `Link`: tries hard link
  (`hardlinkerr`/`linkat`, `:1023`), falls back to symlink (`relname` computes a
  relative target, `:977`), then to copying file contents.
- **`gethms`/`rpytime`/`tadd`/`oadd`** (`:1380,3806,3777,3769`) — the
  time-arithmetic helpers, all overflow-checked (`time_overflow` → fatal,
  `:3762`).
- **`emalloc`/`erealloc`/`growalloc`** (`:452-491`) — die-on-OOM allocators
  (`memory_exhausted` → `EXIT_FAILURE`, `:418`); standard for a build tool.

## Invariants & gotchas

- **`namecheck` is the path-traversal gate for output file names**
  (`zic.c:928-967`, helper `componentcheck` `:885`). It rejects empty names,
  leading `/` ("begins with '/'"), `//`, trailing `/`, and any `.`/`..` path
  component (`:906-914`). Because zone names become output file paths under
  `-d`, this is what stops a malicious `.zi` from writing outside the target
  directory. The producer-side analogue of `pgtz.c::scan_directory_ci`'s
  `.`-skip on the consumer side.
- **Conservative umask** (`zic.c:689`): `umask(umask(S_IWGRP|S_IWOTH) |
  (S_IWGRP|S_IWOTH))` forces group/other write bits off — "a fair chance of
  root running us" (`:1039-1041`). New directories use `MKDIR_UMASK` (0755-ish,
  `:37`).
- **Requires 64-bit `zic_t`** — `main` aborts immediately if
  `TYPE_BIT(zic_t) < 64` (`:692-697`).
- **TZif version** is `ZIC_VERSION '3'` (`:23`); `-b slim` vs `fat` controls
  whether pre-1970 / far-future transitions are emitted in full (affects file
  size, not runtime correctness). PG's default is set by `ZIC_BLOAT_DEFAULT`
  (`:818-828`).
- Build-time only: errors call `error`/`warning` and bump an exit status; this
  is not a backend code path, so its `ereport`-free, `exit()`-based error model
  is correct here (do **not** "convert to ereport").

## Potential issues

- **[ISSUE-undocumented-invariant: TZif trust boundary is producer-validated
  here, consumer-revalidated in localtime.c]** `zic.c:928` (`namecheck`) +
  `zic.c:2084` (`writezone`) — `zic` is trusted to emit well-formed TZif with
  safe names, and `localtime.c::tzloadbody` independently re-validates the
  binary on load (counts, indices, monotonic transitions). The corpus should
  note the pairing: a hand-crafted TZif placed in the timezone dir bypasses
  `zic` entirely, so the *load-side* checks in `localtime.c` are the real
  security boundary, not `zic`'s name/format checks. Documenting the split is
  the fix. Severity: nit (informational).

## Cross-refs

- `knowledge/files/src/timezone/localtime.c.md` — the runtime consumer;
  `tzloadbody` is the inverse of `writezone` and re-validates `zic`'s output.
- `knowledge/files/src/timezone/tzfile.h.md` — the shared on-disk format
  constants both sides obey.
- `knowledge/files/src/timezone/private.h.md` — the arithmetic/limit macros.
- `knowledge/files/src/timezone/pgtz.c.md` — runtime zone-dir scanning, the
  consumer-side path-traversal guard (`scan_directory_ci`).
