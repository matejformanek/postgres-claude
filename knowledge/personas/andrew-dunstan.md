# Persona: Andrew Dunstan

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: git log mining of source/ + cross-cut against committer-map.md,
  contributor-map.md, domain-ownership.md.

## Role + email(s)

- Long-time committer.
- Author/committer email: `Andrew Dunstan <andrew@dunslane.net>`.
  997 historical author entries, single email. [verified-by-code]

## Activity profile (last 24mo)

| Vector                                              | Count |
|-----------------------------------------------------|------:|
| Commits as author (24mo)                            | 105   |
| `Reviewed-by: Andrew Dunstan` in others' commits    | 44    |
| Top reviewer on his own work (self-credit, "Andrew Dunstan") | 21 |

Counts via `rtk proxy git -C source/ log --since='24 months ago'
--author='Andrew Dunstan' --oneline`. [verified-by-code]

### Subsystem footprint (file touches, 24mo, top areas)

| Path                            | Touches |
|---------------------------------|--------:|
| src/bin/pg_dump                 | 71      |
| doc/src/sgml                    | 63      |
| src/test/regress                | 62      |
| src/test/fuzzing                | 26      |
| src/backend/utils               | 24      |
| src/test/modules                | 21      |
| src/backend/commands            | 21      |
| src/backend/postmaster          | 11      |
| src/tools/pgindent              | 10      |
| src/interfaces/ecpg             | 10      |
| src/bin/pg_waldump              | 10      |
| src/bin/pg_verifybackup         | 8       |

Heavily weighted toward client utilities + test infrastructure +
docs. [verified-by-code]

## Domain ownership

- **pg_dump.** 71 file touches in 24mo — the largest single area
  for him and well above any other committer's pg_dump activity in
  the same window. He is a primary maintainer of pg_dump, with a
  particular focus on schema-DDL coverage.
