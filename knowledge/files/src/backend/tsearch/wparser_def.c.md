# `src/backend/tsearch/wparser_def.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~2840
- **Source:** `source/src/backend/tsearch/wparser_def.c`

The default "fancier than you'd expect" text-search parser. Recognizes
26 token types: `asciiword`, `word`, `numword`, `email`, `url`,
`url_path`, `host`, `protocol`, `numhword`, `asciihword`, `hword`,
`hword_numpart`, `hword_part`, `hword_asciipart`, `blank`, `tag`,
`entity`, `version`, `int`, `uint`, `float`, `xml`, `nl`, `file`,
`path`, `space`. Implemented as a hand-written state-machine over
multibyte input — large because each token type has its own
recognition logic and they can chain (e.g. `john@example.com/path`
splits into email + URL parts).

Hyphenated words (`hword*`) are unique: the parser emits both the
whole compound and its parts so the dictionary chain can choose.

Exports: `prsd_start`, `prsd_nexttoken`, `prsd_end`, `prsd_lextype`
(registered as `pg_ts_parser` row "default"). [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
