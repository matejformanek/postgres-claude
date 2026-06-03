# `src/backend/utils/adt/regexp.c`

## Purpose

SQL-level façade around `src/backend/regex/` (Spencer's regex
engine). Provides `LIKE`-style regex operators (`~`, `~*`, `!~`,
`!~*`), `substring(text from pattern)`, `regexp_replace`,
`regexp_match`, `regexp_matches` (set-returning), `regexp_split_to_array`,
`regexp_split_to_table`, `regexp_count`, `regexp_instr`,
`regexp_substr`, `regexp_like`. Maintains a 32-entry per-backend
self-organising LRU cache of compiled `regex_t` to avoid recompiling
on every call. 2081 lines.

## Key functions

- `RE_compile_and_cache` — `regexp.c:141`. Linear scan of
  `re_array[MAX_CACHED_RES]` (32 slots); move-to-front on hit. Per-RE
  AllocSet child of `RegexpCacheMemoryContext` so failed compiles
  clean up via context destruction. Calls `pg_regcomp` from
  `regex/regcomp.c`.
- `parse_re_flags` — flag-string parser ('g'=global, 'i'=icase,
  'x'=expanded, 's'=singleline, 'n'=newline-sensitive, etc.). Maps
  to Spencer engine `cflags`.
- `RE_execute`, `RE_wchar_execute` — `pg_regexec` wrappers; convert
  haystack to `pg_wchar` first.
- `setup_regexp_matches`, `build_regexp_match_result` — populate the
  `regexp_matches_ctx` SRF state.
- SQL operator entry points: `textregexeq`, `textregexne`,
  `texticregexeq` (case-insensitive) — `:486+`. `nameregexeq` and
  family — `:458+` — for `name` type comparisons.
- `textregexreplace`, `textregexreplace_extended` — `:657`, `:699`.
  Replacement-string `\n` backref handling.
- `regexp_matches`, `regexp_split_to_array`, `regexp_split_to_table` —
  SRFs.

## Phase D notes

The regex engine itself is the actual DoS surface (catastrophic
backtracking, complex bounded quantifiers). This file's only
contribution to that risk is the **per-call entry point** — every
SQL row evaluation eventually calls `pg_regexec`, which honours
`CHECK_FOR_INTERRUPTS` at intervals (see
`knowledge/files/src/backend/regex/regexec.c.md`).

Cache scope: 32 entries per backend. Crafted workloads with >32
distinct never-reused patterns force recompile every call (cache
miss eviction at front-insertion — `:79-82` comment explains the
design rationale).

Replacement-string parsing (`appendStringInfoRegexpSubstr` etc.)
handles `\&` and `\N` backrefs. The number of backrefs is bounded
by what the compiled regex captured; no count cap beyond that.

Flag-string parser tolerates unknown flags **silently for some**
historically; check `parse_re_flags`. `[unverified]` — would
need a closer read of the flag table.

## Potential issues

- [ISSUE-dos: 32-entry LRU cache is per-backend and not configurable
  via GUC. Workloads with churning patterns (>32 distinct) pay full
  compile cost per call. Not a security issue, but a knob worth
  considering. (low)] — `regexp.c:95` (`MAX_CACHED_RES`)
- [ISSUE-dos: Cached compiled regexes never expire; long-lived
  backends accumulate up to 32 patterns from the last million
  queries. Memory under `RegexpCacheMemoryContext` grows only with
  *distinct* patterns (bounded), so this is bounded leak-style, not
  unbounded. (low)] — `regexp.c:99`
- [ISSUE-undocumented-invariant: `re_array` is a static C array
  shared by all uses in this backend — there's no concurrency
  concern (single-threaded backend) but extensions calling
  `RE_compile_and_cache` from a bgworker / parallel worker each get
  their own cache copy; documented nowhere visible. (low)]
- [ISSUE-correctness: `regexp_match` (singular) vs `regexp_matches`
  (set-returning, global flag) is a frequent user-facing footgun;
  documented in user manual but not in this file. (n/a)]
