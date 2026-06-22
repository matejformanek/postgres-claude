---
path: src/tools/pg_bsd_indent/args.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 350
depth: deep
---

# `src/tools/pg_bsd_indent/args.c` — option table, profile reading, defaults

## Purpose

Command-line and `.indent.pro` profile parsing for `pg_bsd_indent`, plus the
master option table `pro[]` that maps every `-xx` flag to its target global and
default. `set_defaults()` seeds the globals from `pro[]`; `set_option()` applies
one flag; `set_profile()` reads `$HOME/.indent.pro` and `./.indent.pro`. Also
loads typedef lists (`-U file`). Defines `INDENT_VERSION` (`"2.1.3"`,
args.c:54).

## Public symbols

| Symbol | Lines | Role |
|---|---|---|
| `pro[]` | 86-169 | The option table: `{name, type, default, special, &target}`. |
| `set_profile(const char *)` | 175-195 | Read the two `.indent.pro` files. |
| `set_defaults(void)` | 245-258 | Assign every non-special option its `p_default`. |
| `set_option(char *)` | 260-332 | Parse and apply one `-xx[param]` flag. |
| `add_typedefs_from_file(const char *)` | 334-350 | Load type names from a `-U` file (one per line). |

File-scope: `scan_profile()` (static, args.c:197-230), `eqin()` prefix-match
helper (args.c:232-240), `option_source` (args.c:76).

## Internal landmarks

- **`pro[]` ordering rule** (args.c:80-85): because `set_option` matches by
  prefix via `eqin`, any option whose name is a *substring* of another must come
  later in the table (e.g. `-lp` before `-l`, `-lpl` before `-lp`). The defaults
  are also applied in table order, so the *last* default for a repeated boolean
  wins. `[from-comment]`
- **Profile/special types** (args.c:56-74): `PRO_BOOL` flips a flag to ON/OFF;
  `PRO_INT` `atoi`s a parameter; `PRO_SPECIAL` dispatches on `p_special`
  (`IGN`, `CLI` case-label-indent float, `STDIN`, `KEY` add-typename,
  `KEY_FILE` load-typedefs, `VERSION` print-and-exit).
- **PG additions** in the table: `-tpg`/`-ntpg` → `postgres_tab_rules`
  (args.c:153,163) and `-sac`/`-nsac` → `space_after_cast`. These plus the
  in-tree defaults are what `pgindent` actually passes.
- `add_typedefs_from_file` (args.c:334-350) trims each line at the first
  whitespace (`strcspn(line, " \t\n\r")`) before `add_typename` — this is how
  `pgindent` feeds `src/tools/pgindent/typedefs.list`.

## Invariants & gotchas

- **Substring options must stay after their superstrings in `pro[]`.** Reordering
  the table without honouring this silently mis-parses flags. `[from-comment]`
- **`-version`/`-U`/`-T` are special-cased before the generic loop**; they carry
  their parameter inline (`param_start = eqin(name, arg)`), so `-Tmytype`,
  `-Ufile`, not `-T mytype`.
- `set_defaults` cannot initialise `ps.case_indent` from the table because it is
  a `float`, so it is set explicitly to `0.0` first (args.c:251-254). A new
  float option would need the same treatment. `[from-comment]`

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/indent_globs.h]] — every `&target` in `pro[]`.
- [[knowledge/files/src/tools/pg_bsd_indent/lexi.c]] — `add_typename` (the `-T`/`-U` sink).
- `src/tools/pgindent/` — the wrapper that supplies the flags + `typedefs.list`.

## Potential issues

- **[ISSUE-correctness: `getenv("HOME")` used without NULL check]**
  `args.c:182-183` — `set_profile()` does
  `snprintf(fname, sizeof(fname), "%s/%s", getenv("HOME"), prof)` when no `-P`
  profile is given. If `HOME` is unset, `getenv` returns `NULL` and a `%s` of
  `NULL` is undefined behaviour (glibc prints "(null)", other libcs may crash).
  Reachable only when running `pg_bsd_indent` directly with no `-P` and no
  `HOME` — `pgindent` always passes `-npro`, so this is latent. Low severity for
  a dev tool, but a genuine unchecked-`getenv` deref. See
  `knowledge/issues/tools.md`.
