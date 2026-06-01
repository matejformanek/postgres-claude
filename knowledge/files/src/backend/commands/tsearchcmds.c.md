# tsearchcmds.c

- **Source path:** `source/src/backend/commands/tsearchcmds.c`
- **Lines:** 1870
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines for tsearch manipulation commands." [from-comment, tsearchcmds.c:3-5] DDL for the four tsearch object types: **text search parsers** (tokenisers), **templates** (define dictionary class), **dictionaries** (instantiated templates with options like stopwords), and **configurations** (parser + per-token-type dictionary chain).

## Public surface

- `DefineTSParser`, `AlterTSParser`, `RemoveTSParserById`, `RenameTSParser` — pg_ts_parser.
- `DefineTSTemplate`, `AlterTSTemplate` (limited), `RemoveTSTemplateById`, `RenameTSTemplate` — pg_ts_template.
- `DefineTSDictionary`, `AlterTSDictionary`, `RemoveTSDictionaryById`, `RenameTSDictionary` — pg_ts_dict. ALTER lets you change OPTIONS (e.g. swap stopword files).
- `DefineTSConfiguration`, `AlterTSConfiguration`, `RemoveTSConfigurationById`, `RenameTSConfiguration` — pg_ts_config. ALTER ADD/ALTER/DROP MAPPING modifies pg_ts_config_map.

## Mapping model

A configuration says: "for token type X (e.g. asciiword, hword, numword), apply dictionary chain D1, D2, …". The chain stops at the first dictionary that returns a non-NULL lexeme list. This file is the DDL surface for that mapping table.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`
