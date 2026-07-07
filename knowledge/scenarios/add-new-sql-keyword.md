---
scenario: add-new-sql-keyword
when_to_use: I want to add a new SQL keyword (reserved or unreserved) — the kwlist.h + gram.y + scan-sync sweep, distinct from adding a whole new statement.
companion_skills: ["parser-and-nodes"]
related_scenarios: ["add-new-utility-statement", "add-new-node-type", "remove-from-catalog", "integrate-with-plpgsql"]
canonical_commit: 0823d061b0b
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new SQL keyword

## Scope — what's in / out

**In scope:**
- One new keyword token consumed by `gram.y` somewhere (production, alias,
  function-name, etc.).
- The `kwlist.h` entry, the `%token <keyword>` declaration, and the
  category-list membership (`unreserved_keyword` / `col_name_keyword` /
  `type_func_name_keyword` / `reserved_keyword` / `bare_label_keyword`)
  [verified-by-code](source/src/backend/parser/gram.y:18823),
  [verified-by-code](source/src/include/parser/kwlist.h:27).
- The frontend-scanner-sync obligation: `scan.l` (backend), `psqlscan.l`
  (psql), and `pgc.l` (ecpg) must agree on what's a keyword character class
  [from-comment](source/src/fe_utils/psqlscan.l:14-20).
- Reserved-keyword choice: every new keyword *should* be unreserved unless
  the grammar can't be made unambiguous otherwise
  [from-comment](source/src/backend/parser/gram.y:18762-18766).

**Out of scope:**
- The new statement / clause / expression that *uses* the keyword — that's
  one of `add-new-utility-statement` (utility) or `add-new-node-type`
  (expression Node). This scenario is the keyword surface only.
- New ECPG-specific keywords (`SQL_*` / C-typename keywords) — those land
  in `ecpg_kwlist.h` / `c_kwlist.h` and are decoupled from backend
  `kwlist.h` [verified-by-code](source/src/interfaces/ecpg/preproc/ecpg_kwlist.h:25),
  [verified-by-code](source/src/interfaces/ecpg/preproc/c_kwlist.h:27).
- Lookahead-disambiguated `*_LA` tokens (`NOT_LA`, `NULLS_LA`, …) — those
  are not real keywords; they're emitted by the lexer's lookahead filter
  in `parser.c` after a `NOT` / `NULLS` / etc. [verified-by-code](source/src/backend/parser/gram.y:854).

## Pre-flight

- **Companion skill:** load `parser-and-nodes` — the gram.y / parsenodes
  / scan-pipeline procedural rules. See
  `.claude/skills/parser-and-nodes/SKILL.md`.
- **Canonical commit:** `0823d061b0b` — *Introduce SYSTEM_USER* (Michael
  Paquier, 2022-09-29). One `kwlist.h` line, one `%token` entry, three
  category-list memberships (`reserved_keyword` + `bare_label_keyword` +
  one rule action), plus `catversion` bump and `pg_proc.dat` for the
  helper function. The minimum-viable shape of "add one keyword"
  [verified-by-code](source/src/include/parser/kwlist.h:27).
