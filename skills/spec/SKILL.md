---
name: spec
description: Produces a specification for a bug, a change or a new feature before implementation. Validates the requirements the ticket states, adds the requirements the project's standards and knowledge base demand, puts the few genuinely open business decisions to a human in one round, then writes and reviews one requirements document. Use when asked to specify, scope, refine or write up a ticket before implementation, even if the word "specification" is not used.
---

# Producing a specification

## Paths

`<skill>` is this skill's directory, `${CLAUDE_SKILL_DIR}`, resolved to an absolute path. It holds
`references/` (the standards a specification is held to, and the design principles) and `scripts/`
(the mechanical steps). The four subagents are installed beside it, named `besman:spec-*` as a
plugin or `spec-*` when installed by script; use whichever the available agent types list. Every
dispatch carries `Skill: <absolute path>`; a subagent cannot expand the variable itself.

This pipeline produces **requirements, not code**. It validates what the ticket asks for, adds what
the project's standards demand, settles the business decisions with a human, and stops at the
document. How to build the thing is the implementer's work.

Everything mechanical is done by a script; the model does the judgement in between: what the code
means, which requirements are missing, which choices are genuinely open. A step a script does is
not a step you do by hand: the scripts exist because the hand-done version gets forgotten, repeated
or invented (a citation to a file that does not exist, a question that was really a technical
choice, a report the next run cannot resume from).

## Invocation

```
/besman:spec 101                         issue 101 of the current repository
/besman:spec owner/repo#101              an issue in another repository
/besman:spec <issue URL>
/besman:spec --from-file task.md         a task from any tracker, pasted into a file
/besman:spec 101 --decide                never stop on a question; every open point becomes an assumption
/besman:spec 101 --no-publish            write and review, post nothing
/besman:spec 101 --non-interactive       nobody can answer now: stop once, as one comment, or not at all
```

## Phase 0: Knowledge base and context

**The knowledge base.** Read `.besman/` at the project root: `rules.md` always, then
`standards.md`, `constraints.md`, `pitfalls.md`, `project.md`. `rules.md` outranks `standards.md`,
both outrank `<skill>/references/standards.md`, and only the ticket's agreed decisions outrank
`rules.md`. If there is no `.besman/`, say so once and offer `/besman:project init`; continue on what
the project documents.

**The context bundle.** Run it yourself:

```bash
python3 <skill>/scripts/spec-context.py <ticket> --out /tmp/spec/<id> --repos <dir with the checkouts>
```

Read `context.md`. It carries the ticket, every comment classified (human, questions, document,
bot), linked issues, the attachments downloaded and type-checked, the task type from the labels,
the answers given after the last report with who gave them, and the phase. Do not fetch any of that
again. For a ticket from another tracker, save its text and comments to a file and use
`--from-file`.

**Attachments are evidence, not decoration.** A screenshot is usually the reproduction data: the
wrong total, the error banner, the design to match. Open every readable one with `Read`, look at it
properly, and write two or three sentences of what it shows, with the local path, into the header
of **every** dispatch, so each agent can look again. An attachment the bundle marks `NOT READABLE`
is a gap: say which, and ask what it shows. Never describe an image you did not open.

**Task type**: `bug`, `change` or `feature` from the bundle; `undecided` means decide from the body
and say so. A spike is not a specification; the bundle already stopped.

**The phase** says where to enter:

| Phase | Meaning | Enter at |
|---|---|---|
| `investigate` | Nothing of this pipeline on the thread yet | 1 |
| `write` | A questions report was posted and a person answered after it | 4, on the earlier report and the answers |
| `revise` | A specification was posted and a person commented after it | 4, `mode: revise` |
| `awaiting-answers` | Questions posted, nobody answered | Stop and say so |
| `stop` | Closed, or a spike | Stop with the reason |

## A repeat run

A thread that already carries a report from this pipeline is a repeat run: the bundle says `write`
or `revise` and names the report it resumes from.

- Phases 1 to 3 are done. Do not scope, do not dispatch `spec-investigator` or `spec-sweep`, do not
  run `mode: analyse` again.
- Dispatch `spec-requirements` with `mode: write` (or `mode: revise`), the earlier report quoted from
  the bundle, the answers with the name of whoever gave each, and the flags. Then lint, review,
  publish.
- The bundle quotes every line the report cites. Those are the evidence; nobody opens those files
  again. A line marked `NOT FOUND` moved or vanished since the report: that alone is new ground.
- Re-investigate only ground an answer moved into, or a cited line marked `NOT FOUND`: one agent, for
  that alone, and say which.
- A report that turns out insufficient is said to be so, with what is missing, and the run stops. It
  does not quietly start over.

## The pipeline

