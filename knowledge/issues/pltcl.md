# Issues — `pl/tcl` (src/pl/tcl/)

Per-subsystem issue register for the **PL/Tcl procedural language**
— BOTH the trusted variant (`pltcl`) using a Tcl `safe` slave
interpreter and the untrusted variant (`pltclu`), implemented in a
single source file (`pltcl.c`, 3389 LOC) dispatched via a
`bool pltrusted` parameter threaded through every function.

**Parent docs:** `knowledge/files/src/pl/tcl/pltcl.c.md` (1 doc
covering 1 source file).

**Source:** 11 entries surfaced 2026-06-04 by the A10 foreground sweep
(agent A10-4). Mirrored in the per-file doc's `## Issues spotted`
block.

## The headlines (cross-PL trust-gate ranking — THE most important
finding of A10)

**Tcl Safe ≥ Perl Safe.pm > nothing (plpgsql) > N/A (plpython)**

Tcl's safe interpreter (`Tcl_CreateSlave(master, name, isSafe=1)` at
`source/src/pl/tcl/pltcl.c:507-508`) is enforced at the **C-level
command-dispatch layer** — dangerous commands (`exec`, `socket`,
`open`, `file delete`, `load`) are **NOT PRESENT in the safe interp's
command table at all**, so user Tcl code cannot reach them by any
means. This is structurally stronger than plperl's opcode-mask (which
gates Perl opcodes — the primitive exists in the interpreter, you
just can't compile a reference to it through the mask); the opcode-
mask is drift-prone as new ops get added to Perl. Tcl Safe is
maintained as a Tcl-core feature.

**Other headlines:**

1. **Dual-posture implemented in a single .c file via `bool
   pltrusted`** threaded through every function. This is more
   maintainable than plperl's parallel handler paths and is the
   **cleanest dual-trust implementation in the PG tree**.

2. **`pltcl.start_proc` / `pltclu.start_proc` are PGC_SUSET with two
   non-obvious safety checks** — same-prolang and non-SECURITY-
   DEFINER (`pltcl.c:642-658`). Together prevents privilege
   amplification at interpreter-init time. This is the trust-gate
   keystone.

3. **`spi_exec query` does NOT parameterize** (`pltcl.c:2491`) —
   standard PL SQLi sink unless user uses `quote` /
   `spi_prepare`+`spi_execp`. Same posture as plpgsql `EXECUTE` and
   `plpy.execute(text)`.

4. **Notifier override permanently disables Tcl threading**
   (`pltcl.c:344-354, 429-437`) — required to keep backend single-
   threaded; locks in compatibility cost.

5. **Trigger `TG_table_name`/`TG_table_schema` are attacker-
   controlled if attacker can name tables** — SQLi if trigger body
   interpolates them; normal privilege model prevents most exploit
   paths but worth flagging in audits (`pltcl.c:1126-1136`).

6. **NULL function args passed as empty Tcl strings** —
   indistinguishable from `""` (`pltcl.c:910-911, 879`). Tcl has no
   native null; user must `argisnull`. The cross-PL footgun footnote
   that mirrors plpgsql `STRICT` behavior.

## Cross-sweep references

- **Cross-PL trust-gate ranking**: see headlines. pltcl is the
  structurally strongest sandbox among the four PLs.
- **NAME-based procedure cache**: pltcl uses NAME-based cache; joins
  the corpus-wide NAME-vs-OID Phase D pattern (A3+A6+A7+A8+A9+A10).
- **`spi_exec` text injection cluster**: pltcl's `spi_exec` joins
  plpgsql's `EXECUTE`, plpython's `plpy.execute(text)`, plperl's
  `spi_exec_query` as the four-PL SQLi quad. Single corpus-wide
  idiom doc proposed at
  `knowledge/idioms/pl-dynamic-sql-injection.md`.

---

## Entries (11 total)

- [ISSUE-security: `spi_exec query` does NOT parameterize (likely,
  by design)] — `source/src/pl/tcl/pltcl.c:2491` — standard PL SQLi
  sink unless user uses `quote` / `spi_prepare`+`spi_execp`.
- [ISSUE-security: `pltcl.start_proc` / `pltclu.start_proc` PGC_SUSET
  with prolang+non-secdef checks (defense-in-depth, confirmed
  solid)] — `source/src/pl/tcl/pltcl.c:471-484, 642-658` — design is
  sound; logged because it's the trust-gate keystone.
- [ISSUE-memory: prepared-plan recompile leak — file's own FIXME
  (confirmed)] — `source/src/pl/tcl/pltcl.c:2666-2667` — bounded by
  interpreter lifetime.
- [ISSUE-security: trigger `TG_table_name`/`TG_table_schema` are
  attacker-controlled if attacker can name tables (maybe)] —
  `source/src/pl/tcl/pltcl.c:1126-1136` — SQLi if trigger body
  interpolates them; normal privilege model prevents most exploit
  paths.
- [ISSUE-correctness: NULL function args passed as empty Tcl strings,
  indistinguishable from `""` (likely, by design)] —
  `source/src/pl/tcl/pltcl.c:910-911, 879` — Tcl has no native null;
  user must `argisnull`.
- [ISSUE-error-handling: FATAL path of `pltcl_elog` has unreachable
  PG_CATCH (nit)] — `source/src/pl/tcl/pltcl.c:1891-1921` — comment
  acknowledges; harmless.
- [ISSUE-audit-gap: no per-Tcl-command audit hook (maybe)] — same gap
  as plpython.
- [ISSUE-defense-in-depth: `Tcl_DeleteCommand` of old internal proc
  on recompile relies on Tcl refcounting (confirmed)] —
  `source/src/pl/tcl/pltcl.c:1518-1519` — explicit assumption
  documented; Tcl ABI breakage would SEGV.
- [ISSUE-concurrency: notifier override permanently disables Tcl
  threading (confirmed, by design)] —
  `source/src/pl/tcl/pltcl.c:344-354, 429-437` — required to keep
  backend single-threaded; locks in compatibility cost.
- [ISSUE-documentation: trust-posture rationale scattered across
  three functions (nit)] —
  `source/src/pl/tcl/pltcl.c:113-119, 503-504, 642-658` — consider
  top-of-file consolidation.
- [ISSUE-api-shape: two call handlers + bool param vs one handler +
  pg_proc bit (nit)] — `source/src/pl/tcl/pltcl.c:702-721` — current
  design is right (two pg_language entries need two handlers); just
  worth a one-line comment.