- **`pg_get_*_ddl()` infrastructure (2026-03-19).** A four-commit
  series introducing in-server DDL emission functions:
  - "Add infrastructure for `pg_get_*_ddl` functions"
  - "Add `pg_get_role_ddl()` function"
  - "Add `pg_get_tablespace_ddl()` function"
  - "Add `pg_get_database_ddl()` function"

  Plus follow-up fixes ("Fix `pfree` crash in `pg_get_role_ddl()`
  and `pg_get_database_ddl()`", "Avoid SIGSEGV in
  `pg_get_database_ddl()` on NULL tablespace"). This is a new
  feature surface he owns end-to-end. [verified-by-code]
- **JSON / jsonpath in pg_dump and the backend.** 18 subjects mention
  JSON/jsonpath over 24mo: "Add additional jsonpath string
  methods", "Rename jsonpath method arg tokens", "Apply encoding
  conversion in COPY TO FORMAT JSON", "Fix COPY TO FORMAT JSON to
  exclude generated columns", "Fix incremental JSON parser numeric
  token reassembly across chunks". JSON-in-pg_dump and the
  JSON COPY format are his beat. [verified-by-code]
- **Test infrastructure (TAP + pg_regress).** 25 subjects mention
  TAP / test / pg_regress over 24mo. Notable cluster on 2026-04-01:
  - "perl tap: Show failed command output"
  - "perl tap: Show die reason in TAP output"
  - "perl tap: Use croak instead of die in our helper modules"
  - "pg_regress: Include diffs in TAP output"
  - "Use `command_ok` for pg_regress calls in 002_pg_upgrade and
    027_stream_regress"

  Plus "Convert ddlutils regression tests to TAP tests" (2026-04-29).
  He is actively migrating regress→TAP and improving TAP failure
  diagnostics. [verified-by-code]
- **Fuzzing infrastructure.** 26 src/test/fuzzing/ touches in
  24mo — including "Add built-in fuzzing harnesses for security
  testing" (2026-04-09), which was reverted the next day
  ("Revert 'Add built-in fuzzing harnesses…'", 2026-04-10),
  suggesting a still-evolving feature. [verified-by-code]
- **Docs (63 doc/src/sgml touches).** Heavy doc work in tandem
  with the pg_dump and DDL-function features.

## Style + patterns

- **Title style:** plain imperative ("Add X", "Fix Y", "Convert Z
  to W"). Frequent `Revert "..."` titles — he is willing to back
  out his own features if post-merge issues surface (the fuzzing
  harness revert; recent revert of "Enable fast default for
  domains with non-volatile constraints" on 2026-06-08).
  [verified-by-code]
- **Multi-commit feature series.** The `pg_get_*_ddl` series
  (infrastructure → 3 functions in 4 commits) and the perl-TAP
  cleanup (5 commits, same day) show his pattern of landing
  related changes as small ordered commits rather than one
  monolithic patch. [verified-by-code]
- **Signal-handler refactor + reuse pattern.** "Rework signal
  handler infrastructure to pass sender info as argument"
  (2026-04-14) was followed within weeks by "Only show
  signal-sender PID/UID detail in server log" (2026-05-01) and
  "Add `errdetail()` with PID and UID about source of termination
  signal" (2026-04-06) — refactor first, then exploit.
  [verified-by-code]
- **Willingness to revert.** Two visible reverts of his own
  recent work (fuzzing harness, fast-default-domains). Treat
  his commits as moveable — reverts arrive promptly when
  issues surface.

## Common reviewer/collaborator partners

`Reviewed-by:` trailers inside his own commits (24mo):

| Reviewer            | Count |
|---------------------|------:|
| Chao Li             | 9     |
| Zsolt Parragi       | 7     |
| Jakub Wartak        | 5     |
| Corey Huinker       | 5     |
| Robert Haas         | 4     |
| Nazir Bilal Yavuz   | 4     |
| Euler Taveira       | 4     |
| Andres Freund       | 4     |
| Álvaro Herrera      | 3     |
| Tom Lane            | 3     |
| Kirill Reshke       | 3     |
| Japin Li            | 3     |

Notable: the cluster (Chao Li, Zsolt Parragi, Jakub Wartak, Corey
Huinker, Euler Taveira, Kirill Reshke) is a different
review-circle from the storage/optimizer cores — these are
pg_dump / DDL / test-infra reviewers. [verified-by-code]

Going outward: 44 commits in the 24mo window cite
`Reviewed-by: Andrew Dunstan` — mostly in the pg_dump, JSON, test
infra, and docs neighborhoods. [verified-by-code]

## What to expect on a patch he would review

- He'll review patches touching **pg_dump, pg_restore,
  pg_get_*_ddl, JSON/jsonpath surface, TAP infrastructure,
  perl helper modules, and pg_regress wiring**.
- Strong attention to **dump fidelity**: round-tripping schema
  through pg_dump must produce identical results. Expect
  questions about whether your DDL change updates pg_dump.
- Likes **separate small commits per feature step**. Monolithic
  pg_dump patches will draw a "split this" reply, mirroring his
  own `pg_get_*_ddl` series style.
- For **TAP / regress** patches, he is the right reviewer.
  Expect attention to failure-output verbosity (his recent
  cluster on 2026-04-01 is all about making TAP failures
  diagnose-able).
- **JSON / jsonpath** patches reach him via the COPY FORMAT JSON
  + jsonpath method-tokens work; he is one of a small number of
  committers who actively ship JSON features.
- Willing to **revert post-merge** — keep your patch small enough
  that a revert is cheap if a buildfarm member breaks.

## Landmark commits (last 12mo)

- **`pg_get_*_ddl` series** (2026-03-19, 4 commits). New
  in-backend DDL emission for role/tablespace/database, with
  shared infrastructure. Followed by 2 follow-up bug fixes
  within ~6 weeks. [verified-by-code]
- **Signal-handler info-passing rework** (2026-04-14 → 2026-05-01).
  Refactor + two consumer commits to surface signal-sender
  PID/UID in server logs. [verified-by-code]
- **`Convert ddlutils regression tests to TAP tests`**
  (2026-04-29). Continued regress→TAP migration; emblematic of
  his test-infra focus. [verified-by-code]
- **Perl-TAP cleanup series** (2026-04-01, 5 commits same day).
  `croak` vs `die`, failure-output surfacing, pg_regress diff
  inclusion in TAP output. [verified-by-code]
- **`Fix heap-buffer-overflow in pglz_decompress() on corrupt
  input`** (2026-04-09). Adjacent to his fuzzing-harness work
  (committed 2026-04-09, reverted 2026-04-10) — shows what
  the fuzzing harness was meant to catch. [verified-by-code]
- **`Add additional jsonpath string methods`** + **`Rename
  jsonpath method arg tokens`** (2026-04-02). Continued
  jsonpath surface expansion. [verified-by-code]
- **`Revert "Enable fast default for domains with non-volatile
  constraints"`** (2026-06-08). Recent revert of his own work
  — illustrates the pattern. [verified-by-code]

## Notes / hedges

- His 24mo footprint is **the most heterogeneous of the five
  personas in this bucket**: pg_dump + jsonpath + TAP infra +
  signal-handler refactor + ddl-emit functions + fuzzing
  harnesses. Despite this, the throughline is "tooling, test
  infra, and tree-wide ergonomics" — he is a maintainer of the
  *developer-and-DBA experience*, not a deep subsystem owner.
- **Bus-factor:** pg_dump and TAP infra both have multiple
  contributors (Tom Lane on pg_dump, Andres on TAP-side
  Cluster.pm, others). Dunstan is a primary contributor but
  not a sole owner. No explicit bus-factor concern flagged in
  domain-ownership.md for pg_dump. [from-domain-ownership]
- The fuzzing harness commit-and-revert (2026-04-09 → -10)
  suggests a still-evolving feature that may reappear in a
  different shape; worth watching if security-fuzzing is a
  topic of interest. [inferred]
- His reviewer cluster (Chao Li, Zsolt Parragi, Jakub Wartak,
  Corey Huinker, Euler Taveira) is mostly **not** the
  storage/optimizer core; these are the tooling/utility
  reviewers. Routing a patch his way taps that community.
  [verified-by-code]
- The `pg_get_*_ddl` family is a new feature surface that may
  later expand to other catalog objects (extensions,
  publications, foreign servers). Watch for follow-up commits
  extending the family. [unverified — no evidence yet, but the
  infrastructure-first commit naming pattern suggests intent]
