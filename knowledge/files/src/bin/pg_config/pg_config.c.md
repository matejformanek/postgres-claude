# `src/bin/pg_config/pg_config.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~188
- **Source:** `source/src/bin/pg_config/pg_config.c`

The "where is PostgreSQL installed" oracle. A C rewrite of an older shell
script (Peter Eisentraut → Andrew Dunstan), the rewrite was needed so that
the binary could report the *runtime* install layout even if the cluster
was relocated from its `./configure --prefix=…` location. The real work
lives in `common/config_info.c` (`get_configdata`). [verified-by-code]
[from-comment]

## API / entry points

- `main` — checks `--help`, runs `find_my_exec` to locate the binary,
  calls `get_configdata(my_exec_path, &len)` which returns an array of
  `{name, setting}` pairs, then either prints them all (no args) or matches
  command-line switches against the static `info_items[]` table.
  [verified-by-code]
- `info_items[]` — a `{switchname, configname}` table mapping
  `--bindir → BINDIR`, `--pgxs → PGXS`, etc. Must stay in sync with the
  `help()` text and with what `get_configdata` returns. [verified-by-code]
- `show_item(configname, configdata, len)` — linear scan over configdata,
  prints matching `setting`. [verified-by-code]

## Notable invariants / details

- All path values come from `get_configdata`, which derives them from the
  binary's runtime location plus the compile-time install-layout constants.
  So `pg_config --bindir` returns the directory the binary actually lives
  in, not the original `--prefix`. [from-comment]
- Compiler flags (`CC`, `CFLAGS`, `LDFLAGS`, …) are baked in at compile
  time and reflect the build, not the relocated install. [inferred]
- No options at all → dump everything in `KEY = VALUE` form. With options,
  print just `VALUE\n` per option, one line per option. [verified-by-code]
- Unrecognized switch → exit 1 with an "invalid argument" message and a
  pointer to `--help`. [verified-by-code]
- Help is special-cased (line 142-149) so that `--help` ahead of any other
  args wins and bypasses `find_my_exec`. [verified-by-code]

## Potential issues

- `pg_config.c:42-66` — `info_items[]` is duplicated logically with both
  `help()` and `get_configdata`. Adding a new config item requires touching
  three places. [ISSUE-doc-drift: triple-source for config keys (nit)]
- `pg_config.c:159-164` — when called with zero args, prints all items in
  `get_configdata` order, but the for loop at 167 iterates over `argv`
  and inner-loops over `info_items`. So passing `pg_config --bindir
  --bindir` will print BINDIR twice; harmless but undocumented.
  [verified-by-code]
- `pg_config.c:178` — uses `info_items[j].switchname == NULL` to detect
  end-of-table, but `j` is the local loop counter on the just-completed
  iteration. Works correctly because `j` retains its value after the
  `for` exits. [verified-by-code]
