# `src/backend/utils/misc/tzparser.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~487
- **Source:** `source/src/backend/utils/misc/tzparser.c`

Parses the timezone-abbreviation override files installed under
`SHAREDIR/timezonesets/` (e.g. `Default`, `Australia`, `India`). The
parser is invoked from the GUC `check_hook` for
`timezone_abbreviations`, so it follows the "report via
`GUC_check_errmsg`, avoid raising ERROR" convention. Returns a
populated `TimeZoneAbbrevTable *` that `datetime.c` then consults
during text-to-timestamp conversions. [verified-by-code] [from-comment]

## API / entry points

- `load_tzoffsets(const char *filename)` — public entry. Allocates a
  temp `AllocSet` ("TZParserMemory"), kicks off `ParseTzFile` at
  depth 0, then hands the result to `ConvertTimeZoneAbbrevs` for
  guc_malloc'd packing. Returns NULL on parse failure; caller reads
  `GUC_check_errmsg` for the reason. [verified-by-code]

## Internals (file-scope static)

- `validateTzEntry(tzentry)` — bound checks: abbrev length ≤
  `TOKMAXLEN`, offset within ±14 hours. Lowercases the abbrev to
  match `datetime.c`'s `datetktbl` convention. [verified-by-code]
- `splitTzLine(filename, lineno, line, tzentry)` — tokeniser using
  `strtok_r` with `WHITESPACE` separators. Accepts two forms:
  - `abbrev zone_name [comment]`
  - `abbrev offset [D] [comment]` where offset is signed seconds
  Detects which by looking at the first character of the second
  token (digit or sign → offset; else zone name). [verified-by-code]
- `addToArray(base, arraysize, n, entry, override)` — binary search
  by `strcmp(abbrev)`, doubling `repalloc` on overflow. On duplicate
  abbrev with same value, no-op; on duplicate with different value:
  override if `@OVERRIDE` was seen in the current file, else error.
  [verified-by-code]
- `ParseTzFile(filename, depth, base, arraysize, n)` — opens
  `SHAREDIR/timezonesets/<filename>` after sanity-checking that
  `filename` is alphabetic-only ("we don't want to allow access to
  anything outside the timezonesets directory, so for instance '/'
  *must* be rejected"). Handles `@INCLUDE` (recurse, depth-limit 3)
  and `@OVERRIDE` (toggle override for this file's remaining lines).
  [verified-by-code] [from-comment]

## Notable invariants / details

- **Path-traversal hardening:** the alpha-only filename check (line
  296-306) blocks `/`, `..`, NUL injection, and unicode. This is the
  load-bearing defense for the `@INCLUDE` directive — without it a
  malicious timezoneset file could pull arbitrary readable files
  into the parse. [verified-by-code] [from-comment]
- **Depth limit 3:** prevents `@INCLUDE` recursion bombs. Comment
  calls it "pretty arbitrary"; hardcoded. [verified-by-code]
- **Line length 1023:** `tzbuf[1024]` plus the
  `strlen(tzbuf) == sizeof(tzbuf)-1` overflow check (lines 375-382).
  Lines longer than ~1023 chars fail with "line is too long" rather
  than being silently truncated. [verified-by-code]
- **OOM caveat in header comment:** "in particular out-of-memory will
  throw an error. Could probably fix with PG_TRY if necessary." —
  the check_hook contract is to **not** raise ERROR, but `palloc` /
  `pstrdup` /`repalloc` can; not boxed in a `PG_TRY`. [verified-by-code]
  [from-comment] [ISSUE-stale-todo: header openly admits OOM-via-ereport
  escape from the no-ERROR contract (nit)]
- **Override semantics:** `@OVERRIDE` is per-file, sticky for the
  remainder of that file, **not reset on `@INCLUDE` return**. This
  means: file A says `@OVERRIDE`, A includes B, B's entries override
  prior values silently. Probably intentional but undocumented in
  the file. [verified-by-code] [ISSUE-undocumented-invariant: override
  flag scope across @INCLUDE is subtle (maybe)]
- **Insertion sort via `memmove`:** `addToArray` does a binary
  *search* but a linear *insert* (`memmove` at line 258). O(n²) for
  N entries. With ~250 entries in `Default` this is invisible.
  [verified-by-code]
- **`strtol(offset, &offset_endptr, 10)` accepts a leading sign** but
  the surrounding `isdigit() || == '+' || == '-'` gate guarantees we
  only enter the offset branch when expected. No octal/hex
  surprises (radix 10). [verified-by-code]
- The `ConvertTimeZoneAbbrevs` callee (in `datetime.c`) is where the
  result memory is `guc_malloc`'d; if it returns NULL the parser
  treats it as OOM and reports via `GUC_check_errmsg`. [verified-by-code]
- `AllocateFile` / `AllocateDir` are used (not `fopen`/`opendir`)
  so the FD count is tracked against `max_files_per_process`. [verified-by-code]

## Potential issues

- File-line: tzparser.c:9-12. Header openly acknowledges OOM can
  ERROR out of a check_hook — violates the no-ERROR convention.
  Long-standing TODO. [ISSUE-stale-todo: OOM path escapes check_hook
  no-ERROR convention (maybe)]
- File-line: tzparser.c:294-306. Filename alpha-only check is the
  only defense for `@INCLUDE` against path traversal. If someone
  ever relaxes this (to allow underscores or numbers), they must
  re-audit `@INCLUDE` for `..`/symlink escape. [ISSUE-undocumented-invariant:
  path-traversal defense is one line, easily relaxed (maybe)]
- File-line: tzparser.c:415-419. `@OVERRIDE` flag is sticky and
  persists across `@INCLUDE` recursion in the *current file*. Worth
  a code comment. [ISSUE-undocumented-invariant: @OVERRIDE scope
  vs @INCLUDE recursion (nit)]
- File-line: tzparser.c:250-263. Insertion sort `memmove` is O(n²);
  fine at current sizes but if someone adds a TZ database dump
  (~1000+ entries), parse time scales quadratically. [ISSUE-style:
  quadratic insertion sort, acceptable today (nit)]
- File-line: tzparser.c:117, 159, 397. Multiple `pstrdup` allocations
  in the temp context — leaked if the temp context is reset, but
  `load_tzoffsets` deletes the context after `ConvertTimeZoneAbbrevs`,
  so they vanish. Safe. [ISSUE-leak: no leak in current flow (nit)]
