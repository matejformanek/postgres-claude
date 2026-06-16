---
path: src/interfaces/ecpg/preproc/ecpg.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 518
depth: deep
---

# `ecpg.c` — `main()` driver of the ECPG embedded-SQL preprocessor

## Purpose
This file is the entry point for the standalone `ecpg` binary, the PostgreSQL embedded-SQL precompiler that translates `.pgc` (or `.pgh` header) source containing `EXEC SQL` directives into plain `.c`/`.h` with `ecpglib` runtime calls. It owns command-line option parsing (`getopt_long`), include-path setup, the per-input-file processing loop, the boilerplate header emit (`#include <ecpglib.h>` etc.), invocation of the bison/flex front end via `base_yyparse()`, and cleanup of the global parser state between files. `[verified-by-code]` `ecpg.c:3` (file banner), `ecpg.c:129` (`main`).

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `int ret_value` | `ecpg.c:14` | Global return code; set nonzero by `mmerror`/parse failures, returned at `ecpg.c:517`. Also gates output-file deletion `ecpg.c:501`. |
| `bool autocommit` | `ecpg.c:15` | `-t`. |
| `bool auto_create_c` | `ecpg.c:16` | `-c` (and implied by `-h`). |
| `bool system_includes` | `ecpg.c:17` | `-i`. |
| `bool force_indicator` | `ecpg.c:18` | Defaults true; cleared by `-r no_indicator`. |
| `bool questionmarks` | `ecpg.c:19` | `-r questionmarks`. |
| `bool regression_mode` | `ecpg.c:20` | `--regression`. |
| `bool auto_prepare` | `ecpg.c:21` | `-r prepare`. |
| `char *output_filename` | `ecpg.c:24` | Current output path; NULL when writing to stdout. |
| `enum COMPAT_MODE compat` | `ecpg.c:26` | Default `ECPG_COMPAT_PGSQL`; set by `-C`. |
| `struct _include_path *include_paths` | `ecpg.c:28` | Head of include-search list. |
| `struct cursor *cur` | `ecpg.c:29` | Per-file cursor list (reset each file). |
| `struct typedefs *types` | `ecpg.c:30` | Per-file typedef list (reset each file). |
| `struct _defines *defines` | `ecpg.c:31` | `-D` macro list; trimmed back to cmdline state per file. |
| `struct declared_list *g_declared_list` | `ecpg.c:32` | Per-file declared-statement list. |
| `int main(int, char *const[])` | `ecpg.c:129` | The driver. Returns `ret_value` or `ILLEGAL_OPTION`. |

These globals are declared `extern` in `preproc_extern.h` (included at `ecpg.c:12`) and consumed across the preproc front end (`pgc.l`, `preproc.y`, `type.c`, etc.). `[inferred]` from the `extern` include and absence of local definition elsewhere.

