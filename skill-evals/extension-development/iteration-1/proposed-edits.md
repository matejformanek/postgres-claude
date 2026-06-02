# Proposed edits to SKILL.md — iteration 1

Not applied. Listed in priority order.

## 1. Clarify "meson is only for contrib/" wording

Current §2 says:

> `meson.build`               # in-tree meson build (only needed for contrib/)

This is slightly misleading. Meson *can* be used out-of-tree (some
third-party extensions do), but PGXS is the ecosystem norm. Suggest:

> `meson.build`               # only for in-tree contrib/ builds; out-of-tree
>                             # extensions use PGXS (Makefile)

And in §2's "Two build paths" preamble, add one line:

> Out-of-tree extensions overwhelmingly use PGXS. The in-tree meson path is
> reserved for `source/contrib/*` — third-party extensions targeting meson
> directly are rare and unsupported by the official extension docs.

## 2. Surface Extension_control_path GUC (PG 18+)

`knowledge/files/src/backend/commands/extension.c.md` notes that PG 18
added `Extension_control_path` to let admins override
`<sharedir>/extension/`. This isn't in SKILL.md. Worth a one-liner in §2
or §10:

> Since PG 18, the admin GUC `Extension_control_path` can override the
> default `<sharedir>/extension/` lookup directory — useful for installing
> extensions to non-standard locations without a custom build of PG.

## 3. Add an "extensions with no SQL functions" callout

auto_explain is mentioned but the pattern "extension that has a control
file + .so + tiny SQL script and no CREATE FUNCTION at all" isn't called
out as a first-class case. A new short subsection under §1, or a sentence
in §3 "Lazy load vs shared_preload_libraries":

> Pure-hook extensions (auto_explain, pg_stat_statements partial) ship a
> near-empty `<ext>--1.0.sql` containing only the `\echo … \quit` header.
> Everything they do is wired up by `_PG_init` once loaded via
> `shared_preload_libraries`. The control file + `.so` are still required.

## 4. Promote the "_PG_init: don't redeclare" warning

Currently in §3 as inline parenthetical:

> Declaration is in `fmgr.h:436` — do **not** redeclare it

This is a common mistake. Promote it to a bullet in §9 Common mistakes:

> 8. **Redeclaring `_PG_init` with a different signature.** The prototype is
>    in `fmgr.h`. Redeclaring (e.g. `static void _PG_init(void)`) silently
>    creates a different symbol that never gets called.

## 5. Add a one-line decision table for "lazy vs preload"

§3 has the criteria in prose. A 4-row table would make it scannable:

| Extension does ... | Loading mode |
|---|---|
| Only `CREATE FUNCTION` C funcs | Lazy (no preload needed) |
| Installs any executor/planner/utility/auth hook | `shared_preload_libraries` REQUIRED |
| Calls `RequestAddinShmemSpace` / `RequestNamedLWLockTranche` | `shared_preload_libraries` REQUIRED |
| Registers a background worker | `shared_preload_libraries` REQUIRED |

## 6. Cross-link the SUMMARY of the upgrade-path mechanism

§6 explains upgrade scripts well, but doesn't mention that PG runs a
*graph shortest-path search* — only that "PG finds the shortest chain."
A one-liner pointer to extension.c.md's `find_update_path` would help
readers wanting to debug "why is PG choosing this path":

> The chain is found by `find_update_path` in `extension.c` — a shortest-path
> graph search across all available `<ext>--A--B.sql` files. If you ship
> both `1.0--1.3.sql` and the three single-step files, the direct hop wins.
