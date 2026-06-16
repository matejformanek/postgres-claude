---
path: src/interfaces/ecpg/preproc/util.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 264
depth: deep
---

# `util.c` — ecpg preprocessor utility helpers (error reporting, allocators, string builders)

## Purpose
The grab-bag of support routines used throughout the ecpg preprocessor:
error/warning reporting (`mmerror`/`mmfatal`), the OOM-fatal malloc wrappers
(`mm_alloc`/`mm_strdup`), an arena-style "local" allocator that batches the
many tiny allocations made while processing a single SQL statement
(`loc_alloc`/`loc_strdup`/`reclaim_local_storage`), and the
`cat*_str`/`make*_str` string-concatenation builders the grammar uses to
assemble output fragments. The local allocator and the string builders are
tightly coupled: the builders return transient storage that is reclaimed in
bulk at end of statement. `[verified-by-code]` (whole file)

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `mmerror` | `util.c:49` | Report an error or warning; varargs wrapper over `vmmerror`. `[verified-by-code]` |
| `mmfatal` | `util.c:60` | Report an error and abandon execution: closes files, unlinks the output file, `exit(error_code)`. `[verified-by-code]` |
| `mm_alloc` | `util.c:84` | `malloc` + check; calls `mmfatal(OUT_OF_MEMORY, ...)` on NULL — never returns NULL. `[verified-by-code]` |
| `mm_strdup` | `util.c:96` | `strdup` + check; same OOM-fatal contract. `[verified-by-code]` |
| `loc_alloc` | `util.c:137` | Arena allocator; carves from a chunk list, mallocs a new chunk on demand. Exits on OOM (via `mm_alloc`). `[verified-by-code]` |
| `loc_strdup` | `util.c:169` | `strdup` into local/arena storage. `[verified-by-code]` |
| `reclaim_local_storage` | `util.c:181` | Frees the entire chunk list; call at end of each statement cycle. `[verified-by-code]` |
| `cat2_str` | `util.c:204` | Concatenate 2 strings with a space separator (unless either is empty). `[verified-by-code]` |
| `cat_str` | `util.c:219` | Concatenate N strings (varargs) via repeated `cat2_str`. `[verified-by-code]` |
| `make2_str` | `util.c:242` | Concatenate 2 strings, no separator. `[verified-by-code]` |
| `make3_str` | `util.c:255` | Concatenate 3 strings, no separator. `[verified-by-code]` |

## Internal landmarks
- `vmmerror(int, enum errortype, const char *, va_list)` — `util.c:15`: the
  shared core. Localizes the message with `_()` (`util.c:19`), prints
  `file:line` prefix (`util.c:21`), a `WARNING:`/`ERROR:` tag
  (`util.c:23`-`util.c:31`), then `vfprintf`s the message. For `ET_ERROR` it
  sets the global `ret_value = error_code` (`util.c:43`) which `ecpg.c`
  inspects. Declared `pg_attribute_printf(3, 0)` at `util.c:9`. `[verified-by-code]`
- `struct loc_chunk` — `util.c:118`: singly-linked chunk with
  `chunk_used`/`chunk_avail` counters and a `FLEXIBLE_ARRAY_MEMBER` data
  region. `[verified-by-code]`
- `LOC_CHUNK_OVERHEAD` / `LOC_CHUNK_MIN_SIZE` — `util.c:126`-`util.c:127`:
  per-chunk header overhead (MAXALIGNed) and the 8192-byte minimum chunk
  size. `[verified-by-code]`
- `loc_chunks` — `util.c:130`: static head of the chunk list (the arena's
  only state). `[verified-by-code]`

## Invariants & gotchas
- **`mm_alloc`/`mm_strdup` never return NULL.** On allocation failure they
  call `mmfatal(OUT_OF_MEMORY, "out of memory")` which `exit()`s
  (`util.c:89`-`util.c:90`, `util.c:101`-`util.c:102`). Callers therefore do
  *not* null-check — this is the load-bearing contract of the file. Any new
  caller must rely on this and must not "defensively" recheck. `[verified-by-code]`