- **Common pitfalls (one-line each):**
  - kwlist.h not in ASCII order → `gen_keywordlist.pl` rejects the build
    [from-comment](source/src/include/parser/kwlist.h:24),
    [from-comment](source/src/tools/gen_keywordlist.pl:11).
  - Forgot to add to a category list → `check_keywords.pl` fails the
    backend build with "Token X is not in kwlist" or "missing from
    category list" [verified-by-code](source/src/backend/parser/check_keywords.pl:1-15),
    [verified-by-code](source/src/backend/parser/Makefile:58).
  - Reserving a previously-unreserved word silently breaks user SQL
    (column names like `system_user` become invalid) — see "Pitfalls".
  - Forgot `BARE_LABEL` ↔ `bare_label_keyword:` correspondence
    [from-comment](source/src/backend/parser/gram.y:19378-19379).
  - `psqlscan.l` / `pgc.l` lex character class drift — see
    "Synchronization traps".

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/parser/kwlist.h` | Add `PG_KEYWORD("<lowercase>", <TOKEN>, <CATEGORY>, <LABEL>)` in ASCII-sorted position. Categories: `UNRESERVED_KEYWORD` / `COL_NAME_KEYWORD` / `TYPE_FUNC_NAME_KEYWORD` / `RESERVED_KEYWORD`. Label: `BARE_LABEL` or `AS_LABEL`. The file is consumed both by the backend (via `scan.l` include) and by `gen_keywordlist.pl` to emit `kwlist_d.h` with the perfect-hash table [from-comment](source/src/include/parser/kwlist.h:22-25),[verified-by-code](source/src/tools/gen_keywordlist.pl:1-30). | [kwlist.h.md](../files/src/include/parser/kwlist.h.md) | parser-and-nodes |
| 2 | `src/backend/parser/gram.y` | Three edits: (a) add `<TOKEN>` to the `%token <keyword>` block around line 746 [verified-by-code](source/src/backend/parser/gram.y:746-825); (b) reference it in the production(s) where the new syntax fires; (c) add it to **exactly one** of `unreserved_keyword:` / `col_name_keyword:` / `type_func_name_keyword:` / `reserved_keyword:` (lines 18823, 19182, etc.) [verified-by-code](source/src/backend/parser/gram.y:18823); (d) if `BARE_LABEL` in kwlist, also list it under `bare_label_keyword:` [verified-by-code](source/src/backend/parser/gram.y:19381-19383). Token-list lines are alphabetized within their letter group. | [gram.y.md](../files/src/backend/parser/gram.y.md) | parser-and-nodes |
| 3 | `src/backend/parser/check_keywords.pl` | NOT edited — **runs at build time** as a Bison `BISON_CHECK_CMD` and cross-validates that every kwlist entry appears in exactly one category in gram.y and vice versa [verified-by-code](source/src/backend/parser/Makefile:58),[verified-by-code](source/src/backend/parser/check_keywords.pl:1-15). Build will fail loudly if categories don't match. | — | parser-and-nodes |
| 4 | `src/backend/parser/scan.l` | Usually NOT edited for a plain keyword. The backend scanner uses the auto-generated `ScanKeywords` table from `kwlist_d.h`; the lexer rule for `identifier` calls `ScanKeywordLookup()` against that table [verified-by-code](source/src/backend/parser/scan.l:76-81),[verified-by-code](source/src/backend/parser/parser.c:50). Only edit if your keyword introduces a new character class (e.g. a punctuation token). | [scan.l.md](../files/src/backend/parser/scan.l.md) | parser-and-nodes |
| 5 | `src/include/nodes/parsenodes.h` | Edit only if the new keyword introduces a new parse-tree enum tag, struct field, or `*Stmt` (which then makes this a composite with `add-new-node-type` / `add-new-utility-statement`). A keyword that's a synonym/alias of an existing production touches nothing here [verified-by-code](source/src/include/nodes/parsenodes.h). | [parsenodes.h.md](../files/src/include/nodes/parsenodes.h.md) | parser-and-nodes |
| 6 | `src/backend/parser/analyze.c` | Edit only if post-parse analysis needs to recognize the new construct (e.g. routing a new `*Stmt` through `transformStmt()`). Pure-grammar keywords with no new Node touch nothing here [verified-by-code](source/src/backend/parser/analyze.c). | [analyze.c.md](../files/src/backend/parser/analyze.c.md) | parser-and-nodes |
| 7 | `src/fe_utils/psqlscan.l` | **The classic sync trap.** psql's standalone scanner uses the *backend's* keyword table indirectly via the parser, but its own flex rules for identifier / quoted-literal / dollar-quote MUST stay byte-identical with `scan.l`. The file's header explicitly says: "XXX The rules in this file must be kept in sync with the backend lexer!!!" [from-comment](source/src/fe_utils/psqlscan.l:14-22). Plain `kwlist.h` additions don't require an edit here, but **any change to character classes does** — and the symptom is silent: psql's `\;` statement splitting goes wrong on the new token. | — | parser-and-nodes |
| 8 | `src/interfaces/ecpg/preproc/pgc.l` | **Second sync trap.** ecpg's preprocessor scanner — "a modified version of src/backend/parser/scan.l" [from-comment](source/src/interfaces/ecpg/preproc/pgc.l:5-9). Same rule: keyword additions don't require an edit; character-class changes do. ecpg actually re-uses backend keyword classification automatically because `preproc.y` is built from `gram.y` by `parse.pl` [from-README](source/src/interfaces/ecpg/preproc/README.parser:1-3). | — | parser-and-nodes |
| 9 | `src/interfaces/ecpg/preproc/c_kwlist.h` | NOT edited for a backend keyword. Holds C-language reserved words (`auto`, `bool`, `enum`, …) used by the ECPG preprocessor when parsing host C code [verified-by-code](source/src/interfaces/ecpg/preproc/c_kwlist.h:27-52). Only touch if you're adding a C-language keyword to ECPG, which is rare. | — | parser-and-nodes |
| 10 | `src/interfaces/ecpg/preproc/ecpg_kwlist.h` | NOT edited for a backend keyword. Holds ECPG-only keywords (`SQL_*`, `CONNECTION`, `IDENTIFIED`, …) that don't exist in the backend grammar [verified-by-code](source/src/interfaces/ecpg/preproc/ecpg_kwlist.h:1-10). Confusingly named — it does *not* mirror backend kwlist. Touch only for ECPG-only extensions. | — | parser-and-nodes |
| 11 | `src/interfaces/ecpg/preproc/parse.pl` | NOT edited — runs at build time, extracts the SQL grammar from `gram.y` and weaves in `ecpg.addons` / `ecpg.trailer` to produce `preproc.y` [from-README](source/src/interfaces/ecpg/preproc/README.parser:1-21). Backend keyword additions flow through automatically. | — | parser-and-nodes |
| 12 | `src/bin/psql/tab-complete.in.c` | Add the new keyword wherever its syntactic position is tab-completable. The file is preprocessed by `gen_tabcomplete.pl` into a switch-based `match_previous_words()` [from-comment](source/src/bin/psql/tab-complete.in.c:7-13). Not load-bearing for correctness, but expected by reviewers if the keyword appears in user-typed SQL. | [tab-complete.in.c.md](../files/src/bin/psql/tab-complete.in.c.md) | psql |
| 13 | `doc/src/sgml/keywords.sgml` + `doc/src/sgml/keywords/` | The SQL-keywords appendix is generated by `doc/src/sgml/generate-keywords-table.pl` from `kwlist.h` plus the `sql{2016,2023}-*-{nonreserved,reserved}.txt` reference files [verified-by-code](source/doc/src/sgml/generate-keywords-table.pl). You usually don't hand-edit `keywords.sgml`; the doc build picks up the new entry automatically. Verify by running `meson test --suite docs`. | — | — |
| 14 | `src/test/regress/sql/create_view.sql` + `expected/create_view.out` | The regression test that calls `pg_get_keywords()` lives here — its expected output enumerates the keyword count and a sample [verified-by-code](source/src/test/regress/sql/create_view.sql:806). Adding a keyword will shift counts; re-record expected output. Also `rangefuncs.sql` exercises `pg_get_keywords()` in another way [verified-by-code](source/src/test/regress/sql/rangefuncs.sql:645). | — | testing |
| 15 | `src/backend/utils/adt/misc.c` | NOT edited — but `pg_get_keywords()` lives here and reads the auto-generated `ScanKeywords` table at runtime [verified-by-code](source/src/backend/utils/adt/misc.c:391). Useful for grep-confirming the wire-up after build. | — | — |
| 16 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` **only** if your keyword introduces a stored-parsetree change (new Node type, new Stmt) — see `add-new-node-type`. Pure-grammar keyword additions that don't affect on-disk catalogs / parsetree storage typically don't require a bump [from-comment](source/src/include/catalog/catversion.h:26-38). | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 17 | `src/pl/plpgsql/src/pl_gram.y` | **Third sync trap — PL/pgSQL `%token <str>` sibling block.** Lines 247-250 carry a `%token <str>` declaration block prefixed with the in-source comment "Keep this list in sync with backend/parser/gram.y!" [from-comment](source/src/pl/plpgsql/src/pl_gram.y:240-249). Any new core `gram.y` `%token <str>` shifts the numeric token IDs assigned by Bison in `gram.h` (e.g. `COLON_EQUALS` 270→271, `DOT_DOT` 269→270 in the sesvars run). PL/pgSQL's `pl_scanner.c` makes **integer comparisons** against these IDs (`if (tok == COLON_EQUALS)`), so a desync silently breaks PL/pgSQL parsing of `:=` and `1..N` ranges. Not enforced by any build script. Origin: sesvars F2 retro, where adding `SESSION_VAR` to core gram.y without syncing pl_gram.y caused ~30 of 39 phase-1 regression failures. Composite trigger: see also `scenarios/integrate-with-plpgsql.md` for the broader PL/pgSQL surface. | — | parser-and-nodes |
| 18 | Catalog-conflict audit (REQUIRED before adding new lexer token) | **NOT a single file — a required grep step.** Before introducing a new sigil or character-class lexer rule (`@{ident}`, `#`-prefix, etc.), grep `src/include/catalog/pg_operator.dat`, `src/include/catalog/pg_proc.dat`, and `src/include/catalog/pg_aggregate.dat` for any existing entries that use the proposed sigil/character as an operator name. Origin: sesvars F1 — the brainstorm chose new flex rule `@{ident}` → `SESSION_VAR` with the framing "accept docs incompat for *user-defined* `@`-prefix unary operators." The word "user-defined" was the bug: PG ships **6 built-in `@` unary operators** in `pg_operator.dat` (int2abs / int4abs / int8abs / float4abs / float8abs / numeric_abs). The new `@{ident}` lexer rule hijacked them and regressed the float4 / float8 / opr_sanity tests; Phase 0 had to drop all 6 catalog entries and backfill `descr =>` on the orphaned `*abs` procs (see also `scenarios/remove-from-catalog.md` for the downstream removal sweep). If your audit reveals a conflict, the decision question changes from "accept it" to "remove the existing entries AND audit the contrib + regress fallout" — escalate to brainstorm. | — | parser-and-nodes |

