# `src/bin/scripts/dropdb.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~189
- **Source:** `source/src/bin/scripts/dropdb.c`

CLI wrapper that issues `DROP DATABASE [IF EXISTS] <name> [WITH
(FORCE)]` against a maintenance database. Optionally prompts via
`yesno_prompt` in `-i/--interactive` mode. [verified-by-code]

## API / entry points

- `main(argc, argv)` — parses options, runs interactive prompt,
  picks maintenance db (`template1` if dropping `postgres`),
  builds and sends the SQL. [verified-by-code]

## Notable invariants / details

- The DROP command is built via
  `appendPQExpBuffer("DROP DATABASE %s%s%s;", IF_EXISTS,
  fmtIdEnc(dbname, enc), force ? " WITH (FORCE)" : "")` (line
  146-149). `fmtIdEnc` is the encoding-aware identifier quoter
  added in PG16 to handle multi-byte safety.
  [verified-by-code]
- Auto-fallback to `template1` when target is `postgres` (line
  133-134): same idea as createdb.c — can't drop the db you're
  connected to. [verified-by-code]
- `--force` translates to `WITH (FORCE)` (PG13+), which
  terminates active connections before dropping. [verified-by-code]
- Interactive prompt shows "Database \"%s\" will be permanently
  removed. Are you sure?" (line 127-129) and exits 0 (not error)
  on "no" — clean cancel. [verified-by-code]
- `--if-exists` uses the long-only convention (no short form);
  parsed via `static int if_exists` with the getopt_long
  `&if_exists, 1` form (line 36). [verified-by-code]

## Potential issues

- The dbname comes from a required positional arg (line 109-122)
  — no `--dbname=` option. Slightly inconsistent with
  createdb/dropuser which accept both. [verified-by-code]
- No protection against the user typing `postgres` and the auto
  redirect to template1: dropping `postgres` is technically
  allowed but breaks many tools' defaults. Just emits a normal
  error if the server refuses. [verified-by-code]
- Line 88: `getopt_long` accepts `-U USER` for `--username`. The
  connection user (`-U`) is independent of the target db, but
  the help text doesn't make this clear: "user name to connect
  as". [verified-by-code]
- `--force` does NOT prompt even in `-i` mode — combining the
  two simply drops connections AND prompts once. Documented
  behaviour. [verified-by-code]
- The hint "missing required argument database name" on line 112
  doesn't quote the message string with a translator-noop
  comment; matches the style of other scripts.
  [verified-by-code]
