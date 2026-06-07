# Apache AGE — a second query language (openCypher) spliced in at post-parse-analyze

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `apache/age` @ branch `master`. All `file:line` cites below point into
> that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-06 (see Sources footer).

## Domain & purpose

Apache AGE ("A Graph Extension") turns PostgreSQL into a **multi-model graph
database**: it lets you store property graphs (labeled vertices and edges) and
query them in **openCypher** — Neo4j's declarative graph language — embedded
inside ordinary SQL, e.g. `SELECT * FROM cypher('g', $$ MATCH (a)-[]->(b) RETURN
a,b $$) AS (a agtype, b agtype);` (`README.md`). For an anthropologist this is
the most ambitious divergence in the corpus: AGE does not add a type or an index
or a hook for instrumentation — it embeds **an entire foreign query language**,
with its own lexer, grammar, keyword set, parse nodes, semantic analyzer, and
runtime type, and makes core PostgreSQL execute it by *intercepting parse
analysis and substituting a separately-built query tree*. It is the worked
answer to: *how far can the hook system be pushed — can an extension make
Postgres speak a language its own gram.y has never heard of?*

## How it hooks into PG

`PG_MODULE_MAGIC` (`src/backend/age.c:53`). `_PG_init`
(`src/backend/age.c:57-72`) is unusually busy — it installs **seven** distinct
pieces of machinery `[verified-by-code]`:

1. `register_ag_nodes()` — registers AGE's custom extensible `Node` types with
   core's node system so they survive copy/equal/out/read.
2. `set_rel_pathlist_init()` — chains `set_rel_pathlist_hook` to add custom
   scan paths for graph relations.
3. `object_access_hook_init()` — chains `object_access_hook` to track
   DROP/DDL on graph objects.
4. `process_utility_hook_init()` — chains `ProcessUtility_hook` for graph DDL.
5. `post_parse_analyze_init()` — chains `post_parse_analyze_hook`; **this is the
   load-bearing one** (see Divergence 1).
6. `shmem_request_hook` + `shmem_startup_hook` — reserve/init shared state
   (`age.c:69-72`), each chaining the previous (`age.c:34-49`).

The control file pins `schema = 'ag_catalog'` (`age.control`) and
`default_version = '1.7.0'`.

## Where it diverges from core idioms

### 1. It rewrites the query tree at `post_parse_analyze_hook`, swapping a `cypher()` call for a separately-parsed subquery

