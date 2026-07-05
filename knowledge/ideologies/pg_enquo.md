# pg_enquo — custom types whose comparison operators sort and index CIPHERTEXT while the key never touches the server

> Ideology note produced by the pg-extension-anthropologist cloud routine.
> Repo: `enquo/pg_enquo` @ branch `main`, fetched 2026-07-05.
> Caveat: characterization based on the files actually fetched — `README.md`,
> `Cargo.toml`, `pg_enquo.control`, `src/lib.rs`, and every type module it
> declares (`src/ore.rs`, `src/bigint.rs`, `src/boolean.rs`, `src/date.rs`,
> `src/text.rs`) plus `src/test_helpers.rs` and `doc/development.md`. The
> cryptography itself lives in the **external `enquo-core` crate** (`= 0.9.1`,
> declared in `Cargo.toml`) which is NOT in this repo; its ORE / searchable-
> encryption internals are therefore `[inferred]` / `[from-README]`, cited from
> how this repo *uses* the crate's `I64` / `Boolean` / `Date` / `Text` / `ORE` /
> `Kith` / `Root` / `Field` types, not from the crate source. Probes that 404'd:
> `pg_enquo.control.in`, `src/config.rs`, `src/root_key.rs` — there is **no** GUC
> or key-material module in this repo (confirmed: `src/lib.rs` has no `_PG_init`
> beyond `pg_module_magic!()`).

## Domain & purpose

pg_enquo provides **Encrypted Query Operations**: SQL column types that hold
values encrypted *client-side* (the server never holds the decryption key), yet
still support equality, ordering (`< > <= >=`), and indexing **inside Postgres,
against the ciphertext**. Its thesis: you should be able to run
`WHERE bi < $1` and `ORDER BY bi` and `CREATE INDEX ... (bi)` on an encrypted
column without the database ever seeing plaintext or a key, by storing an
**order-revealing-encryption (ORE)** ciphertext whose byte structure encodes
plaintext order under a keyed transform the client already applied
[from-README, README.md:1-3; verified-by-code, bigint.rs tests
`querying_without_left_ciphertexts`]. It is "typically used in conjunction with
a client library that produces Enquo ciphertexts" — the client encrypts, the
server only compares [from-README, README.md:3]. This is a distinct security
axis from at-rest page encryption ([[pg_tde]]) and from server-side crypto
functions that take the key as an argument ([[pgsodium]]): here the **ciphertext
itself is the queryable, sortable, indexable datum** and the key stays entirely
off-server.

## How it hooks into PG

Load model is `CREATE EXTENSION pg_enquo` — it is a real extension, not a
preload library. The control file is pgrx boilerplate: `default_version = '0.0'`,
`relocatable = false`, `superuser = false` (a non-superuser with `CREATE` on the
database can install it) [verified-by-code, pg_enquo.control:1-5]. It is a
**pgrx** extension (`pgrx = "=0.12.8"` pinned exactly; `enquo-core = "0.9.1"`;
`crate-type = ["cdylib", "lib"]`) targeting PG 12-17 via cargo features
[verified-by-code, Cargo.toml]. Build/test is the pgrx toolchain
(`cargo pgrx run` / `cargo pgrx test`), not PGXS or meson
[from-README, doc/development.md:9-25].

`src/lib.rs` is nearly empty: it declares the type modules (`bigint`, `boolean`,
`date`, `ore`, `text`), re-exports `ore::*`, and calls `pg_module_magic!()`
[verified-by-code, lib.rs:1-15]. There is **no `_PG_init`, no hook, no GUC, no
background worker, no shared memory** — every SQL object is emitted by pgrx
derive macros. Concretely, each type is a Rust newtype wrapping an `enquo-core`
datatype, and the pgrx derives generate the whole catalog surface:

