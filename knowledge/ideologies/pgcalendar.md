# pgcalendar — ideology / divergence notes

Extension: **h4kbas/pgcalendar** (`master`, control `default_version = '1.0.1'`,
`relocatable = false`, `schema = pgcalendar`, `superuser = false`,
`module_pathname = '$libdir/pgcalendar'`) `[verified-by-code: pgcalendar.control:1-9]`.

pgcalendar is a pure-SQL / PL/pgSQL extension that models recurring events with
"infinite projections." Its domain is four layers: **Events** (logical entities
— meetings, tasks), **Schedules** (non-overlapping time configs that describe a
recurrence), **Exceptions** (per-instance cancel/modify), and **Projections**
(the generated calendar occurrences) `[from-README: README.md:9-12]`. There is
NO C and NO `.so` — the prompt-named `src/pgcalendar.c` returns 404 and the
install script contains zero `LANGUAGE C` routines; every object is a table,
an ENUM, a PL/pgSQL function, a trigger, or a view
`[verified-by-code: pgcalendar.sql:1-401]`. Yet the control file still declares
`module_pathname = '$libdir/pgcalendar'` `[verified-by-code: pgcalendar.control:4]`
— a vestigial/boilerplate field copied from C-extension templates that names a
shared library this extension never ships or loads (exactly the pgmq tell,
`[[pgmq]]`).

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> All `file:line` cites below point into the fetched pgcalendar repo files
> (`pgcalendar.sql`, `pgcalendar.control`, `README.md`, `Makefile`,
> `pgcalendar--uninstall.sql`, `package.json`), NOT into `source/`. Cites
> verified against files fetched 2026-07-15 (see Sources). pgcalendar sits at
> the schema-library / domain-modeling-as-extension end of the extension
> spectrum — the pure-SQL cluster with `[[pgmq]]`, `[[pgque]]`,
> `[[temporal_tables]]`, and `[[index_advisor]]`; it is a *scheduling*-domain
> sibling of `[[pg_cron]]` and `[[pg_partman]]` but, unlike those, adds no
> background worker and no partition automation — it is data model + query-time
> computation only.

## Domain & purpose

The README frames it as an "Infinite Calendar Extension … with recurring
events, multiple schedule configurations, and exception handling"
`[from-README: README.md:1-3]`, `[verified-by-code: pgcalendar.control:2]`. The
data model is a strict hierarchy Event → Schedule(s) → Projection(s), with
Exceptions attached to a Schedule and applied per-date
`[from-README: README.md:255-257]`:

- `events` — logical entity: `name`, `description`, `category`, `priority`,
  `status`, `metadata JSONB`, plus `created_at`/`updated_at`
  `[verified-by-code: pgcalendar.sql:24-34]`.
- `schedules` — a recurrence config bound to an event via
  `event_id … REFERENCES events(event_id) ON DELETE CASCADE`, carrying
  `start_date`/`end_date`, a `recurrence_type` ENUM, and
  `recurrence_interval` / `recurrence_day_of_week` / `recurrence_day_of_month`
  / `recurrence_month` selectors `[verified-by-code: pgcalendar.sql:36-54]`.
- `exceptions` — per-instance overrides keyed
  `UNIQUE(schedule_id, exception_date)`, of `exception_type` `cancelled` or
  `modified`, with optional `modified_date` / `modified_start_time` /
  `modified_end_time` `[verified-by-code: pgcalendar.sql:56-68]`.

There is no `projections` table. Projections are never stored — they are a
return shape of a set-returning function (see divergence 1).

## How it hooks into PG

It barely hooks at all — the whole "extension" is DDL run into a dedicated
schema. Mechanisms it leans on, all first-party SQL-engine features:

- **Schema scoping.** `CREATE SCHEMA IF NOT EXISTS pgcalendar` +
  `SET search_path TO pgcalendar, public`, matching `schema = pgcalendar`
  in the control file `[verified-by-code: pgcalendar.sql:5-8, pgcalendar.control:6]`.