## Phases — suggested split for `pg-feature-plan`

The tree must build at the end of each phase.

1. **Phase 1 — Token plumbing.** Files: [1, 2 (a + c only)].
   Add the kwlist entry in ASCII-sorted position. Add `<TOKEN>` to the
   `%token <keyword>` block. Add the membership line to the chosen
   category rule and (if BARE_LABEL) the `bare_label_keyword` rule.
   Phase-end check: `meson compile -C dev/build-debug` succeeds —
   `check_keywords.pl` runs as part of the Bison step and will fail
   loudly if categories don't line up. The keyword is now scannable
   but unused.

2. **Phase 2 — Grammar use.** Files: [2 (b), 5 if new Node, 6 if new
   analysis]. Reference the token in the production(s) that fire the
   new syntax. If this introduces a new Node, follow
   `add-new-node-type`; if a new utility statement,
   `add-new-utility-statement`. Phase-end check: rebuild + ad-hoc
   `psql -c "<sample using new keyword>"` returns expected result.

3. **Phase 3 — Frontend + docs + tests.** Files: [12, 13, 14].
   Add tab-completion hints. Regenerate `create_view.out` /
   `rangefuncs.out` after the new keyword shifts the
   `pg_get_keywords()` count. Doc build picks up `keywords.sgml`
   automatically. Phase-end check:
   `meson test -C dev/build-debug --suite regress --suite docs`
   passes.

