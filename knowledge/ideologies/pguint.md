# pguint — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `petere/pguint` @ branch `master` (Peter Eisentraut). All `file:line`
> cites point into that repo (not `source/`). Cites verified against files
> fetched 2026-07-04 (see Sources footer). Read alongside the sibling
> custom-type notes `[[knowledge/ideologies/postgresql-unit]]` and
> `[[knowledge/ideologies/uuidv47]]`, and the contrib exemplar
> `[[knowledge/subsystems/contrib-isn]]`.

## Domain & purpose

pguint adds the integer scalar types PostgreSQL core deliberately omits: `int1`
(signed 8-bit), and the unsigned family `uint1`/`uint2`/`uint4`/`uint8`
(`README.md:1-11`) `[from-README]`. Each type ships a full backend citizen's
kit — text I/O, the comparison + arithmetic + bitwise operator sets, btree and
hash opclasses, sort support, casts to/from the core numeric types, and the
`min`/`max`/`sum`/`avg`/`bit_and`/`bit_or` aggregates — so the new types behave
"like the standard integer types" (`README.md:36-51`) `[from-README]`. The
README is candid that this is as much a stress test of the extension mechanism
as a practical feature: core rejects extra integer types because the SQL
standard's type-promotion rules force a *comprehensive* per-type-pair operator
set, and "you do the math" on the 8×8 cross-product (`README.md:57-79`)
`[from-README]`. pguint's entire ideology is a response to that combinatorial
blowup: **generate the cross-product instead of hand-writing it.**

## How it hooks into PG

Pure base-type + C-function + SQL-DDL extension. No `_PG_init`, no
`shared_preload_libraries`, no planner/utility hooks — the only module-level
symbol is `PG_MODULE_MAGIC` in its own translation unit (`magic.c:1-4`)
`[verified-by-code]`. It is `relocatable = true` (`uint.control:1-4`)
`[verified-by-code]`. Concretely it hooks in via:

- **Base-type registration by DDL, not catalog `.dat`.** Each type uses the
  shell-type two-step: `CREATE TYPE int1;` (shell) → declare `int1in`/`int1out`
  → full `CREATE TYPE int1 (INPUT=…, OUTPUT=…, INTERNALLENGTH=1, PASSEDBYVALUE,
  ALIGNMENT=char)` (`uint.sql:1-21`) `[verified-by-code]`. All five types are
  fixed-width, pass-by-value, aligned to `char`/`int2`/`int4`/`double`
  (`uint.sql:15-21,46-52,77-83,108-114,139-145`) `[verified-by-code]`.
- **Scalar C functions via `PG_FUNCTION_INFO_V1`** — the dynamic fmgr V1
  protocol, e.g. `int1in`/`uint4in`/`uint8out` (`inout.c:63-257`)
  `[verified-by-code]`. No entry ever lands in core's static `fmgrtab`.
- **Operator classes for btree and hash**, generated per new type, declared
  `DEFAULT FOR TYPE <t> USING btree/hash FAMILY integer_ops`
  (`generate.py:277-293`) `[verified-by-code]`.
- **Casts** — `CREATE CAST … WITH INOUT` to/from `double precision`, `numeric`,
  `real` are hand-written (`uint.sql:23-29`), while every inter-integer cast is
  code-generated `WITH FUNCTION` (`generate.py:519-523`) `[verified-by-code]`.
- **Aggregates** via `CREATE AGGREGATE` with generated SFUNCs
  (`generate.py:549-590`) `[verified-by-code]`.
- **PGXS build.** `MODULE_big = uint`, `EXTENSION = uint`, `OBJS = aggregates.o
  hash.o hex.o inout.o magic.o misc.o operators.o` (`Makefile:15-18`)
  `[verified-by-code]`. `operators.c`/`operators.sql` do not exist in the repo;
  they are produced at build time by `python generate.py` (`Makefile:38-40`)
  `[verified-by-code]`.

## Where it diverges from core idioms

### 1. The operator/cast/aggregate matrix is *metaprogrammed* (the headline)

Core hand-writes every builtin integer function — `int4pl`, `int48pl`,
`int84lt`, … live as literal C in `src/backend/utils/adt/int.c`/`int8.c` and as
fixed rows in `pg_proc.dat`/`pg_operator.dat`/`pg_opclass.dat`. pguint instead
runs a Python metaprogram (`generate.py`) whose `main()` loops over
`new_types + old_types` × `new_types + old_types`, skipping the all-core pairs
(`if lefttype in old_types and righttype in old_types: continue`), and for each
surviving pair emits: six comparison operators, a `bt<L><R>cmp` three-way
comparator, five arithmetic operators, and (when the types differ) a cast
(`generate.py:456-523`) `[verified-by-code]`. `write_op_c_function` synthesizes
the C body; `write_sql_operator` synthesizes the `CREATE OPERATOR` with
`COMMUTATOR`/`NEGATOR`/`RESTRICT`/`JOIN`/`HASHES`/`MERGES` filled from lookup
tables (`generate.py:143-230`) `[verified-by-code]`. The mapping from SQL type
name to C type is a single dict (`generate.py`, `c_types`) `[verified-by-code]`.
This is the corpus's purest example of *type-cross-product-as-code-generation*
versus core's hand-maintained per-type functions.