- **Two ENUM types** — `recurrence_type` (`daily`/`weekly`/`monthly`/`yearly`)
  and `exception_type` (`cancelled`/`modified`), each created inside a
  `DO $$ … EXCEPTION WHEN duplicate_object THEN null $$` guard
  `[verified-by-code: pgcalendar.sql:11-21]`. The guard is a tell that this
  file is authored to be run *idempotently as a plain script*, not as a
  once-in-clean-schema `CREATE EXTENSION` install script — reinforced by
  `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and
  `CREATE OR REPLACE FUNCTION` throughout `[verified-by-code: pgcalendar.sql:24,36,56,71-82,85]`.
- **PL/pgSQL functions + BEFORE-row triggers** — an `updated_at` stamper
  (`update_updated_at_column`, BEFORE UPDATE on `events` and `schedules`)
  and an overlap guard (below) `[verified-by-code: pgcalendar.sql:85-132]`.
- **Set-returning PL/pgSQL** (`RETURNS TABLE(...)`) for projection generation,
  consumed via `CROSS JOIN LATERAL` `[verified-by-code: pgcalendar.sql:135-145,284]`.
- **A view** `event_calendar` over the SRF, bounded to CURRENT_DATE ± 6 months
  `[verified-by-code: pgcalendar.sql:376-395]`.
- **`GRANT … TO PUBLIC`** on the schema, all tables, all functions, and the
  view — wide-open, consistent with `superuser = false`
  `[verified-by-code: pgcalendar.sql:398-401, pgcalendar.control:7]`.

No `_PG_init`, no `PG_MODULE_MAGIC`, no hooks, no bgworker, no custom C type,
no `pg_extension_config_dump` marking of the user tables (contrast `[[pgmq]]`,
which registers its metadata for `pg_dump`). Tests live entirely outside PG:
a Node.js/TypeScript Jest harness driving a `pg` client
`[verified-by-code: package.json:6-15,32-34]` — which is why GitHub reports the
repo language as "TypeScript" even though the extension is SQL. No `pg_regress`
or TAP suite ships.

## Where it diverges from core idioms

### 1. "Infinite projections" are computed on-query by an imperative WHILE loop, never materialized — and are not actually infinite

There is no projection storage. `generate_projections(schedule_id, start, end)`
`RETURNS TABLE(projection_date, start_time, end_time, status)` and walks dates
with a hand-rolled `WHILE v_current_date <= LEAST(p_end_date,
v_schedule.end_date::date) LOOP … END LOOP`, `RETURN QUERY`-ing one row per
occurrence `[verified-by-code: pgcalendar.sql:135-205]`. Two things stand out:

- It does **not** use `generate_series` or a recursive CTE — the two idiomatic
  PG ways to expand a recurrence — but an explicit PL/pgSQL loop that advances
  via `get_next_recurrence_date` `[verified-by-code: pgcalendar.sql:167,202]`.
  Set-returning-loop instead of set-generating-SQL is the central procedural
  divergence.
- The loop's upper bound is `LEAST(p_end_date, v_schedule.end_date::date)`, and
  `schedules.end_date` is `TIMESTAMP NOT NULL`
  `[verified-by-code: pgcalendar.sql:41,167]`. So every projection stream is
  finite and doubly bounded — by the caller's requested window AND by a
  mandatory schedule end. The "infinite" branding is marketing: there is no
  unbounded recurrence and no open-ended schedule; the callers
  (`get_event_projections`, `event_calendar`) always pass an explicit
  `[start,end]` window `[verified-by-code: pgcalendar.sql:256-288,376-395]`.
  "Infinite" means "re-derivable for any window on demand," not "stored
  forever." This is the pure-SQL inversion of a materialized calendar table:
  storage-free, but O(days-in-window) PL/pgSQL work per query.

### 2. Exceptions override projections inside the generation loop, per candidate date

For each date the recurrence admits, the loop looks up
`exceptions WHERE schedule_id = … AND exception_date = v_current_date`; on
`NOT FOUND` it emits a normal `'active'` projection, on `cancelled` it emits
nothing (`NULL`), and on `modified` it emits a `'modified'` row with
`COALESCE(v_exception.modified_date, …)` / `modified_start_time` /
`modified_end_time` overriding the computed values
`[verified-by-code: pgcalendar.sql:170-198]`. So the Exception layer is applied
*at projection time* by a correlated single-row lookup, not by pre-computing a
difference set — the `UNIQUE(schedule_id, exception_date)` constraint is what
guarantees the lookup returns at most one row
`[verified-by-code: pgcalendar.sql:67]`.

### 3. Non-overlapping schedules enforced by an application-level BEFORE trigger + EXISTS, not a range exclusion constraint

The idiomatic PG way to forbid overlapping time spans is a `tstzrange` column
with `EXCLUDE USING gist (event_id WITH =, span WITH &&)`. pgcalendar instead
runs a BEFORE INSERT/UPDATE trigger `prevent_schedule_overlap` that does an
`EXISTS (SELECT 1 FROM schedules WHERE event_id = NEW.event_id AND schedule_id
!= COALESCE(NEW.schedule_id,-1) AND (NEW.start_date <= end_date AND
NEW.end_date >= start_date))` and `RAISE EXCEPTION` on a hit
`[verified-by-code: pgcalendar.sql:107-132]`. The same overlap predicate is
duplicated in a standalone `check_schedule_overlap(event_id, start, end)`
function `[verified-by-code: pgcalendar.sql:324-339]` and consulted again in
`transition_event_schedule` before inserting a new schedule
`[verified-by-code: pgcalendar.sql:342-360]`. Two consequences worth flagging:

- **Race window.** Under READ COMMITTED, two concurrent inserts for the same
  `event_id` can each run the `EXISTS` check, each see no conflict, and both
  commit — the trigger provides no locking, unlike a real exclusion constraint
  which is enforced by the index `[inferred]` (the code holds no advisory or
  row lock around the check, `pgcalendar.sql:111-121`).
- **Predicate duplicated in three places**, so a fix to the overlap semantics
  must be made three times `[verified-by-code: pgcalendar.sql:116,335,358]`.

The README nonetheless states overlap is "enforced by triggers" as a design
rule `[from-README: README.md:255]`.

### 4. Timezone-naive throughout — the classic recurrence correctness minefield, unmitigated

Every timestamp column is `TIMESTAMP` (without time zone): `schedules.start_date`
and `end_date` are `TIMESTAMP NOT NULL`, `events.created_at`/`updated_at` and
`exceptions.modified_*` are all plain `TIMESTAMP`, and `exception_date` is `DATE`
`[verified-by-code: pgcalendar.sql:31-32,40-41,59-63]`. There is **no
`timestamptz` anywhere, no `AT TIME ZONE`, no `date_bin`, and no DST handling**.
Projection times are assembled by **text concatenation**:
`(v_current_date || ' ' || v_schedule.start_date::time)::timestamp`
`[verified-by-code: pgcalendar.sql:178-179,190-193]`. Recurrence stepping is
pure `date` arithmetic (`p_date - start_date::date`, `p_current_date + interval`)
`[verified-by-code: pgcalendar.sql:216-226,242-248]`. The posture is therefore
**naive wall-clock**: a "daily 09:00" event silently means 09:00 in whatever the
session/local interpretation is, and DST transitions (a day with 23 or 25 hours,
a skipped 02:00) are neither detected nor corrected `[verified-by-code:
pgcalendar.sql:40-41,178-179]`. This is the textbook footgun for calendar
software; here it is unmitigated and should be called out to any consumer.

### 5. Recurrence math uses crude fixed-length approximations for month/year

`should_generate_projection` gates monthly occurrences on
`EXTRACT(DAY FROM p_date) = recurrence_day_of_month AND (p_date -
start_date::date) >= recurrence_interval * 30`, and yearly on the month/day
matching plus `>= recurrence_interval * 365`
`[verified-by-code: pgcalendar.sql:220-226]`. The 30-day-month and 365-day-year
constants are approximations that ignore variable month lengths and leap years
`[inferred]`. Meanwhile `get_next_recurrence_date` advances monthly/yearly with
true `INTERVAL '1 month'`/`INTERVAL '1 year'` arithmetic — but the function
`RETURNS DATE`, so the `timestamp`-typed interval expression is truncated back
to a date on return `[verified-by-code: pgcalendar.sql:234-248]`. The weekly
branch double-filters: it requires both `EXTRACT(DOW) = recurrence_day_of_week`
AND a `(p_date - start)%(interval*7) = 0` modulo, while the loop already steps
by `interval*7` days — overlapping conditions that can silently drop
occurrences when `start_date`'s DOW differs from `recurrence_day_of_week`
`[verified-by-code: pgcalendar.sql:217-219,243-244]` `[inferred]`.

### 6. Packaging is broken for `CREATE EXTENSION` as shipped; the versioned script is generated, not committed

The control file sets `default_version = '1.0.1'`
`[verified-by-code: pgcalendar.control:3]`, but the repo does **not** contain
`pgcalendar--1.0.1.sql` (HTTP 404, see Sources) — the file
`CREATE EXTENSION pgcalendar` requires. The control file even carries a comment
admitting it: "For CREATE EXTENSION, PostgreSQL requires versioned files
(pgcalendar--1.0.1.sql) … For manual installation, use pgcalendar.sql directly"
`[verified-by-code: pgcalendar.control:8-9]`. The rename is deferred to install
time: README Method 3 copies `pgcalendar.sql` →
`…/extension/pgcalendar--1.0.1.sql` by hand, and the Makefile `build` target
produces the versioned name only inside the PGXN tarball
(`cp $(EXTENSION).sql dist/…/$(EXTENSION)--$(VERSION).sql`)
`[verified-by-code: README.md:47-49, Makefile:82]`. So the extension is
distributed as a raw script that works via `psql -f` or the PGXN tarball, but a
bare `git clone … && make install && CREATE EXTENSION` does not have the file it
needs. Version metadata also drifts: the script header says
`-- Version: 1.0.0`, the control and Makefile say `1.0.1`, and `package.json`
says `1.0.1` `[verified-by-code: pgcalendar.sql:2, pgcalendar.control:3,
Makefile:6, package.json:3]`.

## Notable design decisions

- **RECORD-typed helper signatures.** `should_generate_projection(p_schedule
  RECORD, p_date DATE)` and `get_next_recurrence_date(p_schedule RECORD,
  p_current_date DATE)` take the whole schedule row as an untyped `RECORD`; the
  uninstall script drops them by `(RECORD, DATE)` signature
  `[verified-by-code: pgcalendar.sql:208-211,234-237, pgcalendar--uninstall.sql:12-13]`.
- **Composition via LATERAL SRF.** `get_event_projections` /
  `get_events_detailed` / the `event_calendar` view all shape output by
  `JOIN schedules … CROSS JOIN LATERAL generate_projections(s.schedule_id, …)`
  `[verified-by-code: pgcalendar.sql:282-286,316-319,386-392]` — the SRF is the
  single source of projection truth, wrapped for three call shapes.
- **The `event_calendar` view double-bounds the same window.** It passes
  `CURRENT_DATE ± 6 months` into `generate_projections` and then re-filters the
  identical range in a `WHERE` — redundant, since the SRF already clamps to its
  arguments `[verified-by-code: pgcalendar.sql:388-394]`.
- **Payload extensibility via `metadata JSONB DEFAULT '{}'`** on all three
  tables `[verified-by-code: pgcalendar.sql:33,49,66]` — schemaless escape
  hatch, though no function reads it.
- **CHECK constraints validate recurrence selectors** (`interval > 0`,
  day-of-week 0–6, day-of-month 1–31, month 1–12) at the table level
  `[verified-by-code: pgcalendar.sql:50-53]` — the one place enforcement is
  declarative rather than procedural.
- **`transition_event_schedule` is the "safe reconfigure" entry point** — it
  checks overlap then `INSERT … RETURNING schedule_id`
  `[verified-by-code: pgcalendar.sql:342-373]`; it does the overlap check in
  application code (divergence 3) rather than letting a constraint reject the
  insert.
- **Every projection carries a text `status`** (`'active'` / `'modified'`;
  cancelled rows are simply absent) `[verified-by-code: pgcalendar.sql:181,196]`
  — the exception state is surfaced as a computed string column, not a stored
  flag.

## Links into corpus

- `[[pgmq]]` — the canonical pure-SQL, no-`.so`, vestigial-`module_pathname`
  sibling; pgcalendar shares the ideology (schema + tables + PL/pgSQL functions)
  but is thinner — no dynamic DDL, no `SKIP LOCKED`, no `pg_extension_config_dump`.
- `[[pgque]]` — the other minimal pure-SQL queue-style sibling in the cluster.
- `[[temporal_tables]]` — time-domain sibling: both reconstruct a temporal
  feature core lacks, but temporal_tables uses a C trigger + range types +
  typcache, whereas pgcalendar stays entirely in PL/pgSQL and avoids range
  types even where they fit (overlap enforcement, divergence 3).
- `[[index_advisor]]` — schema-library-as-extension sibling (advice via SQL
  functions, no engine hook).
- `[[pg_cron]]` — scheduling-domain neighbor, but pg_cron IS a bgworker running
  jobs; pgcalendar only *models* schedules and never executes anything.
- `[[pg_partman]]` — time-partitioning neighbor; pgcalendar's recurrence
  expansion is the manual PL/pgSQL analogue of what partman automates, minus the
  background maintenance.

## Sources

Fetched 2026-07-15 (branch `master`, via `raw.githubusercontent.com`):

- `https://raw.githubusercontent.com/h4kbas/pgcalendar/master/pgcalendar.sql`
  @ 2026-07-15 → HTTP 200 (401 lines; the load-bearing install script — tables,
  ENUMs, triggers, projection SRF + helpers, view, grants; deep-read).