4. **Phase 4 — (only if reserving).** If the new keyword is RESERVED,
   sweep the tree for user-visible breakage: existing test SQL using
   the bareword (e.g. `SELECT … AS system_user`) will now fail and
   needs quoting. This phase exists to bound the blast radius.



## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | shares files: `src/include/catalog/catversion.h`, `src/include/catalog/pg_proc.dat` |
| [`node-types`](../idioms/node-types.md) | shares files: `src/include/nodes/parsenodes.h` |
| [`node-types-and-lists`](../idioms/node-types-and-lists.md) | direct reference |
| [`parser-pipeline`](../idioms/parser-pipeline.md) | direct reference |
| [`security-barrier-views`](../idioms/security-barrier-views.md) | shares files: `src/include/nodes/parsenodes.h` |

<!-- /idioms-invoked:auto -->

## Pitfalls

- **kwlist.h sort order.** `gen_keywordlist.pl` requires ASCII order;
  out-of-order entries fail the build with a clear message
  [from-comment](source/src/include/parser/kwlist.h:24). The header
  says "deliberately not an `#ifndef KWLIST_H` here" — the file is
  re-included with different `PG_KEYWORD` macro definitions in
  multiple places (categories, labels, hash table) [from-comment](source/src/include/parser/kwlist.h:19).
