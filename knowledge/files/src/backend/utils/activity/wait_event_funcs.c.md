# `src/backend/utils/activity/wait_event_funcs.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~90
- **Source:** `source/src/backend/utils/activity/wait_event_funcs.c`

SQL-level access to the wait-event registry: `pg_wait_events` view.
Returns one row per known wait event with `type`, `name`, `description`.
The body table is generated at build time from `wait_event_names.txt`
via `generate-wait_event_types.pl` into `wait_event_funcs_data.c` which
this file `#include`s inline.

Custom (extension) wait events under the `Extension` class are
appended dynamically at the end of the iteration. [from-comment]