- `#[derive(PostgresType)]` → a `pg_type` entry + text/binary I/O functions.
  The text representation is **JSON** (`serde_json`): the tests insert a value by
  casting a `serde_json::to_string(&value)` string literal to the type
  (`'{...}'::enquo_bigint`) [verified-by-code, bigint.rs `data_insertion`,
  `querying_without_left_ciphertexts`]. The on-disk storage is a pgrx-managed
  varlena [inferred, pgrx `PostgresType` default].
- `#[derive(PostgresEq)]` → the `=` / `<>` operators + a hash/eq support surface.
- `#[derive(PostgresOrd)]` → the `< > <= >=` operators **and a B-tree operator
  class**, so an encrypted column is indexable with a stock `CREATE INDEX`
  [verified-by-code, bigint.rs `type_has_operators`, `create_test_index` uses a
  plain `CREATE INDEX bigint_test_idx ON bigint_tests(bi)`].
- `enquo_text` additionally derives `#[derive(PostgresHash)]` → a hash operator
  class, and its index test is `CREATE INDEX ... USING hash (txt)`
  [verified-by-code, text.rs:9-24, `create_test_index`].

The five SQL-visible types are `enquo_bigint` (wraps `I64`), `enquo_boolean`
(`Boolean`), `enquo_date` (`Date`), `enquo_text` (`Text`), and the ORE pair
`enquo_ore_32_8` (`ORE<8,16>`) + `enquo_kith_ore_32_8` (`Kith<ORE<8,16>>`)
[verified-by-code, respective module structs]. `enquo_text` also exposes a
`length(enquo_text) -> enquo_ore_32_8` function via `#[pg_extern]` — an encrypted
string-length that returns an ORE ciphertext you can range-query
[verified-by-code, text.rs:22-27].

## Where it diverges from core idioms

- **Comparison operators compare CIPHERTEXT and reveal plaintext order without
  decrypting.** A normal PG type's `<` operates on the plaintext value; here the
  derived B-tree opclass sorts the stored ORE ciphertexts, and the sort order
  *equals* the plaintext order because ORE encodes order into ciphertext bytes.
  The comparison consults **no key** — `ore_32_8_lt` is literally
  `left.0 < right.0.compatible_member(&left.0)`, a pure comparison of ciphertext
  structs [verified-by-code, ore.rs:26-34]. This is the core break: PG's type
  machinery assumes ordering is a property of the decrypted value; pg_enquo makes
  it a property of the ciphertext.
- **The key never reaches the server — stronger than any keyed core façade.**
  Encryption happens client-side; the test harness stands in for the client:
  `Root::new(Static::new(&[0u8;32]))` builds a key holder, `root.field(b"foo",
  b"bar")` derives a per-field context, and `I64::new(42, b"test", &field())`
  produces the ciphertext that is then `serde_json`-serialized and sent to the
  server as a string [verified-by-code, test_helpers.rs:5-11, bigint.rs
  `data_insertion`]. The server-side extension holds **zero** key material (no
  GUC, no `root_key`, no config module — 404 on `src/config.rs`,
  `src/root_key.rs`). Contrast [[uuidv47]], whose keyed-façade type still needs a
  session-key GUC *on the server* and errors when it is unset: pg_enquo needs no
  server key at all because ORE comparison is keyless by construction.
- **"Left ciphertext" leakage tradeoff surfaces as a runtime SQL failure mode.**
  A value encrypted with `I64::new(...)` is a *right* ciphertext: it can be the
  right-hand operand of a comparison (so `WHERE bi < $1` works) but two such
  values cannot be ordered against *each other* — so building a B-tree index or
  running `ORDER BY` over a column of them **fails at runtime**
  [verified-by-code, bigint.rs `indexing_without_left_ciphertexts_fails` and
  `order_by_without_left_ciphertexts_fails`, both `#[should_panic]`]. To make a
  column orderable/indexable, the client must encrypt with
  `I64::new_with_unsafe_parts(...)`, which embeds the *left* ORE ciphertext (more
  leakage — hence "unsafe") [verified-by-code, bigint.rs
  `indexing_with_unsafe_parts_succeeds`]. A well-typed, NOT-NULL column can thus
  still refuse to build an index depending only on *how the client encrypted the
  bytes* — a failure axis alien to every core type.