- **Category mismatch between kwlist.h and gram.y.**
  `check_keywords.pl` is wired into `BISON_CHECK_CMD` and catches this
  at build time [verified-by-code](source/src/backend/parser/Makefile:58).
  Fix in the same commit; do not bypass.
- **Reserving a previously-common word silently breaks user code.**
  Every reserved-keyword promotion has historically been a multi-thread
  discussion on pgsql-hackers. Prefer `UNRESERVED_KEYWORD` if the
  grammar can be made unambiguous (often by listing the new keyword in
  `unreserved_keyword:` and depending on context). The four reserved
  categories form a hierarchy: unreserved → col_name → type_func_name
  → reserved, in order of decreasing usability as an identifier
  [from-comment](source/src/backend/parser/gram.y:18757-18766).
- **Missing `bare_label_keyword:` membership.** If you mark a keyword
  `BARE_LABEL` in kwlist.h, you MUST also list it in the
  `bare_label_keyword:` production [from-comment](source/src/backend/parser/gram.y:19378-19379).
  Otherwise `SELECT 1 newkw` (column alias without AS) breaks — and
  the failure mode is a confusing syntax error far from the real edit.
- **`pg_get_keywords()` regression-output drift.** The
  `create_view.out` expected file includes a row count from
  `pg_get_keywords()` [verified-by-code](source/src/test/regress/sql/create_view.sql:806).
  Forgetting to re-record makes `make check` red. Easy fix:
  `cp dev/build-debug/testrun/.../create_view.out
  source/src/test/regress/expected/create_view.out` after the run.
- **Lookahead-disambiguated tokens are not keywords.** Don't try to
  add `*_LA` variants to kwlist.h — those are emitted by the lexer
  post-filter in `base_yylex()` (see `parser.c`), not by the keyword
  table [verified-by-code](source/src/backend/parser/gram.y:854).

