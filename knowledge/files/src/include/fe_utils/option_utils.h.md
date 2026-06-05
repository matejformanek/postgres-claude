---
path: src/include/fe_utils/option_utils.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 34
depth: read
---

# `src/include/fe_utils/option_utils.h`

- **File:** `source/src/include/fe_utils/option_utils.h` (34 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Small set of command-line-option-processing helpers shared by frontend tools: the standard
`--help`/`--version` handler, a range-checked integer parser, a `--sync-method` parser, and a
mutually-exclusive-options checker (with a variadic macro wrapper). Implementation in
[[knowledge/files/src/fe_utils/option_utils.c]]. `[from-comment]` (:1-8)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `help_handler` | :17 | Callback type for a tool's `--help` printer. |
| `handle_help_version_opts` | :19 | Early-scan argv for `--help`/`--version`, print + exit. |
| `option_parse_int` | :22 | Parse an int with min/max range check; returns success + `*result`. |
| `parse_sync_method` | :25 | Parse `--sync-method` text → `DataDirSyncMethod`. |
| `check_mut_excl_opts_internal` | :27 | Variadic: error if >1 of a set of flags is set. |
| `check_mut_excl_opts` (macro) | :30 | Ergonomic wrapper computing the arg count via `VA_ARGS_NARGS`. |

## Internal landmarks

- `handle_help_version_opts` (`:19-21`) standardizes the "`prog --help` / `prog --version`
  short-circuit before full getopt" idiom every bin tool repeats; it takes the fixed program
  name + a `help_handler` so each tool supplies only its own usage text. `[verified-by-code]`
- The `check_mut_excl_opts` macro (`:30-32`) prepends a count via `VA_ARGS_NARGS(__VA_ARGS__)
  + 2` so `check_mut_excl_opts_internal` knows how many `(name, isset)` pairs follow without a
  sentinel. `[verified-by-code]`

## Invariants & gotchas

- `option_parse_int` (`:22`) returns a bool **and** writes `*result`; callers must check the
  return before trusting `*result` — on out-of-range input it reports the error against
  `optname` and returns false. `[inferred]`
- The `check_mut_excl_opts` macro count is `+ 2` to account for the `set` and `opt` leading
  args (`:31`); editing the macro's arg shape without adjusting the constant breaks the count.
  See the in-file comment pointing at `option_utils.c` for the contract. `[from-comment]` (:29)

## Cross-refs

- Implementation: [[knowledge/files/src/fe_utils/option_utils.c]].
- `DataDirSyncMethod` lives in `common/file_utils.h` (included at `:15`).

## Potential issues

None — thin option-parsing veneer; the only subtlety (the `+2` count in the variadic macro) is
documented and stable.