### 2. It injects its types into core's *existing* `integer_ops` families

Rather than defining private opfamilies, pguint's per-type opclasses join
`FAMILY integer_ops` (`generate.py:278-291`), and the generator then emits
`ALTER OPERATOR FAMILY integer_ops USING btree ADD …` / `… USING hash ADD …`
carrying the loose cross-type OPERATOR/FUNCTION members
(`generate.py:614-637`) `[verified-by-code]`. Effect: an index on a `uint4`
column can satisfy `WHERE x = 3::int4` because the new type and the core type
sit in one amop/amproc family (the test harness asserts exactly this with
`EXPLAIN (COSTS OFF) … WHERE x = 3::{righttype}`, `generate.py:609-611`)
`[verified-by-code]`. Extending a *core-owned* catalog object from an extension
is itself a divergence from the usual "extensions own their own catalog rows"
posture — see `[[knowledge/idioms/catalog-conventions]]`.

### 3. Arithmetic errors on overflow — never wraps — and the checks are derived

Like core's `int4pl` (which raises `ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE`), every
generated arithmetic op appends a computed `c_check` guard that `ereport(ERROR)`s
`"integer out of range"` (`generate.py:194-200`) `[verified-by-code]`. The novel
part is that `write_arithmetic_op` *derives* the correct overflow predicate from
signedness and width: unsigned `+` uses `result < arg1 || result < arg2`; signed
`+` uses core's `SAMESIGN(arg1,arg2) && !SAMESIGN(result,arg1)`; mixed
signed/unsigned `+`/`-` get bespoke predicates; and `*` widens into the
`next_bigger_type` and checks the truncation, falling back to a divide-back check
at 64-bit width (`generate.py:326-390`) `[verified-by-code]`. `SAMESIGN` is
lifted verbatim from core (`uint.h:44`) `[verified-by-code]`. So the semantics
match core (trap, don't wrap) but the *implementations* are a generator's output,
not human-audited functions.

### 4. Casts encode signed↔unsigned range checks; widening is IMPLICIT

The generated cast body starts `result = arg1;` and conditionally appends a
truncation check (`if ((<Ltype>) result != arg1) ereport…`) when the source is
at least as wide, plus a sign check (`if (!SAMESIGN(result, arg1)) ereport…`)
whenever signedness differs (`generate.py:504-516`) `[verified-by-code]`. Cast
context is width-driven: **IMPLICIT when widening, ASSIGNMENT otherwise**
(`generate.py:519-523`) `[verified-by-code]` — mirroring core's policy that
narrowing integer casts must be explicit/assignment. The float/numeric casts are
declared `WITH INOUT` (relying on text I/O) rather than dedicated functions
(`uint.sql:23-29`) `[verified-by-code]`.

### 5. Hash values are chosen to *match* the core integer hash

`hashuint8` deliberately reproduces core `hashint8`'s fold — `lohalf ^= hihalf;
return hash_uint32(lohalf)` with a `/* see also hashint8 */` comment
(`hash.c:21-33`) `[verified-by-code]`; the narrower types cast up to `uint32`
and call `hash_uint32` (`hash.c:7-19`) `[verified-by-code]`. Matching hashes is
what lets the new types share the hash `integer_ops` family (§2) and hash-join
against core `int4`/`int8` — see `[[knowledge/idioms/fmgr]]` for the V1 dispatch
these use.

### 6. Aggregates reuse core's int8 accumulator layout, with a known gap

`avg` reuses core's two-element `int8` transition array and finalizes with
core's `int8_avg` (`generate.py:582-586`); its accumulator
`<t>_avg_accum` casts the incoming value into an `Int8TransTypeData
{int64 count; int64 sum;}` — the same struct core uses
(`aggregates.c:29-63`) `[verified-by-code]`. `sum` widens the transition type
per a `sum_trans_types` map (e.g. `uint2 → uint8`), but `uint8_sum` accumulates
into a `uint8` and carries a `// FIXME: should use numeric` (`aggregates.c:26`)
`[verified-by-code]` — i.e. `sum(uint8)` can silently overflow, unlike core's
`sum(bigint) → numeric`. A rare place the metaprogram's uniformity undershoots
core's care.

### 7. The generator patches *core's own* `%` operator set

The most surprising divergence: after emitting its own matrix, `main()` adds
four purely-core cross-type modulo operators — `(int2,int4)`, `(int4,int2)`,
`(int8,int2)`, `(int8,int4)` — because core supplies `%` only for same-type
pairs and relies on promotion; the presence of pguint's extra integer types
changes overload resolution and *breaks the core regression tests*, so the
extension repairs core's operator set to "unbreak this" (`generate.py:639-653`,
citing the 2008 pgsql-hackers thread) `[verified-by-code]`. The README's testing
note — run the *main PG regression suite* with pguint loaded and expect no
changes (`README.md:81-92`) `[from-README]` — is the same concern institutional-
ized: the extension must be transparent to existing expression interpretation.