- **`mmfatal` is terminal and has side effects.** It closes `base_yyin`/
  `base_yyout` if open (`util.c:69`-`util.c:72`) and unlinks the output file
  unless it is `"-"` (`util.c:74`-`util.c:75`) before `exit(error_code)`
  (`util.c:76`). Do not call it for recoverable conditions. `[verified-by-code]`
- **`vmmerror` only records ret_value for errors.** Warnings print but leave
  `ret_value` untouched (`util.c:40`-`util.c:45`), so a run with only
  warnings still exits successfully. `[verified-by-code]`
- **Arena alignment.** `loc_alloc` MAXALIGNs the requested size
  (`util.c:144`) so every returned pointer is adequately aligned; the chunk
  also reserves `LOC_CHUNK_OVERHEAD - offsetof(...)` bytes of slack at the
  front (`util.c:153`). `[verified-by-code]`
- **Arena freeing is all-or-nothing.** There is no per-allocation free;
  `reclaim_local_storage` frees the whole list and resets `loc_chunks = NULL`
  (`util.c:181`-`util.c:193`). Anything handed out by `loc_alloc`/
  `loc_strdup`/`cat*_str`/`make*_str` is invalid after the reclaim. Holding a
  pointer across statement boundaries is a use-after-free. `[from-comment]`
  (`util.c:108`-`util.c:116`)
- **New-chunk sizing.** A request larger than the current chunk's
  `chunk_avail` triggers a fresh chunk of `Max(size, LOC_CHUNK_MIN_SIZE)`
  (`util.c:147`-`util.c:154`); large single requests get their own
  appropriately sized chunk, so the arena never silently truncates. `[verified-by-code]`
- **`cat2_str` space rule.** A space is inserted only when *both* inputs are
  non-empty (`util.c:210`-`util.c:211`); the `+2` in the alloc covers the
  separator and the NUL (`util.c:207`). `make2_str`/`make3_str` use `+1`
  (no separator). `[verified-by-code]`

## Cross-refs
- [[output.c]] — primary consumer of `loc_alloc` (`hashline_number`) and the
  `cat*_str`/`make*_str` builders that produce the `stmt` text it emits.
- [[ecpg.c]] — sets `input_filename`/`output_filename`/`base_yylineno`,
  owns `base_yyin`/`base_yyout`, and reads `ret_value` as the process exit
  status.
- [[error-handling]] (idiom) — the ecpg-side analogue of the backend
  `ereport`/`elog` discipline: `mmerror`/`mmfatal` + `ET_WARNING`/`ET_ERROR`
  + `OUT_OF_MEMORY` error code. Note ecpg is *frontend* code (`postgres_fe.h`
  at `util.c:3`), so it uses `malloc`/`exit`, not backend `palloc`/`ereport`.
- [[type.c]], [[variable.c]] — heavy users of `mm_alloc`/`mm_strdup` and the
  string builders.
- `preproc_extern.h` — declares the prototypes and the globals
  (`input_filename`, `output_filename`, `base_yylineno`, `base_yyin`,
  `base_yyout`, `ret_value`, `enum errortype`).

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-robustness: `cat_str` does not validate `count` against varargs]** `util.c:219` — `cat_str`
  reads `count` arguments via `va_arg` with no NULL-terminator sentinel; a
  miscounted call walks past the provided arguments (undefined behavior).
  This is the standard varargs contract and every in-tree caller is grammar-
  generated, so it is not a live bug — flagged only as a fragility note for
  hand-written callers. Severity: info. `[inferred]`
- **No unbounded-buffer analogue to the ecpglib runtime findings.** The
  `cat*_str`/`make*_str` builders each size the destination with explicit
  `strlen(...)` sums before `strcpy`/`strcat` (`util.c:207`, `util.c:245`,
  `util.c:258`), so there is no fixed-size stack/heap buffer to overflow here
  — unlike the runtime-side `sprintf`-into-fixed-buffer patterns. No issue.
  `[verified-by-code]`