The defining divergence. AGE exposes a sentinel set-returning function
`cypher(graph, query_string)`. The `post_parse_analyze_hook` callback
`post_parse_analyze` (`src/backend/parser/cypher_analyze.c:73-95`) runs after
core finishes analyzing *every* statement; it chains the previous hook
(`:84-86`) and then sends the analyzed `Query` through `convert_cypher_walker`
(`:95`). That walker (`cypher_analyze.c:116-215`) recurses the tree looking for
`cypher()`: when it finds one as a `RangeTblEntry` of kind `RTE_FUNCTION` in a
FROM clause (`is_rte_cypher`, `:131`), it calls `convert_cypher_to_subquery`
(`:132`), which **lexes and parses the Cypher string with AGE's own
scanner/parser, analyzes it into a fresh `Query`, and replaces the RTE in place
— turning `RTE_FUNCTION` into `RTE_SUBQUERY`** (`:247` comment: "We convert
RTE_FUNCTION (cypher()) to RTE_SUBQUERY (SELECT)"). The actual Cypher analysis
is `analyze_cypher`/`analyze_cypher_and_coerce` (`:62-65`). Cypher used anywhere
*other* than a FROM-clause RTE — in an expression, or in `ROWS FROM(...)` — is
explicitly rejected with a friendly error (`cypher_analyze.c:153-157, 205-209`).
So core's planner and executor never know they're running graph queries: by the
time they see the tree, the `cypher()` call has been transparently replaced by a
normal SQL subquery AGE synthesized. Hijacking `post_parse_analyze_hook` to
*substitute* subtrees — rather than merely inspect them, as auto_explain does —
is an extraordinarily deep use of a hook meant for read-mostly post-processing.
Cross-ref `[[knowledge/subsystems/parser]]`, `.claude/skills/parser-and-nodes/SKILL.md`,
`.claude/skills/executor-and-planner/SKILL.md`.

### 2. A complete parallel parser stack: flex scanner, bison grammar, keyword table

To do (1), AGE ships its own front end mirroring core's `src/backend/parser/`
file-for-file: a flex scanner `parser/ag_scanner.l`, a bison parser
`parser/cypher_parser.c` (from a `cypher_gram.y`), a dedicated keyword table
`parser/cypher_keywords.c`, a parse-state shim `parser/cypher_parse_node.c`, and
aggregate handling `parser/cypher_parse_agg.c`. Core assumes exactly one grammar
(`gram.y`) and one keyword list (`kwlist.h`); AGE runs a *second, independent*
grammar with its own keywords inside the same backend, invoked only for strings
handed to `cypher()`. Building and maintaining a shadow of the entire parser
subsystem is something no in-core feature does. Cross-ref
`.claude/skills/parser-and-nodes/SKILL.md`.

### 3. Cypher clauses are lowered to PostgreSQL `Query` nodes by hand

`parser/cypher_clause.c` (the largest analyzer file) is a transformation layer
that turns each Cypher clause — `MATCH`, `CREATE`, `MERGE`, `WHERE`, `RETURN`,
`WITH` — into the equivalent core `Query`/`FromExpr`/`JoinExpr`/`TargetEntry`
structures, so that a graph pattern match becomes a tree of self-joins over the
label tables. AGE is effectively a *source-to-source compiler* from Cypher to
PostgreSQL's internal query representation, living entirely in an extension.
This is the graph analog of what a planner does for SQL, re-implemented above
the line core draws. Cross-ref `[[knowledge/subsystems/parser]]`,
`[[knowledge/subsystems/optimizer]]`.

### 4. Custom extensible Node types registered into core's node machinery

`register_ag_nodes()` (`age.c:59`) registers AGE's bespoke parse/plan nodes
(cypher clause nodes, etc.) as **extensible nodes** so core's
copyObject/equal/outNode/readNode infrastructure can serialize them — required
because AGE's intermediate trees flow through core code paths that copy and
compare nodes. Using the extensible-node escape hatch (`ExtensibleNode`) for an
entire alternative AST is a heavyweight use of a facility core provides mainly
for custom scan/path plug-ins. Cross-ref `.claude/skills/parser-and-nodes/SKILL.md`.

### 5. `agtype` — a jsonb-superset value type as the universal graph datum

Every value crossing the Cypher/SQL boundary is `agtype`
(`src/backend/utils/adt/agtype.c`, a ~400 KB file). It is a superset of `jsonb`
extended with graph-native notions (vertices, edges, paths, and numeric
distinctions Cypher needs), with a full `datum_to_agtype` type-category switch
(`agtype.c:78-81+`) and its own operators, aggregates (including a percentile
aggregate state, `agtype.c:65-74`), and I/O. Rather than reuse `jsonb`
unchanged, AGE forks its semantics into a new type so Cypher's data model is
first-class. Cross-ref `[[knowledge/idioms/varlena]]`,
`.claude/skills/catalog-conventions/SKILL.md`.

## Notable design decisions (cited)

- **Every hook chains the predecessor.** `post_parse_analyze` (`:84-86`), and
  both shmem hooks (`age.c:34-49`), call the previous hook first — AGE composes
  cleanly with other extensions despite the depth of its intervention.
- **Cypher is confined to FROM-clause RTEs by design.** The walker rejects
  `cypher()` in expressions and `ROWS FROM` (`cypher_analyze.c:153-215`) so the
  substitution always has a well-defined subquery slot to land in — a deliberate
  scoping of where the language transplant is legal.
- **Fail-soft to the real error site.** When it sees `cypher()` somewhere it
  can't convert, it leaves the node alone so the function's own runtime error
  fires later with a clearer message (`cypher_analyze.c:148-153` comment).
- **`_PG_fini` actually tears everything down** (`age.c:78-83`) — unusually, AGE
  un-chains all its hooks on unload, where most extensions ignore `_PG_fini`.
- **Schema-pinned, non-relocatable** (`age.control`, `schema = 'ag_catalog'`):
  the graph catalog tables and the `agtype`/`cypher()` machinery must live in a
  known schema the C code references.

## Links into corpus

- `[[knowledge/subsystems/parser]]` — `post_parse_analyze_hook`, `ParseState`,
  `Query`/`RangeTblEntry` rewriting, and the parallel scanner/grammar AGE runs.
- `.claude/skills/parser-and-nodes/SKILL.md` — extensible nodes, the
  `query_tree_walker` AGE drives, and the second keyword table.
- `[[knowledge/subsystems/optimizer]]` — `set_rel_pathlist_hook` custom paths
  for graph relations, and Cypher-to-Query lowering as a compiler stage.
- `[[knowledge/idioms/varlena]]` — `agtype` as a jsonb-superset value type.
- `[[knowledge/ideologies/citus]]` — the other "rewrite the query tree from a
  hook" extension (Citus rewrites for distribution; AGE rewrites for a new
  language); good contrast in *why* one hijacks the planner pipeline.