## Notable design decisions

- **No fixed OIDs, no bootstrap.** Everything is created by DDL at
  `CREATE EXTENSION` time (`uint.sql`, generated `operators.sql`), so all
  types/operators get dynamically-assigned OIDs — the opposite of core's
  fixed-OID `pg_type.dat` bootstrap. Contrast `[[knowledge/idioms/catalog-conventions]]`.
- **64-bit only.** `uint8` is declared `PASSEDBYVALUE -- requires 64-bit`
  (`uint.sql:143`) and the README restricts to 64-bit builds
  (`README.md:14-16`) `[verified-by-code]`/`[from-README]`. `uint.h` guards
  `DatumGetUInt64`/`UInt64GetDatum` on `USE_FLOAT8_BYVAL` (`uint.h:17-33`)
  `[verified-by-code]`.
- **Version-portability shims in `uint.h`.** It redefines `DatumGetInt8`
  around `GET_1_BYTE`, and version-gates `Int8GetDatum` for `PG_VERSION_NUM >=
  190000` and the `DatumGetUInt64` macros for `< 90600` (`uint.h:5-40`)
  `[verified-by-code]` — a single header absorbing a decade of fmgr ABI drift.
- **`%` is exposed as a `mod` function, not a `%` operator name**, per the SQL
  standard (`generate.py:207-211`) `[verified-by-code]`.
- **One operator escapes the generator.** Unary minus doesn't fit the binary
  matrix, so `int1um` is hand-written in C (`misc.c:7-21`) with its own overflow
  trap and hand-declared `CREATE OPERATOR - (PROCEDURE=int1um, RIGHTARG=int1)`
  (`uint.sql:156-161`) `[verified-by-code]`.
- **`int1out` prints via `%d` on an `int8` C value** into a `palloc(5)` buffer
  (`inout.c:72-81`) `[verified-by-code]` — `int1`'s C representation is `int8`
  throughout (`c_types['int1'] = 'int8'`), a deliberate "store narrow, compute
  wide" choice.
- **Input parsing is core code, cut down.** `my_pg_atoi8` is "a copy of old
  `pg_atoi()` from PostgreSQL, cut down to support int8 only" (`inout.c:11-61`),
  and `pg_atou` is a hand-written unsigned parser rejecting any `-`
  (`inout.c:83-144`) `[verified-by-code]`/`[from-comment]`.
- **Sort support is generated too** — a `bt<t>fastcmp` + `bt<t>sortsupport`
  pair per type, wired into the btree opclass as support function 2
  (`generate.py:249-293`) `[verified-by-code]`.
- **`hex.c` adds `to_hex(uint4)`/`to_hex(uint8)`** paralleling core's `to_hex`
  for signed ints (`hex.c:9-38`) `[verified-by-code]`.
- **Zero-ish versioning.** `extension_version = 0` (`Makefile:12`) /
  `default_version = 0` (`uint.control:2`) `[verified-by-code]` — no upgrade
  scripts; the extension has never left version 0.

## Links into corpus

- `[[knowledge/idioms/catalog-conventions]]` — the fixed-OID `pg_type.dat`/
  `pg_proc.dat` bootstrap that pguint sidesteps by doing everything via DDL, and
  the "extensions own their catalog rows" norm §2 violates by `ALTER`-ing
  `integer_ops`.
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` dynamic dispatch every
  pguint C function rides.
- `[[knowledge/idioms/portable-identifiers]]` — companion for the
  `uint.h` version-gating shims.
- `[[knowledge/subsystems/contrib-isn]]` — in-tree exemplar of a "make a new
  scalar type with full operator/opclass/cast kit" contrib module, for contrast
  with pguint's generated approach.
- `[[knowledge/ideologies/postgresql-unit]]`, `[[knowledge/ideologies/uuidv47]]`
  — sibling custom-base-type ideology notes.

## Sources

GitHub git/trees API and the codeload tarball endpoint were **unusable this
session** (403 "not enabled" — session scoped to a different repo), so the file
set was reconstructed from `Makefile` `OBJS` + `raw.githubusercontent.com`
probes rather than a directory listing. All fetched 2026-07-04 from
`https://raw.githubusercontent.com/petere/pguint/master/<path>`, all **HTTP
200**: `README.md`, `Makefile`, `uint.control`, `uint.h`, `uint.sql`,
`generate.py`, `inout.c`, `hash.c`, `aggregates.c`, `misc.c`, `magic.c`,
`hex.c`, `hash.sql`, `hex.sql`.

Not in the repo tree (build-time output of `generate.py`, listed in
`EXTRA_CLEAN`, `Makefile:26`): `operators.c`, `operators.sql`,
`test/sql/operators.sql` — their shape is characterized from `generate.py`
directly, not fetched.
