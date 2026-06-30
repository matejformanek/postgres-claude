# postgresql-unit — a fixed-layout base type that carries a 7+1-vector of SI dimensions and does dimensional analysis *inside* its operators

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `df7cb/postgresql-unit` @ branch `master` (Christoph Berg). All
> `file:line` cites point into that repo (not `source/`). Cites verified against
> files fetched 2026-06-30 (see Sources footer). Read alongside the sibling
> custom-type notes `[[knowledge/ideologies/uuidv47]]` and
> `[[knowledge/ideologies/orafce]]`.

## Domain & purpose

postgresql-unit "implements a *PostgreSQL datatype for SI units, plus byte*"
(`README.md:5-6`) `[from-README]`. A `unit` value is a scalar magnitude plus a
vector of integer exponents over eight base dimensions — the seven SI base units
(m, kg, s, A, K, mol, cd) plus a non-SI eighth, *byte* (`unit.h:8-17`)
`[verified-by-code]`. Arbitrary derived units (newton, pascal, joule, MB/min,
hl) compose from these via the PG operator system, and a `@` conversion operator
rescales a quantity into any compatible target unit (`README.md:6-10, 72-77`)
`[from-README]`. Over 2500 units and 100+ prefixes ship from GNU Units'
`definitions.units` file and are loaded into ordinary catalog *tables* at
install (`README.md:12-15, 207-208`) `[from-README]`. It earns a doc because it
is the corpus's cleanest example of a custom base type that bakes a **typed
algebra with runtime dimension checking** into its operator set — `1 m + 1 s`
raises an error, unlike any core numeric operation.

## How it hooks into PG

A C base type plus a SQL/PLpgSQL install layer:

- **The struct** is fixed-width 16 bytes: a `double value` followed by
  `signed char units[8]` (`unit.h:60-63`) `[verified-by-code]`. No varlena, no
  TOAST — the SI exponent vector is packed inline with the magnitude and travels
  with every datum on the heap page.
- **Type I/O**: `unit_in`/`unit_out`/`unit_recv`/`unit_send`, all
  `PG_FUNCTION_INFO_V1` (`unit.c:544-595`) `[verified-by-code]`. `unit_in`
  delegates the whole text grammar to `unit_parse()` (the generated bison parser,
  below); `unit_out` calls `unit_cstring()` (`unit.c:546-568`).
- **`_PG_init`** defines four `PGC_USERSET` bool GUCs that steer *output*
  formatting — `unit.output_superscript`, `unit.time_output_custom`,
  `unit.byte_output_iec`, `unit.output_base_units` — then populates two
  backend-local hash tables via `unit_get_definitions()` (`unit.c:141-195`)
  `[verified-by-code]`.
- **Operators**: arithmetic (`unit_add`/`unit_sub`/`unit_neg`/`unit_mul`/
  `unit_div`/`unit_pow`), mixed `unit`×`double` variants, roots, transcendental
  functions, the `@` conversion family (`unit_at_text2`/`unit_at_double`), and
  two full comparison families (`unit.c:768-1408`) `[verified-by-code]`.
- **B-tree opclass** off `unit_cmp` for indexing/sorting, plus aggregates
  `min`/`max`/`sum` (`README.md:42, 374-394, 430`) `[from-README]`.
