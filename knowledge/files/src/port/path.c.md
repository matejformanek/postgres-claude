---
path: src/port/path.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 1165
depth: deep
---

# src/port/path.c

## Purpose

The PG-wide pathname toolkit: canonicalization, separator handling, relative/
absolute conversion, the `get_*_path` family that derives install directories
(share, lib, etc, locale, …) from the running executable's location, and — most
security-relevant — the helpers that decide whether a path is **safe for
archive extraction** (no escape above the cwd). Frontend and backend both link
it. Several of its functions are the trust chokepoints the A3/A4/A6/A7 sweeps
repeatedly cite as the place to validate untrusted, server- or archive-supplied
path strings. `[verified-by-code]`

## Public symbols (selected)

| Symbol | Site | Role |
|---|---|---|
| `first_dir_separator` / `last_dir_separator` | `path.c:110` / `:145` | Locate `/` (or `\` on Win32) in a filename |
| `first_path_var_separator` | `path.c:127` | Locate the PATH-list separator (`:` / `;`) |
| `make_native_path` | `path.c:236` | Convert `/` → `\` on Win32 |
| `canonicalize_path` / `canonicalize_path_enc` | `path.c:337` / `:344` | Collapse `.`, `..`, redundant separators, trailing slash |
| `path_contains_parent_reference` | `path.c:577` | True if a canonicalized path still begins with `..` |
| `path_is_relative_and_below_cwd` | `path.c:604` | True iff relative and cannot escape the cwd |
| `path_is_safe_for_extraction` | `path.c:637` | **The archive-extraction gate**: canonicalize then check no parent refs |
| `path_is_prefix_of_path` | `path.c:654` | Directory-aware prefix test |
| `get_progname` | `path.c:669` | Strip directory + `.exe` from argv[0] |
| `make_relative_path` | `path.c:755` | Relocate an install path relative to the exe |
| `make_absolute_path` | `path.c:824` | Resolve a relative path against cwd |
| `get_share_path` … `get_man_path` | `path.c:919-1018` | Derive install subdirs from `my_exec_path` |
| `get_home_path` | `path.c:1022` | `$HOME` (getpwuid fallback) |
| `get_parent_directory` | `path.c:1085` | Strip the last component in place |

## Internal landmarks

- `canonicalize_path_enc` (`path.c:344-575`) — the workhorse: on Win32 converts
  backslashes first (`:355-360`), then collapses `//`, `./`, and `dir/..`
  pairs, tracking `pathdepth` so it never collapses a leading `..` that would
  change meaning. Encoding-aware so it doesn't split a multibyte trailing byte
  that looks like a separator (the SJIS handling via `pg_sjis_mblen`, `:202`).
- `skip_drive` (`path.c:69`) — Win32 drive/UNC prefix skip, used by the
  parent-reference check so `C:..` is judged on its component, not the drive.
- The `get_*_path` family all funnel through `make_relative_path` /
  `append_subdir_to_path`, so a relocated install tree (binaries moved) still
  finds its `share/`, `lib/`, etc. relative to the executable.

## Invariants & gotchas

- **`path_is_safe_for_extraction` is the canonical extraction guard.** It copies
  into a `MAXPGPATH` stack buffer, runs `canonicalize_path`, then
  `path_is_relative_and_below_cwd` (`path.c:637-645`). The whole correctness
  argument rests on **canonicalization happening first**: `path_contains_parent_
  reference` only inspects the *start* of the path (`:585-590`) because, post-
  canonicalization, an absolute path can hold no `..` at all and a relative one
  can hold `..` only at the front (`:579-583`). Feeding it a non-canonicalized
  path would defeat the check — callers must not skip the canonicalize step.
- This guard prevents `../` **path components**; it does **not** call
  `O_NOFOLLOW` or `realpath`, so it does not defend against a *symlink* planted
  inside the extraction tree. That symlink-following concern is the A6 pg_rewind
  / pg_upgrade finding and lives at the `open`/`mkdir` call sites, not here.
- `canonicalize_path` assumes server-safe encoding (`PG_SQL_ASCII`); the `_enc`
  variant exists for callers that must respect a specific client encoding when
  deciding separator boundaries.
- `get_progname` strips a trailing `.exe`/`.EXE` on Win32 (`:669-705`) — relied
  on for consistent program-name reporting in errors.

## Potential issues

- **[ISSUE-undocumented-invariant: extraction-safety depends on prior
  canonicalization]** `path.c:577-645` — `path_contains_parent_reference`
  only checks the leading component and is correct *only* if its input was
  already canonicalized. `path_is_safe_for_extraction` enforces this by
  canonicalizing internally, but any caller that invokes
  `path_is_relative_and_below_cwd` / `path_contains_parent_reference`
  **directly** on un-canonicalized input gets a wrong answer. The precondition
  is in comments (`:598`, `:580-583`) but not asserted. Severity: maybe — worth
  an `Assert` or a note for the Phase-D path-traversal hardening pitch. See
  `knowledge/issues/port.md`.

## Cross-refs

- `knowledge/issues/pg_rewind.md`, `knowledge/issues/pg_upgrade.md` — the
  symlink-following (`O_NOFOLLOW`) gap that this file does *not* close (A6).
- `knowledge/files/src/port/pgmkdirp.c.md` — consumes canonicalized paths.
- `knowledge/files/src/fe_utils/astreamer_tar.c.md` — extraction caller (A11).