- **Heterogeneous operand types on one comparison operator.** The ORE query path
  compares `enquo_ore_32_8` (left) against `enquo_kith_ore_32_8` (right): the
  operator's left and right types differ [verified-by-code, ore.rs:29-34]. A
  `Kith` ("acquaintances") is a *set* of ORE ciphertexts under different
  sub-contexts; `compatible_member(&left.0)` selects the one whose crypto
  parameters match the left operand, and panics if none is compatible
  [verified-by-code, ore.rs:31-33]. Normal PG operators for a type are
  same-type; here the asymmetry is a direct projection of ORE's left/right
  ciphertext split into the type system.
- **Catalog objects are macro-generated, not hand-declared.** There is no
  `pg_type.dat`, no `pg_operator.dat`, no hand-written `CREATE FUNCTION ... AS
  'MODULE_PATHNAME'` install script in the repo — pgrx's `cargo pgrx schema`
  derives the `pg_type` / `pg_operator` / `pg_opclass` / `pg_amproc` SQL from the
  `#[derive(...)]` and `#[pg_operator]` annotations at build time
  [verified-by-code, absence of any `.sql`/`.dat`; ore.rs `#[pg_operator]`,
  bigint.rs derive list]. This is the [[pgrx]] substrate replacing the
  catalog-conventions hand-authoring path.

## Notable design decisions

- **IMMUTABLE marking is honest here — unlike a keyed façade.** The ORE
  operators are `#[pg_operator(immutable, parallel_safe)]`
  [verified-by-code, ore.rs:26]. Because the comparison is a pure function of the
  two ciphertexts and consults no key or session state, IMMUTABLE is genuinely
  correct: the same two ciphertexts always compare identically. Contrast
  [[uuidv47]], where a transform that depends on a session-key GUC is only
  *nominally* immutable — the I/O-purity tension that bites keyed types does not
  bite pg_enquo, precisely because it moved the key off the server.
- **`negator` metadata is wired for the planner.** Each ORE operator declares its
  negator (`<` negates `>=`, `>` negates `<=`, etc.) via `#[negator(...)]`
  [verified-by-code, ore.rs:27-28, 36-37, 45-46, 54-55], so the planner can
  reason about `NOT (a < b)` even over ciphertext.
- **Encrypted `length()` as a first-class queryable projection.**
  `length(enquo_text)` returns an `enquo_ore_32_8`, and the tests range-query it:
  `WHERE length(txt) > $1::enquo_kith_ore_32_8` counts rows by *encrypted string
  length* without decrypting the text [verified-by-code, text.rs:22-27 and
  `length_querying`]. The `Text` ciphertext optionally carries a
  length-as-ORE payload; extracting it panics if absent
  [verified-by-code, text.rs:23-25].
- **Text equality can be hash-indexed; ordering needs the unsafe left part.**
  `enquo_text` derives `PostgresHash` (hash opclass for `=`) but still fails to
  build even a hash index unless the ciphertext carries the required hash value
  (`new` fails, `new_with_unsafe_parts` succeeds)
  [verified-by-code, text.rs `indexing_text_without_hash_value_fails`
  vs `indexing_text_with_unsafe_parts_succeeds`].
- **Fixed ORE geometry `ORE<8,16>` / `enquo_*_32_8`.** The one ORE type shipped is
  `ORE<8, 16>` surfaced as `enquo_ore_32_8` — a fixed block/parameter geometry
  baked into the type name [verified-by-code, ore.rs:20]. Widening the domain
  means a new named type, not a parameter.
- **Zero server-side configuration surface.** No `DefineCustomVariable`, no
  `MarkGUCPrefixReserved`, no hook chaining — the extension's entire behavior is
  types + operators. Everything policy-like (which key, which field context,
  whether to include unsafe parts) is a **client-side** decision baked into the
  ciphertext before it ever arrives [verified-by-code, lib.rs:1-15;
  test_helpers.rs:5-11].