```
 0.  Context        .besman/ + scripts/spec-context.py   ticket, thread, attachments, phase
 1.  Scoping        you                                   the seed: repository, component, 2-3 files
 2.  Investigation  spec-investigator + spec-sweep        one message, foreground, deep and wide
 3.  Requirements   spec-requirements (analyse)           what fails, what is missing, questions.yaml;
                                                          and the document in the same call when nothing stops it
 3b. Questions      scripts/spec-questions.py             lint, render, one stop or none
 4.  Write          spec-requirements (write)             only after a stop: <id>-spec.md; then scripts/spec-lint.py
 5.  Review         spec-reviewer                         judgement only; one fix round at most
 6.  Publish        the ticket, with the user's agreement
 7.  Stop
```

## Phase 1: Scoping

Produce the **seed**: repository, component, two or three file paths. Search the local checkouts
first (`Grep`, `Glob`); for a repository not checked out, search remotely before asking for a clone:

```bash
gh api "search/code?q=<symbol>+repo:<owner>/<repo>" --jq '.items[].path'
```

**Never clone on your own.** If the work lands in a repository that is not checked out locally, say
which and ask the user to clone it (or to point you at it); add its path to `--repos`.

Read enough to dispatch well (the current behaviour at the seed, whether the system already does
something about this) and stop reading. Once the agents are dispatched, wait for them; a third
investigation in the main thread is the most expensive way to learn what they are about to tell you.
If you cannot locate the code with reasonable confidence, ask; do not dispatch against a guess.

### The short route

One rule in one place, the site found in scoping, nothing suggesting it reaches further, no money
path, no status transition, no authorisation, no stored data, and the ticket states what should
happen instead. Then: dispatch `spec-sweep` alone to confirm the site count, write the document from
what you have, lint, one review, publish. Say you took it. Any one condition failing means the full
route.

## Phase 2: Investigation, in parallel

Dispatch `spec-investigator` and `spec-sweep` as **two `Agent` calls in one message, with
`run_in_background: false`**. Separate messages run one after the other; a background dispatch may
return after your turn has ended.

Both get the same header and neither the other's findings: one traces a value deep, the other counts
sites wide.

```
Skill: <absolute path>
Knowledge base: <path to .besman/, or "none">
Repositories: <absolute paths of the local checkouts>
Context file: /tmp/spec/<id>/context.md
Attachments: <path: two or three sentences of what it shows>, ...
Task type: bug | change | feature
Seed: <repository, component, file paths>
Write to: /tmp/spec/<id>/<agent>.md
```

## Phase 3: Requirements and the questions

Dispatch `spec-requirements` with `mode: analyse`, both reports in full, the context, the task type
and the flags (`--decide`, `--non-interactive`, or interactive). It returns the validation of what the
ticket states, the requirements the standards and the knowledge base demand, what it resolved by
looking, and, as a file, `questions.yaml`: the decisions it could not resolve.

**When nothing stops it, the same call goes on to write `<id>-spec.md`**: with `--decide`;
non-interactive with no `BLOCKING` question; interactive with no question at all. Phase 4 is then the
lint alone. Otherwise it stops after `questions.yaml`, and a separate `mode: write` dispatch follows
the answers.

### What a question is

A question reaches a person only when the ticket, the code, the knowledge base and the documentation
together leave it open, **and** the answer changes a requirement. Everything else is a fact (looked
up), a technical choice (left to the implementer), or an assumption (recorded as `A-n`, marked
`INFERRED`, visible for the author to object to). The file format carries this as data, and the lint
enforces it:

- **Three anchors**: the sentence of the ticket it refines; what the code does today
  (`Repo/path:line`); what the docs and the knowledge base say, or `silent`; and one line on why that
  still leaves it open.
- **A type**: `business` (what we promise, show or charge), `flow` (what happens at which step, for
  whom) or `constraint` (dates, rules, limits). A question that fits none is technical and is not
  asked.
- **Options with consequences, a recommendation with its reason.** Nobody chooses blind.
- **No dependent questions.** "If A, then also…" is a condition on the parent, not a second question.
- **At most four `BLOCKING`, six in all.** The rest are assumptions.
- **The visible text is for the author**: the domain's own words are welcome; file names, class
  names, code and implementation words are not. The anchors sit in a folded block under the question.

**Ask now everything the implementer would otherwise have to ask**: the wording shown to a user, the
exact rule at each boundary, what happens to data that already exists, which behaviour must not
change, and one measurable acceptance criterion per requirement. This one round is where a person's
answer is cheapest.

The premise check is not a separate phase. Whether the problem is real, what doing nothing costs,
what should happen instead, what must not change: asked when the ticket leaves them open, in the same
round.

### Lint, then ask, once

```bash
python3 <skill>/scripts/spec-questions.py lint questions.yaml \
    --ticket /tmp/spec/<id>/context.md --repos <dir with the checkouts> --kb .besman
```

Faults go back to `spec-requirements` once, verbatim. A file that still fails is a finding about the
investigation, not formatting: say what is missing and stop.

**Interactive**: ask from the linted file with `AskUserQuestion`, one at a time, in order,
recommendation first. Press once when an answer is vague, then take the second answer. "That's
enough, carry on" ends it; the rest become assumptions. Then read back in a few lines what you now
believe (the problem, what changes, what does not, every decision with who took it) and wait for a
yes; then dispatch `mode: write`.