- `.claude/skills/extension-development/SKILL.md` — the multi-hook `_PG_init`
  install/chain/teardown pattern AGE exemplifies.

## Sources

Fetched 2026-06-06 (branch `master`; repo added to the queue this run as the
refill candidate after `pg_top` was judged out of scope — see run log). The
queue manifest for AGE was synthesized from the tree listing (the original queue
entry was `markwkm/pg_top`, skipped). Files fetched:

- `https://raw.githubusercontent.com/apache/age/master/README.md`
  @ 2026-06-06 → HTTP 200 (HTML-heavy; usage example + "multi-model graph
  database" framing).
- `https://raw.githubusercontent.com/apache/age/master/age.control`
  @ 2026-06-06 → HTTP 200 (`default_version = '1.7.0'`, `schema = 'ag_catalog'`).
- `https://raw.githubusercontent.com/apache/age/master/src/backend/age.c`
  @ 2026-06-06 → HTTP 200 (2366 bytes; the `_PG_init`/`_PG_fini` hook installs).
- `https://raw.githubusercontent.com/apache/age/master/src/backend/parser/cypher_analyze.c`
  @ 2026-06-06 → HTTP 200 (36 KB; the `post_parse_analyze_hook` + walker +
  RTE_FUNCTION→RTE_SUBQUERY conversion).
- `https://raw.githubusercontent.com/apache/age/master/src/backend/utils/adt/agtype.c`
  @ 2026-06-06 → HTTP 200 (401 KB; `agtype` type, only the header/category
  region cited).
- Tree listing
  `https://api.github.com/repos/apache/age/git/trees/master?recursive=1`
  @ 2026-06-06 → HTTP 200 (432 paths; the parallel `src/backend/parser/*` and
  `src/include/parser/*` stacks enumerated for Divergence 2).

Cites into `age.c` and `cypher_analyze.c` (the hook installs, the
`convert_cypher_walker`, the RTE substitution, the FROM-only restriction) are
`[verified-by-code]` against the fetched files. Divergences 2–3 (the flex/bison
shadow stack and the clause-lowering in `cypher_clause.c`) are
`[verified-by-code]` for the *existence and role* of the files (from the tree +
the `age.c` includes `optimizer/cypher_paths.h`, `parser/cypher_analyze.h`) but
their bodies were not fetched line-by-line this run; the per-clause lowering
detail is `[inferred]` from the file names and the analyzer entry points.
</content>