- **Synchronization traps** (sibling files that must change together):
  - `kwlist.h` entry ↔ `gram.y` `%token` declaration ↔ `gram.y`
    category-rule membership ↔ (if BARE_LABEL) `bare_label_keyword:`
    membership. All four enforced by `check_keywords.pl` at build.
  - `scan.l` (backend) ↔ `psqlscan.l` (psql) ↔ `pgc.l` (ecpg). Not
    enforced by any script. The header comment on `psqlscan.l` is the
    only warning system [from-comment](source/src/fe_utils/psqlscan.l:14-22).
    The trap fires when you edit character classes (identifier rules,
    string-literal rules) — *not* when you add a plain kwlist entry —
    so for the typical keyword-add this is a non-issue. Note it
    explicitly in the commit message if you DID touch character
    classes.
  - **Core `gram.y` `%token <str>` block ↔ `src/pl/plpgsql/src/pl_gram.y:247-250`
    `%token <str>` block.** New core `%token <str>` shifts Bison-assigned
    numeric IDs in `gram.h`; PL/pgSQL's `pl_scanner.c` compares against
    those IDs by integer, so desync silently breaks `:=`, `1..N`, and
    other PL/pgSQL constructs. Not enforced by any script — the
    in-source comment "Keep this list in sync with backend/parser/gram.y!"
    [from-comment](source/src/pl/plpgsql/src/pl_gram.y:240-241) is the
    only warning. Origin: sesvars F2 retro.
  - `kwlist.h` ↔ `create_view.out` / `rangefuncs.out` expected output
    (the row counts shift).
  - kwlist length ↔ `doc/src/sgml/keywords.sgml` regen happens
    automatically; no action needed unless the doc build fails.

- **Catalog-conflict audit BEFORE picking a sigil / character-class
  lexer rule.** Required pre-flight grep step (row 18 in the checklist):
  search `pg_operator.dat`, `pg_proc.dat`, `pg_aggregate.dat` for any
  existing entries that use the proposed sigil. PG ships 6 built-in
  `@` unary operators that the sesvars `@{ident}` lexer rule hijacked
  unintentionally (sesvars F1 retro). If you find conflicts, decide
  whether to (a) abandon the sigil and pick another, (b) remove the
  existing entries and pin `scenarios/remove-from-catalog.md` for the
  downstream sweep, or (c) escalate to the user. Do NOT proceed
  without making that decision explicitly.

## Verification (exact test invocations)

```bash
# Build — runs check_keywords.pl and gen_keywordlist.pl
meson compile -C dev/build-debug

# Smoke-test: confirm the new keyword scans
dev/install-debug/bin/psql -c "SELECT * FROM pg_get_keywords() WHERE word = '<newkw>';"

# Full regress — picks up create_view.out and rangefuncs.out diffs
meson test -C dev/build-debug --suite regress

# Specifically the tests that exercise pg_get_keywords()
meson test -C dev/build-debug --suite regress --test regress
# (the relevant SQL is in create_view.sql and rangefuncs.sql)

# Doc build — regenerates keywords.sgml from kwlist.h
meson test -C dev/build-debug --suite docs

# ECPG (sanity — the auto-regen via parse.pl should pick the keyword up)
meson test -C dev/build-debug --suite ecpg
```

No new test file is needed for a plain keyword addition; the existing
`create_view.sql` + `rangefuncs.sql` exercises of `pg_get_keywords()`
provide coverage that the new entry is wired into the runtime
keyword table. If your keyword introduces actual new syntax, the
test scope expands to whatever scenario you compose with
(`add-new-utility-statement`, `add-new-node-type`, …).

## Cross-refs

- Companion skills: `.claude/skills/parser-and-nodes/SKILL.md`,
  `.claude/skills/psql/SKILL.md` (tab-complete only).
- Related scenarios: `scenarios/add-new-utility-statement.md`,
  `scenarios/add-new-node-type.md`, `scenarios/bump-catversion.md`
  (only if the keyword introduces a stored-parsetree change).
- Idioms: `knowledge/idioms/parser-pipeline.md`,
  `knowledge/idioms/node-types-and-lists.md`.
- Subsystems: `knowledge/subsystems/parser-and-rewrite.md`,
  `knowledge/subsystems/ecpg.md`, `knowledge/subsystems/psql.md`.
- Issues: `knowledge/issues/include-cmds-nodes-parser-tcop-rewrite.md`,
  `knowledge/issues/ecpg.md`, `knowledge/issues/psql.md`.
- Reference patch (canonical_commit): `git -C source show 0823d061b0b`
  — *Introduce SYSTEM_USER*, the minimal "one new reserved keyword + a
  helper function" shape.