- `https://raw.githubusercontent.com/h4kbas/pgcalendar/master/pgcalendar.control`
  @ 2026-07-15 → HTTP 200 (9 lines; deep-read — vestigial `module_pathname`,
  the missing-versioned-file admission at lines 8-9).
- `https://raw.githubusercontent.com/h4kbas/pgcalendar/master/README.md`
  @ 2026-07-15 → HTTP 200 (354 lines; domain model, install methods, usage,
  the "enforced by triggers" rule).
- `https://raw.githubusercontent.com/h4kbas/pgcalendar/master/Makefile`
  @ 2026-07-15 → HTTP 200 (120 lines; PGXN-tarball build that generates the
  versioned SQL name, Node/Jest test wiring — no PGXS `include`).
- `https://raw.githubusercontent.com/h4kbas/pgcalendar/master/pgcalendar--uninstall.sql`
  @ 2026-07-15 → HTTP 200 (33 lines; drop order + RECORD-typed function
  signatures).
- `https://raw.githubusercontent.com/h4kbas/pgcalendar/master/package.json`
  @ 2026-07-15 → HTTP 200 (35 lines; TypeScript/Jest external test harness —
  explains GitHub's "TypeScript" language tag).
- `https://raw.githubusercontent.com/h4kbas/pgcalendar/master/pgcalendar--1.0.1.sql`
  @ 2026-07-15 → HTTP 404 — the versioned install script `CREATE EXTENSION`
  needs is NOT committed (divergence 6); it is generated at package/install time.

Not fetched (out of scope / unprobed): `META.json`, `LICENSE`, the `tests/`
TypeScript sources, and any `src/` C file — the prompt-named `src/pgcalendar.c`
is confirmed absent (this is a pure-SQL extension). All behavioral cites are
`[verified-by-code]` against the fetched `pgcalendar.sql` unless tagged
`[from-README]` (end-user framing) or `[inferred]` (race window in divergence 3,
the month/year approximation and weekly double-filter consequences in
divergence 5).