## Links into corpus

- [[pgrx]] — the Rust framework substrate. Every catalog object here is a pgrx
  derive (`PostgresType` / `PostgresEq` / `PostgresOrd` / `PostgresHash`) or
  `#[pg_operator]` / `#[pg_extern]`; the JSON text I/O and varlena storage are
  pgrx defaults.
- [[pg_tde]] — the at-rest / page-level encryption axis: pg_tde decrypts pages so
  the server operates on plaintext; pg_enquo never decrypts and operates on
  ciphertext. Same word "encryption", opposite trust boundary.
- [[pgsodium]] — libsodium crypto *functions* where the key is handed to the
  server (or held in server-managed key material); contrast pg_enquo's key-never-
  on-server model.
- [[uuidv47]] — the closest sibling: a keyed-façade custom type. But uuidv47
  keeps its key in a session GUC on the server and bends I/O purity to read it;
  pg_enquo keeps the key entirely client-side and its operators are honestly
  IMMUTABLE. The instructive contrast on "where does the key live".

## Sources

- `https://raw.githubusercontent.com/enquo/pg_enquo/main/README.md` — HTTP 200.
  Thesis + client-library dependence.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/Cargo.toml` — HTTP 200.
  `enquo-core = "0.9.1"` (external crypto crate), `pgrx = "=0.12.8"`,
  `crate-type = ["cdylib","lib"]`, pg12-pg17 features.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/pg_enquo.control` —
  HTTP 200. pgrx boilerplate; `superuser = false`, `relocatable = false`,
  `default_version = '0.0'`.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/src/lib.rs` — HTTP 200.
  Module list, `pg_module_magic!()`, no `_PG_init`/GUC/hook.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/src/ore.rs` — HTTP 200.
  `enquo_ore_32_8` / `enquo_kith_ore_32_8`, the four `#[pg_operator]` ORE
  comparisons, `compatible_member`.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/src/bigint.rs` —
  HTTP 200. `enquo_bigint(I64)`; the left/right-ciphertext test matrix
  (`querying_without_left_ciphertexts`, `indexing_without_left_ciphertexts_fails`,
  `indexing_with_unsafe_parts_succeeds`, `order_by_without_left_ciphertexts_fails`).
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/src/text.rs` — HTTP 200.
  `enquo_text(Text)` + `PostgresHash`, `length()` → `enquo_ore_32_8`, encrypted
  length querying, hash-index tests.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/src/boolean.rs` —
  HTTP 200. `enquo_boolean(Boolean)`; same left/right-ciphertext test pattern.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/src/date.rs` — HTTP 200.
  `enquo_date(Date)`; same pattern.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/src/test_helpers.rs` —
  HTTP 200. `field()` builds `Root::new(Static::new(&[0u8;32]))` →
  `root.field(b"foo", b"bar")` — the client-side key/field derivation the server
  never performs.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/doc/development.md` —
  HTTP 200. `cargo pgrx` build/test workflow.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/pg_enquo.control.in` —
  HTTP 404. No `.in` template; the checked-in `.control` is the pgrx-generated one.
- `https://raw.githubusercontent.com/enquo/pg_enquo/main/src/config.rs`,
  `.../src/root_key.rs` — HTTP 404. No server-side key/config module exists; key
  material is exclusively client-side (see `test_helpers.rs`).
- `enquo-core` crate internals (ORE construction, `Kith`, left/right ciphertext,
  `new_with_unsafe_parts` leakage semantics) — external dependency, NOT in this
  repo; characterized `[inferred]` from usage sites above.
- `https://api.github.com/repos/enquo/pg_enquo/git/trees/main?recursive=1` — not
  used (GitHub tree API blocked for this session); module set enumerated from
  `src/lib.rs` `mod` declarations and fetched via raw CDN.