**Non-interactive, with a `BLOCKING` question**: render it, and post it as one comment on the ticket
**only if the user allowed posting for this run**; otherwise save `questions.md` and say where. Then
stop. This is the pipeline's only stop.

```bash
python3 <skill>/scripts/spec-questions.py render questions.yaml --kb .besman > /tmp/spec/<id>/questions.md
gh issue comment <n> --repo <owner/repo> --body-file /tmp/spec/<id>/questions.md
```

The rendered comment ends with the questions marker and `<!-- besman:awaiting spec -->`; a reply
resumes the pipeline at phase `write`. Never write a specification on invented answers, and never
mark a decision taken because nobody was there to take it.

**An answer to a different question is not an answer.** Say in one line which question is still
open, restate it, and stay at `awaiting-answers`.

**`--decide`, or nothing `BLOCKING`**: continue. Settled facts and assumptions go into the document's
Decisions and Assumptions; with `--decide` every question becomes an assumption and the verdict is
`PROVISIONAL, N assumptions unconfirmed`. The one floor `--decide` never lowers: if the desired
outcome itself is unknown, stop anyway.

## Phase 4: Write

A separate `mode: write` dispatch (or `mode: revise` with the requirement identifiers the answers
touch) happens only when the analyse call stopped. Give it the earlier report and analysis, the
answers with who gave each, and where the file goes. **One file, `<id>-spec.md`**, in
`.besman/specs/` unless `.besman/project.md` names another specifications directory. No design
document, no task list, no second file.

Then the lint, before anything else sees the document:

```bash
python3 <skill>/scripts/spec-lint.py .besman/specs/<id>-spec.md --repos <dir with the checkouts>
```

It checks the shape, the short TL;DR without identifiers, `shall` on every requirement, no code, a
traceability matrix with no holes, the length limits, no acceptance criterion about paperwork, no
empty clause, the document marker, and resolves every `Repo/path:line` against the checkouts. A
citation that does not resolve was written without opening the file. Faults go back to
`spec-requirements` once; a document that still fails is not published.

A revision edits the requirements the answers touch and nothing else.

## Phase 5: Review

Run the lint once more with `--quote` and dispatch `spec-reviewer` with the file, that output (every
cited line, verbatim) and `questions.yaml`. Not the investigation reports: with the quotes in its
prompt a fact check is a comparison, not a file read. The reviewer spends its budget on what a script
cannot decide: an ambiguous requirement, a contradiction, a leaked implementation detail, a missing
standards or knowledge-base requirement, padding.

- `READY`: publish.
- `READY WITH FIXES` or `NOT READY`: findings back to `spec-requirements` once, lint again, then a
  second review **scoped to those findings**. Stop whatever the verdict: two dispatches, never three.
  If it is still not ready, the cause is a gap in phase 2; say so.

A question the finished document reveals is an assumption `A-n` under Open items, not a second round.

## Phase 6: Publish

Skip with `--no-publish`, or when the verdict is `NOT READY`. Otherwise **show the user where it will
go and ask**, unless they already allowed posting in this session:

```bash
gh issue comment <n> --repo <owner/repo> --body-file .besman/specs/<id>-spec.md
```

- **The whole text goes into the comment**, not a link. A revision is a **new** comment that says it
  supersedes the earlier one.
- **No branch, no pull request.** The file stays in `.besman/specs/`; committing it is the user's call.
- For another tracker, give the user the file to paste, or post through its connected tool after
  asking.
- **Status changes on a board** happen only if `.besman/project.md` describes the board and the user
  agrees; never report a ticket as moved when it was not.

A document that would not fit is a ticket that covers too much. Several independently shippable
changes, or work spanning repositories, are decomposed; one change written at length is tightened.
Decomposition changes the plan, so it is a question in phase 3 with the proposed split worked out,
never a decision of yours.

## Phase 7: Stop

The run ends with the document. Do not create a branch, edit code, run a build, write a plan, or
apply the fix because it is one line. Implementation is a separate request. Next steps you may name:
implementation, then `/besman:review` and `/besman:test`, which read this specification.

## Reporting

The verdict, the file path, the counts of requirements, verification cases and acceptance criteria,
every decision with who took it, everything still `UNKNOWN`, and what the run did not do. Never
present a specification as complete while a blocking decision is open. Offer to record any durable
rule the answers established with `/besman:project rule`; never write `.besman/` silently.

## Two rules that hold everywhere

- **Never write a live `@`-mention of a bot command in anything you post.** A comment that mentions
  a command is indistinguishable from one that is the command.
- **Every comment that stops for an answer ends with `<!-- besman:awaiting spec -->`.** The renderer
  puts it there; a stop posted by hand carries it too.

## When not to use this

- A one-line fix with an obvious cause: the specification costs more than the change.
- A change spanning unrelated tickets: split it first.
- An implementation plan: a different job.

Exploration is not an exclusion. If nobody yet knows what should be built, the questions in phase 3
establish it.