## Internal landmarks
- `help(const char *progname)` `ecpg.c:34` — usage text; the `-d` line is compiled in only `#ifdef YYDEBUG` `ecpg.c:47-49`.
- `add_include_path(char *path)` `ecpg.c:67` — appends to the tail of `include_paths` (linear walk `ecpg.c:81`), preserving insertion order so search precedence matches the order added at `ecpg.c:265-269`.
- `add_preprocessor_define(char *define)` `ecpg.c:89` — parses a `-D name[=value]`; copies the arg via `mm_strdup` `ecpg.c:93` (comment at `ecpg.c:92`: don't rely on argv storage), strips spaces before `=` `ecpg.c:107`, stores `cmdvalue` pointing into the copy (no separate malloc, never freed — comment `ecpg.c:110-113`), prepends to `defines`.
- Long-option table `ecpg_options[]` `ecpg.c:132` with the single `--regression` entry mapped to sentinel `ECPG_GETOPT_LONG_REGRESSION` (`#define` `ecpg.c:128`).
- Early `--help`/`--version` short-circuit `ecpg.c:156-168` — handled before `getopt_long` so they work positionally as `argv[1]`.
- Option-parse switch `ecpg.c:171-263` — `getopt_long` spec `"cC:dD:hiI:o:r:tv"`. `-C` INFORMIX/INFORMIX_SE additionally injects the informix esql include dir `ecpg.c:181-187`; `-o -` routes output to stdout `ecpg.c:223-224`.
- Fixed include-path appends `ecpg.c:265-269`: `.`, `/usr/local/include`, the configured pkg include path, `/usr/include` — added after user `-I` dirs so user dirs win.
- Verbose early-exit `ecpg.c:271-281` — `-v` prints the search list and returns 0 without processing files.
- "No input files" guard `ecpg.c:283-288` → `ILLEGAL_OPTION`.
- Per-input-file loop `ecpg.c:292-515` — the core. Per iteration: resolve `stdin` vs filename `ecpg.c:296-326` (auto-appends `.pgc`/`.pgh` when no extension `ecpg.c:313-323`); compute output name when `-o` absent `ecpg.c:328-353`; reset all per-file global state (cursors `ecpg.c:368-390`, declared list `ecpg.c:393-399`, defines back to cmdline `ecpg.c:402-424`, typedefs `ecpg.c:427-437`, `when_*` structs `ecpg.c:440-442`, `struct_member_list` `ecpg.c:445`, `ecpg_internal_var` `ecpg.c:451`, `connection` `ecpg.c:454`); `lex_init()` `ecpg.c:457`; emit header boilerplate `ecpg.c:461-480`; `base_yyparse()` `ecpg.c:483`; warn on declared-but-unopened cursors `ecpg.c:489-491`; close files `ecpg.c:493-496`; unlink output on error `ecpg.c:501-505`.

## Invariants & gotchas
- **Per-file global reset is mandatory and order-sensitive.** All preproc state lives in process globals, so the loop must scrub cursors/defines/typedefs/`when_*`/`struct_member_list`/`connection`/`ecpg_internal_var` before each `base_yyparse()` `ecpg.c:367-454`. Skipping any reset would leak state across multiple input files in one invocation. `[verified-by-code]`
- **Defines reset keeps cmdline `-D`, drops in-source defines.** The trim loop `ecpg.c:402-424` retains entries with non-NULL `cmdvalue` (resetting `value` from `cmdvalue` `ecpg.c:409-410`) and unlinks/frees the rest. This relies on `cmdvalue` being NULL exactly for source-introduced `EXEC SQL DEFINE` entries. `[inferred]` — `add_preprocessor_define` always sets `cmdvalue` non-NULL `ecpg.c:114,119`, so the NULL case must be set by the parser elsewhere.
- **`-h` forces `-c`.** Header mode sets `auto_create_c = true` `ecpg.c:213`; the comment `ecpg.c:212` documents this is required for it to make sense.
- **`mm_alloc(strlen(argv[fnr]) + 5)`** `ecpg.c:305` — the `+5` reserves room for the `.pgc`/`.pgh` 4-char extension plus NUL appended at `ecpg.c:318-322`. The output buffer uses `+3` `ecpg.c:334` because it only rewrites the trailing extension to `.c`/`.h` `ecpg.c:337-340`.
- **Input-path extension search is separator-aware** `ecpg.c:309-310`: it finds the last dir separator first, then `strrchr` for `.` within the basename, so a dot in a parent directory name isn't mistaken for an extension.
- **`base_yyin == NULL` is not fatal** `ecpg.c:355-357`: a failed input open prints an error and skips the file but does not set `ret_value`, so the binary can still exit 0 even if an input file could not be opened. `[verified-by-code]`

## Cross-refs
- [[knowledge/files/src/interfaces/ecpg/ecpglib/misc.c.md]] — runtime side; `ECPGdebug` is the symbol macro-overridden in regression mode at `ecpg.c:478`.
- [[knowledge/files/src/interfaces/ecpg/ecpglib/connect.c.md]], [[knowledge/files/src/interfaces/ecpg/ecpglib/execute.c.md]], [[knowledge/files/src/interfaces/ecpg/ecpglib/prepare.c.md]] — the `<ecpglib.h>` runtime that the emitted `#include`s `ecpg.c:468` pull in.
- [[knowledge/files/src/interfaces/ecpg/compatlib/informix.c.md]] — `ecpg_informix.h` emitted under INFORMIX_MODE `ecpg.c:471-472`; same compat dimension as the `-C` handling `ecpg.c:178-198`.
- [[knowledge/idioms/parser-pipeline.md]] — `base_yyparse()` / `lex_init()` here are the ECPG analogue of the backend flex/bison front end.
- Sibling preproc files (not yet in corpus): `preproc_extern.h` (declares the globals defined here), `pgc.l`/`preproc.y` (the lexer/grammar driven by `base_yyparse`), `type.c`, `variable.c`, `output.c` (`output_line_number` `ecpg.c:480`).

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-correctness: `output_filename` may be NULL in the error-unlink path]** `ecpg.c:501-505` — when an input file is read from `stdin`, the `out_option == 0` branch sets `base_yyout = stdout` and leaves `output_filename` NULL `ecpg.c:330-331` (it is never assigned for stdin). If a parse error sets `ret_value != 0` for that stdin input, the cleanup block dereferences `output_filename` in `strcmp(output_filename, "-")` `ecpg.c:503` with a NULL pointer → crash. The pre-existing `output_filename` from a previous `-o` invocation does not apply because `-o` sets `out_option = 1`, skipping this block. Severity: maybe (requires stdin input + parse error + no `-o`). `[inferred]`
- **[ISSUE-leak: output `base_yyout` FILE leaked when `-o` open fails after a prior success]** `ecpg.c:221-236` — a second `-o` on the command line reassigns `base_yyout` without `fclose`-ing the previously opened stream; on failure it clears `output_filename` but the earlier successful stream (and `out_option`) handling is order-dependent. Minor, single-shot tool. Severity: nit. `[inferred]`
