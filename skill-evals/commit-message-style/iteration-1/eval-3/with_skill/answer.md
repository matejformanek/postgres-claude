**`Backpatch-through:` value.** Name the **oldest** branch that
receives the fix, as a bare major-version number. Backpatching to 16,
17, and 18 means:

```
Backpatch-through: 16
```

Not "16-18", not "from master", not "16, 17, 18" — just `16`. The line
goes **last** in the trailer block.

**Does the message differ between branches?** No. The commit message
must be **identical** across master and all back branches, so the
release-note tooling can match the cherry-picked copies as one logical
fix. Only the diff itself varies (resolved conflicts). The
`Backpatch-through: 16` line appears verbatim on all four copies
(master, 18, 17, 16).

**Trailer block for your scenario.** With Jane as author, you as the
diagnoser, and two reviewers, the typical order is:

```
<imperative subject under ~64 chars>

<paragraphs explaining why and what, wrapped near 72-76 cols>

Author: Jane Doe <jane@example.com>
Reported-by: <if applicable>
Diagnosed-by: <Your Name> <you@example.com>
Reviewed-by: <Reviewer 1> <r1@example.com>
Reviewed-by: <Reviewer 2> <r2@example.com>
Discussion: https://postgr.es/m/<message-id>
Backpatch-through: 16
```

`Diagnosed-by:` is a real PG trailer for someone who root-caused the
bug without writing the patch. One tag per line, repeated per person
— don't comma-separate reviewers.
