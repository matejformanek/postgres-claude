No — do **not** add `Co-Authored-By: Claude <noreply@anthropic.com>` to
a commit intended for upstream PostgreSQL. Two distinct reasons:

1. **Casing and convention.** PostgreSQL uses the lowercase form
   `Co-authored-by:` (lowercase `a` and `b`), not GitHub's
   `Co-Authored-By:`. The uppercase form is a GitHub / Claude Code
   convention and does not appear in PG history.

2. **Attribution semantics.** PG attribution trailers credit *humans*
   who substantively wrote or shaped the patch. The community does not
   credit AI tooling as a co-author. There is no precedent for it in
   `git log`, and adding it would be flagged in review.

The right way to credit contributors on a PG commit is the trailer
block:

```
Author: First Last <email@example.com>
Co-authored-by: Second Author <email@example.com>   (only if a real
                                                     second human author)
Reported-by: ...
Reviewed-by: ...
Discussion: https://postgr.es/m/<message-id>
Backpatch-through: <branch>    (only if backpatching)
```

When the first author is also the committer, **omit `Author:` entirely**
— additional authors then still go on `Co-authored-by:`. Names and
emails are cut-and-pasted verbatim from the From: header of the
contributor's mailing-list message; don't normalize them. There is no
`Signed-off-by:` in PG — it is not a DCO project.
