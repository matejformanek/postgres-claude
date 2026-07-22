---
source_url: https://www.postgresql.org/docs/current/ecpg-process.html
fetched_at: 2026-07-21T18:50:00Z
anchor_sha: 0da71d90d623
title: "ECPG — Processing Embedded SQL Programs (§36 leaf): the .pgc→.c ecpg preprocessor toolchain, libecpg / libpgtypes linkage, pg_config/pkg-config wiring"
maps_to_skill: build-and-run
---

# ECPG — Processing Embedded SQL Programs (the toolchain)

How an embedded-SQL C program is built: a two-stage pipeline where the `ecpg`
preprocessor rewrites `.pgc` into `.c`, then a normal C compiler/linker takes
over, linking against `libecpg` (and `libpgtypes` when the pgtypes API is
used). This is the ECPG counterpart to how a plain libpq program links
`-lpq`.

## Non-obvious claims

- **The preprocessor is a *separate binary* named `ecpg`, run before the C
  compiler ever sees the file.** `ecpg prog1.pgc` emits `prog1.c`; `-o
  outfile.c` overrides the output name. The default rule maps `%.pgc → %.c`.
  Nothing about embedded SQL survives into the compiler's view — by the time
  `cc` runs, the file is ordinary C calling `libecpg` functions. [from-docs]

- **The generated `.c` needs the ECPG include dir at compile time.** Compile
  with `cc -c prog1.c -I/usr/local/pgsql/include` (or wherever
  `ecpglib.h`/`ecpgtype.h` live) — the two auto-inserted includes
  (see `ecpg-develop`) resolve from there. [from-docs]

- **Link against `libecpg`, and `-L` its lib dir.** `cc -o myprog prog1.o … -L…
  -lecpg`. Programs that use the pgtypes date/numeric/interval API additionally
  need `-lpgtypes` — `libpgtypes` is a *distinct* shared library from
  `libecpg`, so a program that only runs `EXEC SQL` statements links just
  `-lecpg`, while one that calls `PGTYPESnumeric_*`/`PGTYPESdate_*` needs both.
  [from-docs]

- **Prefer `pg_config` / `pkg-config` over hardcoded paths.** The docs steer
  build systems to discover the include/lib dirs via `pg_config --includedir`
  or `pkg-config --cflags/--libs libecpg` (the pkg-config package name is
  `libecpg`) rather than baking `/usr/local/pgsql/...` into a Makefile —
  matches how the rest of the client-tooling docs recommend locating an install.
  [from-docs]

- **`libecpg` is thread-safe by default, but the *application's* threading flags
  still matter.** The library itself is built thread-safe; the caveat is that
  the client code may need its own compiler threading options, and a
  build-flag mismatch between `libecpg` and the app is exactly what makes
  `ECPGdebug`'s `FILE *` crash on Windows (see `ecpg-library`). [from-docs]

- **The canonical Make idiom is a pattern rule.** `%.c: %.pgc` with
  `$(ECPG) $<` (where `ECPG = ecpg`) is the documented implicit rule — the
  preprocessor slots in as just another codegen step ahead of the normal
  `%.o: %.c` compile. Full `ecpg` flag reference lives in the `app-ecpg`
  reference page, not this chapter. [from-docs]

## Links into corpus

- What the preprocessor emits into the `.c`:
  `knowledge/docs-distilled/ecpg-develop.md`.
- The `libpgtypes` API that pulls in `-lpgtypes`:
  `knowledge/docs-distilled/ecpg-pgtypes.md`.
- Sibling client link model (plain libpq `-lpq`):
  `knowledge/docs-distilled/libpq-connect.md`.
- Skill: `build-and-run` (toolchain wiring), `wire-protocol` (client family).