- **Definition tables + loader**: `unit_prefixes` and `unit_units` are real
  user-visible tables (`README.md:167-184`); `unit_load()` is a PL/pgSQL function
  (hence `requires = 'plpgsql'`, `unit.control:6-7`) that bulk-loads the
  `.data` files (`README.md:217-219`) `[from-README]`. The extension is
  `relocatable = false` because the lexer references those tables by name
  (`unit.control:3-5`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. Operators do dimensional type-checking at *runtime*, and raise on mismatch

Core `+`/`-` on `numeric`/`float8` never inspect the operands' "kind" — a number
is a number. `unit` adds a typed-algebra layer *above* PG's static type system:
`unit_add_internal`/`unit_sub_internal` first call `test_same_dimension()`, which
`memcmp`s the two 8-byte exponent vectors and `ereport(ERROR, …
"dimension mismatch in \"%s\" operation")` if they differ (`unit.h:93-117`)
`[verified-by-code]`. So `'1 m'::unit + '1 s'::unit` fails at execution time even
though both arguments share the *same* SQL type `unit`. Multiplication/division
instead *add/subtract* the exponent vectors elementwise, synthesizing a new
dimension (`unit.h:119-143`) `[verified-by-code]` — so `m * m → m^2`, `m / s →
m·s⁻¹`. Division additionally guards a zero-valued divisor with
`ERRCODE_DIVISION_BY_ZERO` (`unit.h:134-138`). The transcendental ops
(`exp`/`ln`/`log2`/`asin`/`tan`) refuse any non-dimensionless input
(`unit.c:993-1098`), and `sqrt`/`cbrt` refuse exponents not divisible by 2/3
(`unit.c:930-991`) `[verified-by-code]`. This is a dimensional-analysis type
checker implemented entirely in C operator bodies — a kind of correctness core
SQL types never attempt. Cross-ref `[[knowledge/idioms/error-handling]]`,
`[[knowledge/idioms/fmgr]]`.

### 2. Two comparison families: the b-tree opclass cmp is dimension-*blind*

There are two parallel comparison ladders. The plain one (`unit_cmp_internal`)
sorts by `value` first and only `memcmp`s the dimension vector as a tiebreaker
(`unit.c:1205-1213`) `[verified-by-code]` — so `1 m` and `1 s` are *orderable*
against each other (they compare by magnitude), which is what the b-tree opclass
uses. A separate "strict" family (`unit_strict_cmp_internal`) calls
`test_same_dimension()` first and *errors* on a cross-dimension compare
(`unit.c:1294-1303`) `[verified-by-code]`. The design therefore deliberately
relaxes dimensional strictness for the indexable comparison (a b-tree opclass
support function must be total and may not throw) while offering strict operators
for query logic — a pointed illustration of the tension between opclass totality
requirements and a type's semantic invariants. Cross-ref
`[[knowledge/subsystems/access-nbtree]]`,
`.claude/skills/access-method-apis/SKILL.md`.

### 3. Text *output* depends on session GUC state — the same datum renders differently

Like uuidv47, `unit`'s output is not a pure function of the stored bytes:
`unit_cstring()` branches on four session GUCs. `unit.output_superscript` swaps
`^2` for `²` (`unit.c:212-231`); `unit.byte_output_iec` formats a byte quantity
with binary prefixes `Ki/Mi/Gi…` instead of decimal SI (`unit.c:390-421`);
`unit.time_output_custom` renders a ≥60 s duration as `hh:mm:ss`/days/years
instead of seconds (`unit.c:431-437, 233-302`); `unit.output_base_units` strips
all prefix/derived-name formatting (`unit.c:334, 390, 425`) `[verified-by-code]`.
So a stored `unit` prints different *text* under different session settings —
output is effectively `STABLE`, not `IMMUTABLE`, the same I/O-purity bend uuidv47
exhibits (there via a key GUC; here via formatting GUCs). Unlike uuidv47 the
*round-trip value* is preserved (the GUCs only affect presentation, not the
decoded magnitude), and output never `ereport`s — a milder form of the same
divergence. Cross-ref `[[knowledge/idioms/guc-variables]]`,
`.claude/skills/gucs-config/SKILL.md`.

### 4. The text grammar is a generated bison parser that *runs SQL* during lexing

`unit_in` hands the whole input string to `unit_parse()`, declared in
`unit.h:86` as living "in unit.y" — i.e. the lexer/parser is a flex+bison grammar
(`unitparse.tab.c` is the checked-in generated parser; build needs flex and
bison 3, `README.md:17-18`) `[from-README]`. A custom base type shipping its own
LALR grammar instead of hand-rolled `strtod`+`switch` parsing is already unusual.
What is sharper: when the lexer meets a unit name it is *not* a compiled constant
— it **queries the `unit_units`/`unit_prefixes` catalog tables** (cross-joining
to try every prefix+unit split, erroring on ambiguity like "dat" = dekatonne vs
deciatmosphere, and retrying with a trailing-plural `s` stripped)
(`README.md:187-194`) `[from-README]`. Resolved names are memoized into a
backend-local hash table seeded with the eight base units (`unit_get_definitions`,
`unit.c:45-133`) `[verified-by-code]`. Because the parser issues SQL, the I/O
function needs `search_path = @extschema@` — the source flags this on every
`unit_parse`-using entry point (`unit.c:543, 1101, 1154, 1180`)
`[verified-by-code]`. An input function that runs queries against extension
tables is a long way from core's self-contained scanners.

### 5. Unit definitions are mutable catalog data, refreshable at runtime

The full unit table is not compiled in: only the 8 base units and 17 SI derived
names are C constants (`defined_units.h:7-37`) `[verified-by-code]`; the
2500-plus real definitions live in `unit_units` as ordinary rows a user can
`INSERT` into (`README.md:225-238`) `[from-README]`. After editing definitions
the user calls `unit_reset()`, which re-runs `unit_get_definitions()` to rebuild
the backend-local cache (`unit.c:1423-1432`) `[verified-by-code]`. So the type's
*vocabulary* is run-time-extensible per database — closer to a data-driven
configuration system than a fixed type, and a notable contrast with core types
whose literal grammar is frozen in the backend binary.

## Notable design decisions (cited)

- **Fixed 16-byte struct, byte as the 8th dimension.** `double` + `signed char
  units[8]`, with `UNIT_B` (byte) sitting alongside the seven SI base units
  (`unit.h:15-17, 60-63`) `[verified-by-code]` — lets `MB/min` and `Gi`-prefixed
  byte rates be first-class dimensioned quantities.
- **`recv`/`send` are raw and trusting.** `unit_recv` reads a float8 then
  `memcpy`s 8 exponent bytes straight off the wire with no validation
  (`unit.c:572-581`) `[verified-by-code]` — fine for a fixed layout, but no
  range/sanity check on the exponents.
- **Powers-of-ten thresholds are a generated, deliberately-rounded-down table.**
  `powers.h` is emitted by `powers.c` using `nextafter(x,0)` so each constant is
  the largest double strictly below the true power, making `>=` prefix-selection
  comparisons land on the intended SI prefix (`powers.c:4, 12-34`;
  `powers.h:2-3`) `[verified-by-code]` — a careful float-boundary trick for
  picking k/M/G/… on output.
- **Custom float printer revives an old PG internal.** `float8out_unit` is a
  vendored copy of pre-12 `float8out_internal`, honoring `extra_float_digits`
  with the PG-12 "==1 means revert to old default" quirk (`float8out_unit.h:1-17`)
  `[verified-by-code, from-comment]` — so unit magnitudes format consistently
  across PG versions independent of core's `%g` changes.
- **Hash-table rebuild is OOM-safe via PG_TRY.** `unit_get_definitions` builds
  *temporary* tables and only swaps them into the live globals after the loop
  succeeds, destroying the partial table in `PG_CATCH` (`unit.c:70-96, 109-132`)
  `[verified-by-code]` — leaves the cache consistent if an allocation throws
  mid-rebuild.
- **`@` conversion has accreted versioned variants.** `unit_at`/`unit_at_text`/
  `unit_at_text2`/`unit_at_double` coexist for backward compat across extension
  versions 1–7 (`unit.c:1100-1201`) `[verified-by-code, from-comment]`; all
  re-`unit_parse` the RHS target unit and `test_same_dimension` before rescaling.

## Links into corpus

- `[[knowledge/ideologies/uuidv47]]` — sibling custom base type that also makes
  text output depend on session GUC state; uuidv47 bends I/O harder (output
  *errors* on an unset key and storage≠presentation), unit bends it more mildly
  (GUCs reshape presentation only, value preserved, output never throws).
- `[[knowledge/ideologies/orafce]]` — custom types + GUC-driven dialect behavior;
  same "session state alters a type's surface" theme.
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` operator surface and
  `PG_GETARG_POINTER`/`PG_RETURN_POINTER` discipline for a by-reference fixed type.
- `[[knowledge/idioms/error-handling]]` — operators that `ereport(ERROR)` on a
  dimension mismatch / division-by-zero-unit / non-dimensionless transcendental.
- `[[knowledge/idioms/guc-variables]]` — four `PGC_USERSET` bool GUCs steering
  output formatting via `DefineCustomBoolVariable`.
- `[[knowledge/idioms/catalog-conventions]]` — custom base type with a b-tree
  opclass and `min`/`max`/`sum` aggregates.
- `[[knowledge/subsystems/access-nbtree]]` — the dimension-blind `unit_cmp`
  feeding the b-tree opclass (must be total, may not throw).

## Anthropology takeaway

postgresql-unit is the corpus's clearest **"typed algebra inside one SQL type"**:
the SQL type is a single `unit`, but every datum carries an 8-integer dimension
vector and the operators enforce dimensional analysis at runtime — `m + s`
errors, `m * s` synthesizes `m·s`, roots demand even/triple exponents. That is a
correctness layer core's static type system can't express, retrofitted entirely
through operator bodies. Two divergences are worth a future `knowledge/issues`
note. (a) Output depends on four session GUCs, so a `unit` column's *text* is
`STABLE`, not `IMMUTABLE` — the same I/O-purity bend as uuidv47 but milder (value
preserved, never throws). (b) The input function runs SQL against extension
tables during lexing (hence the `search_path = @extschema@` requirement on every
`unit_parse` caller), making the type's literal grammar data-driven and
runtime-mutable — a parser that queries the catalog is a long way from a
self-contained scanner, and a clean cautionary contrast for anyone modeling a
"cheap immutable I/O function" assumption in the planner.

## Sources

Fetched 2026-06-30 (branch `master`):

- `https://raw.githubusercontent.com/df7cb/postgresql-unit/master/README.md`
  → HTTP 200 (569 lines; spec, GUCs, lookup-table resolution, `@` conversion,
  GNU Units import). Note: an initial batch fetch transiently returned the
  unrelated TopN README; the doc cites only the verified 569-line unit README.
- `.../master/unit.control` → HTTP 200 (7 lines; `relocatable=false`,
  `requires='plpgsql'`).
- `.../master/unit.h` → HTTP 200 (163 lines; `Unit` struct, base-unit indices,
  the inline `test_same_dimension` + add/sub/mul/div internals — deep-read).
- `.../master/unit.c` → HTTP 200 (1432 lines; I/O, `_PG_init`+GUCs,
  `unit_cstring` output formatter, all operators, both comparison families,
  `unit_reset` — deep-read).
- `.../master/powers.c` → HTTP 200 (35 lines; generator for the rounded-down
  powers-of-ten table).
- `.../master/powers.h` → HTTP 200 (26 lines; generated constants).
- `.../master/defined_units.h` → HTTP 200 (40 lines; 8 base + 17 derived SI
  names compiled in).
- `.../master/float8out_unit.h` → HTTP 200 (34 lines; vendored pre-12
  `float8out_internal`).

NOT fetched (noted gaps): `unitparse.tab.c`/`unit.y` (the generated bison parser)
— its existence and SQL-querying lexer behavior rest on `unit.h:86` (`unit_parse`
declared "in unit.y") plus `README.md:17-18, 187-194` `[from-README]`, not a read
of the grammar itself; `definitions.units` and the install/upgrade SQL scripts
were not fetched, so the catalog-table DDL and `unit_load()` body are cited from
`README.md` `[from-README]` rather than from source.

All other cites are `[verified-by-code]` against the fetched C/H files except
where tagged `[from-README]`, `[from-comment]`, or `[inferred]`.
