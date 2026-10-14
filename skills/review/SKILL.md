---
name: review
description: Reviews a finished implementation against the ticket it came from by dispatching four independent review lenses in parallel (code quality, security, implementation vs the ticket, project standards), running the project's linters, tests and SAST scanner, then deduplicating and ranking the findings into a single verdict and optionally publishing one review to the pull request. Use when asked to review a branch, a pull request or a completed change before it is merged.
---

# Reviewing a finished implementation

## Paths

`<skill>` below is this skill's directory, `${CLAUDE_SKILL_DIR}`, resolved to an absolute path.
It holds `references/` and `scripts/`. The four lenses are subagents installed next to it
(`.claude/agents/review-*.md`, or the plugin's `agents/`). Every lens you dispatch gets one line,
`Skill: <absolute path>`, and reads the shared reference from there; a subagent cannot expand the
variable itself.

## Invocation

`/besman:review` as a plugin; `/review` when installed by script or when no other command has that name.

```
/review                                   the current branch of the repo you are in
/review <path-to-repo>                    name the repository explicitly
/review <ticket>                          find the branch or pull request for this ticket
/review --pr <n> [--repo <owner/repo>]    an open pull request
/review --base <ref>                      compare against <ref> instead of the default branch
/review --since <sha>                     review only the commits after <sha>
/review --no-publish                      do not offer to post the review to GitHub
```

With no argument, review the current branch of the repository you are standing in. If you are not
inside a git repository, ask which one.

This skill reviews work that is **finished**. It is not a design review and not a specification
review; those run before any code exists.

## Non-interactive mode

`--non-interactive` (or running in CI with no human to ask) changes two things and nothing else:

| Step | Interactive | Non-interactive |
|---|---|---|
| Gate: missing information | Ask the user | Report every `BLOCKING` gap in the review body and mark the affected findings unverified. Do not invent the missing fact |
| Phase 5, publish | Show the body and ask | Post without asking, because the run was explicitly requested |

**Do not downgrade a verdict because a check could not be run.** Report the check as not run and
let the reader decide. Never guess at a ticket you could not fetch. Never report a lint or SAST
result you did not measure: "no security issues found" after the scanner failed to start turns an
absence of evidence into a false clearance.

**Never print a secret.** Test whether a token is set with `[ -n "$TOKEN" ]` or print its length,
never `echo` its value: CI transcripts and logs are kept.

## The pipeline

Four lenses, five phases. Phase 2 is parallel: four lenses over one diff, independent by design.
Phase 3 is yours, because it runs commands and reads exit codes, and a subagent's summary of a
command it ran is not evidence.

The shared rules the lenses work from (evidence, plain wording, severity, machine checks) live in
**`<skill>/references/review.md`**. Each lens reads only the sections its own instructions name.

```
 1. Scoping         you, inline: repo, base, diff, ticket, spec, project rules,
                    plus the mechanical checks (branch, title, size)
        │
        ▼  seed: repo + base..HEAD + changed files + ticket text
 2. Review          review-best-practices  ─┐
                    review-security        ─┤
                    review-implementation  ─┼─ parallel subagents, one message
                    review-standards       ─┘
        │
        │  (phase 3 runs alongside: start it before you dispatch, read it after)
        ▼
 3. Machine checks  YOU, inline: the project's type check, lint, format, tests, SAST
        │
        ▼
 Gate: missing information, BLOCKING gaps go to the user
        │
        ▼
 4. Synthesis       YOU: deduplicate, rank, gate, one verdict
        │
        ▼
 5. Publish         ask first, unless standing authorisation this session
```

## Phase 1: Scoping

**Do this yourself.** A reviewer pointed at the wrong base commit reviews the whole release and
reports a hundred findings that belong to somebody else's merged work.

### 1.1 Identify the repository and the base

```bash
git -C <repo> rev-parse --abbrev-ref HEAD
git -C <repo> fetch origin --quiet
git -C <repo> symbolic-ref --short refs/remotes/origin/HEAD     # the default branch, e.g. origin/main
git -C <repo> merge-base origin/<default> HEAD
```

The base is, in order of precedence: `--base`; the pull request's base branch
(`gh pr view <n> --json baseRefName`); the branching rules the project documents (a hotfix branch
cut from the production branch is compared against it, not against the integration branch); the
repository's default branch.

**Use the merge base, not the branch tip.** `git diff origin/main HEAD` includes, inverted,
everything that landed on `main` since the branch was cut. `git diff <merge-base> HEAD`, or
`git diff origin/main...HEAD` with three dots, does not.

**Prove the base resolves and the diff is non-empty before going further.**

```bash
git -C <repo> rev-parse --verify "$BASE^{commit}"   # non-zero on a bad ref
git -C <repo> diff --quiet $BASE HEAD; echo $?      # 1 = there are changes, 0 = nothing to review
```

A bad ref or an empty diff must fail **here**, not inside four parallel agents. Four agents pointed
at nothing will not say "there is nothing here"; they will find something to say about the
surrounding code. If either check fails, say which and stop.

With `--since <sha>`, the lenses read `<sha>..HEAD` only; the machine checks still run on the whole
branch. If `<sha>` is the head itself there is nothing new to read: do not widen the diff back to
the merge base, say so and stop.

### 1.2 Given a ticket, find every pull request that belongs to it

A ticket can mean several pull requests in several repositories (a backend change and its front-end
caller are normal). Find them all, review each, and report one summary.

```bash
gh pr list --repo <owner/repo> --state open --search "<ticket>" \
  --json number,title,headRefName,baseRefName,isDraft,url
```

**Filter by branch name, not by mention.** A search matches any pull request that quotes the number,
including releases and rollups. Keep the ones whose branch carries the ticket (whatever naming
convention the project uses). Skip branches that aggregate other people's work (release, rollup,
merge-forward): a finding there lands on the wrong author.

**Review drafts too**, and say it was a draft. **Skip what is genuinely stale** and say why: already
merged or closed, or so far behind its base that half the findings would concern code that has since
changed (report it as needing a rebase). When in doubt, review it.

If nothing is found, say so plainly: either the work has not started or the branch does not follow
the naming convention.

### 1.3 Scope the diff

```bash
git -C <repo> diff --stat        $BASE HEAD
git -C <repo> diff --name-status $BASE HEAD
git -C <repo> log --oneline      $BASE..HEAD
git -C <repo> status --short     # uncommitted work is in scope too, say so
```

Record the line count and the file count. If the project documents a size limit, compare against
it; otherwise use a working default of **under ~400 changed lines** as reviewable in one pass.

**If the diff is over ~1500 lines, say so before starting.** Past that size reviewers stop finding
defects and start summarising. Propose a split by commit or by directory and let the user choose.

If the change spans several repositories, scope each separately, run the pipeline once per
repository, and synthesise across them. A change to a shared schema, message shape or public API is
nearly always multi-repository even when the diff is not.

### 1.4 Fetch the ticket and the specification

Fetch the ticket with whatever tracker the project uses (`gh issue view <n> --json
title,body,comments`, a Jira/Linear/other tool if one is connected). **Read every comment**:
reproduction data, the second example and the reporter's real expectation often live there.

Then look for a specification or design document for this ticket (search the repository's docs
directory for the ticket number). If one exists, it, not the ticket body, is what the
implementation lens traces against.

If there is a pull request, read it too: `gh pr view <n> --json
title,body,files,reviews,comments`. Existing review comments tell you what has already been raised.

**If you cannot find a ticket, say so and ask.** Without one the implementation lens has nothing to
trace against and is skipped, and the review must be labelled as reduced, not presented as complete.

### 1.5 Find the project's written rules

The standards lens checks the change against **the rules this project wrote down for itself**, so
find them now and pass the paths. Look for, in this order: `CLAUDE.md`, `AGENTS.md`,
`CONTRIBUTING.md`, a PR template (`.github/pull_request_template.md`), and a docs directory with
coding standards, architecture notes, a testing guide or a list of known pitfalls. Also note the
linters' and formatters' config files, because whatever they enforce is not a review finding.

List what you found. If the project documents nothing, say so: the standards lens then reports only
what the neighbouring code establishes by consistent practice.

### 1.6 Mechanical checks: do them here, not in an agent

Branch name, branch base, PR title and diff size are decided by a regex and a count. Run them now
and hand the result to the standards lens.

```bash
git -C <repo> rev-parse --abbrev-ref HEAD
git -C <repo> diff --shortstat $BASE HEAD
git -C <repo> diff --name-only $BASE HEAD | wc -l
gh pr view <n> --json title,baseRefName,headRefName
```

Check each against the project's documented convention (branch naming, PR title format such as
Conventional Commits, target branch, size limit). Where the project documents no convention, skip
the row and say so. Generated files, lockfiles and snapshots inflate the count: report the total,
the total without them, and what you excluded.

### 1.7 Put the inputs on disk once

The lenses do not read this conversation. Write each input to a file once and pass paths:

```bash
mkdir -p /tmp/rv
git -C <repo> diff $BASE HEAD > /tmp/rv/<repo>.diff
gh issue view <ticket> --json title,body,comments > /tmp/rv/ticket.json
```

### 1.8 Report before proceeding

One short block: repository and branch, base commit and how you chose it, diff size, the ticket and
whether a specification exists, the project rules found, and anything you could not fetch. Then
continue without waiting; this is information, not a gate.

## Phase 2: Review, in parallel

Dispatch the four lens subagents in **one message**. Installed as the `besman` plugin they are named
`besman:review-*`; installed by `install-besman.sh` they are plain `review-*`. Use whichever form the
available agent types list:

| Subagent | Judges |
|---|---|
| `review-best-practices` | Whether it is good code, measured against the code around it |
| `review-security` | How the change can be abused: access control, injection, secrets, SSRF, XSS, disclosure |
| `review-implementation` | Whether it does what the ticket asked, and nothing it did not (only if a ticket was found) |
| `review-standards` | Conformance to the rules the project wrote down for itself |

If the subagents are not installed (no `review-*` agent type in either form), say so and stop rather
than substituting a general-purpose agent: the lens definitions are the review.

Run them in the **foreground** (`run_in_background: false`): a background agent may return after
your turn has ended, and in CI the run then finishes "successfully" with nothing published. Four
foreground calls in one message are still parallel. A ticket with three pull requests gets twelve
lenses in one message, not three rounds of four.

Give each the same header, with paths, not quoted text:

```
Skill: <absolute path>         where references/review.md is
Repository: <absolute path>
Branch: <branch>
Base commit: <sha>            the merge base, or --since
Diff file: /tmp/rv/<repo>.diff
Changed files: <name-status list>
Ticket file: /tmp/rv/ticket.json   (or "none")
Specification: <path, or "none found">
Project rules: <paths found in 1.5, or "none documented">
Mechanical checks: <the 1.6 results, already measured; do not re-measure>
Write to: /tmp/rv/<repo>-<lens>.json
```

Give the **base commit**, not "the current branch": an agent that re-derives the base will sometimes
derive a different one, and its citations then disagree with everybody else's. A lens that hits its
turn cap returns what it has; treat a missing or unreadable file as a check not run.

Do not feed one lens's findings into another's prompt. Cross-feeding creates one shared error that
then looks like independent confirmation.

## Phase 3: Linters, tests and SAST

**This is yours. Never delegate it.** A machine check is worth exactly its exit code and its output.
Start these before you dispatch phase 2 if you can.

**If CI already ran on this commit, read it instead of measuring again:**

```bash
gh pr checks <n> --json name,state,link
gh run view <run id> --log-failed | tail -80       # only for a failed check
```

Record each check with its conclusion and link; a pending check is recorded as pending, not assumed.

**Locally**, follow section 4 of `<skill>/references/review.md`: discover the project's own commands,
run only those for the languages the diff touches, compare against a measured baseline, and run a
SAST scanner scoped to the changed paths if one is installed.

For every check: the exact command, the exit code, the measured numbers, and whether it moved
against the baseline. For every check not run: which, and **why** (not installed, not applicable,
would call an external service, timed out).

## Gate: missing information

Collect `missing_information` from all lens files. For anything `blocking`, **ask the user before
going further**; if several lenses miss the same fact, ask once.

| Gap | Action |
|---|---|
| No ticket, or one that never states the expected behaviour | Ask. Without it the implementation lens cannot run |
| A business rule, threshold or external behaviour code cannot settle | Ask, or carry it as an explicitly unverified finding. Never assert it holds |
| Needs production data or telemetry to judge | Ask whether to query read-only, and query only the unsampled source |
| An image or attachment nobody could read | Ask what it shows. Never guess from the filename |

Non-blocking gaps do not stop the pipeline; carry them into the report as open items.

## Phase 4: Synthesis

### 4.1 Deduplicate, by machine

```bash
python3 <skill>/scripts/review-merge.py /tmp/rv/<repo>-merged.json /tmp/rv/<repo>-*.json
```

The script merges findings on the same file within two lines, keeps the strictest severity and the
sharpest failure text, records which lenses raised each, ranks the list, and names a lens whose file
did not parse as a check not run. Read the merged file, not the four lens files. Your judgement
starts there: correct a severity the whole picture warrants, apply the gates of 4b, write the
verdict.

Merge on **file and line**, not wording; three lenses landing on one line is evidence of importance
and survives as a note, not three entries. Two findings on the same line are **not** duplicates when
they describe different failures; split them back if the script merged them.

### 4.2 Rank by severity

Section 2 of the reference has the scale. Correct it, do not restate it: a lens that saw only its
own slice sometimes rates a finding lower than the whole picture warrants. Every finding above
`Note` carries a **concrete failure scenario** (inputs or state, then the wrong outcome); one without
it is an opinion, so demote or drop it.

### 4.3 One verdict, but never a masked axis

State each lens's outcome on its own line first:

```
Implementation vs the ticket: pass | fail | not run, one clause
Security:                     pass | fail, one clause
Standards:                    pass | fail, one clause
Code quality:                 pass | fail, one clause
Machine checks:               pass | fail | partly run, one clause
```

Merging four lenses into one list lets one axis hide another: code that follows every convention and
implements the wrong thing scores well on three lenses. The per-axis lines stop that.

Then the single verdict:

- **`READY`**: no Blocking and no Major findings, every applicable machine check ran and passed, and
  no warning count rose against its baseline.
- **`READY WITH FIXES`**: Major or Minor findings a competent author can fix without re-deciding
  anything. List them in the order to fix them.
- **`NOT READY`**: any Blocking finding, any failing machine check, any requirement traced to
  nothing, or any blocking gap still open.
- **`INCOMPLETE`**: a lens gave no output, so no verdict can cover its axis.

A check that could not run does **not** by itself make a change `NOT READY`. It narrows the verdict,
and the report must say what the verdict does not cover, as a sentence a reader will notice.

### 4.4 The report

```markdown
## Verdict
READY | READY WITH FIXES | NOT READY | INCOMPLETE, one sentence of justification

## Scope reviewed
Repository, branch, base commit, diff size in lines and files, ticket, specification, project rules.

## Blocking findings
Numbered. `file:line`, confidence (CONFIRMED or SUSPECTED), what is wrong in plain words, the
failure scenario (inputs → wrong outcome), the lenses that raised it, the suggested correction.

## Major findings
Same structure.

## Minor findings
Same structure, shorter.

## Machine checks
Table: check | command | exit code | measured result | moved against baseline?

## Checks not run
Every one, with the reason. SAST belongs here whenever no scanner was available.

## Dropped before publishing
Counts per gate: not confirmed, not bug-shaped, already raised. A run that dropped nothing did not
apply the gates.

## Open questions
Blocking gaps still unanswered, and what would resolve each.
```

Every finding is tied to a file and a line, or labelled as a suspicion.

**Do not fix anything.** Not the trivial ones, not while you are in the file. An author who receives
a review with half the findings silently applied cannot tell which half.

## Phase 4b: Earn the right to publish each finding

The failure mode of AI review is not a missed bug, it is noise, which ends with the bot muted. Every
finding passes three gates before it is published.

### Gate 1: confidence, which is not severity

*Severity* is how bad it would be; *confidence* is how sure you are it is real.

| Label | Test it must pass |
|---|---|
| **CONFIRMED** | You can state concrete inputs or state and the wrong outcome, and you have read every line on that path. Someone could reproduce it from your description alone |
| **SUSPECTED** | It looks wrong but you cannot construct the failing case: the path depends on data, config or a caller you did not see |

Write the failing case out. If doing so exposes a step you assumed rather than read, it is
`SUSPECTED`. **Only CONFIRMED findings reach the pull request**; SUSPECTED go to the job summary or
the local report.

### Gate 2: is it bug-shaped

Drop it if:

- **a linter already reports it** (formatting, import order, naming, unused variables);
- **it is a preference with no failure attached** ("could be extracted", "would read better");
- **it restates the diff** ("this adds a null check");
- **it is about code the diff does not touch**, and nothing in the diff makes it newly wrong.

### Gate 3: has it already been said

```bash
gh api repos/<owner>/<repo>/pulls/<n>/comments --jq '.[] | {path, line, body: .body[0:120]}'
gh pr view <n> --json comments,reviews
```

**Drop anything already raised**, by anyone, unless you add a fact that changes the conclusion.
Re-running on the same pull request must be safe.

If an earlier review of yours left open threads, decide for each whether the code **now** addresses
it (read the code, not the reply), answer on that thread, and never re-raise it as a new inline
comment. Open the review body with
`Re-review since <sha>: <k> earlier finding(s) addressed, <m> still open.`

Report how many findings each gate dropped.

## Phase 5: Publish back to GitHub

Skip if `--no-publish` was given or the change has no pull request.

Publishing is **outward-facing**. **Show the user the exact body and ask**, unless they already gave
standing authorisation in this session; then post and say you did.

**The review goes on the pull request**, whatever you were invoked with. When the run started from
a ticket, the ticket may get one line naming the pull request and the verdict, nothing more.

Three channels, each carrying what it is good at. Do not put the same thing in two.

### 5.1 Review with inline comments: the findings that need an answer

Write the review to a file and post it through the script, never by calling the reviews API by hand:

```bash
cat > /tmp/rv/review.json <<'JSON'
{
  "body": "<verdict, and every finding not tied to a line>",
  "comments": [
    { "path": "src/orders/quote.ts", "line": 305, "side": "RIGHT", "body": "<finding, failing case, correction>" },
    { "path": "src/orders/handler.ts", "start_line": 30, "line": 33, "side": "RIGHT", "body": "..." }
  ]
}
JSON
<skill>/scripts/review-publish.sh /tmp/rv/review.json <owner/repo> <n> <head sha>
```

The script reads the pull request's diff, keeps each comment whose line the diff can carry (`RIGHT`:
added and context lines; `LEFT`: removed and context lines; a range needs both ends inside), moves
the rest into the body under their path and line, posts **one** review with `commit_id` set, and
fails loudly if the inline comments did not land. One unresolvable anchor otherwise makes the API
reject the whole review with an unhelpful `422`.

**`event` is always `COMMENT`.** Never `APPROVE` (a bot approval satisfies branch protection meant
for a human). Never `REQUEST_CHANGES` (it blocks the pull request until a person clears it by hand).
A single issue comment instead of a review is a failed publish: it leaves "Files changed" empty.

| The finding is about | Where it goes |
|---|---|
| A specific line the diff touches | Inline, on that line |
| A range the diff touches | Inline, `start_line` with `line` |
| Something absent: a missing test, an unhandled case | The review body |
| The change as a whole, or a line the diff does not touch | The review body, with path and line written out |

**Do not manufacture an anchor**, and **do not inline what needs no answer** (praise, restatements,
observations nobody will act on). Every inline comment asks a person to respond.

#### Suggested changes, for fixes that are already decided

A ` ```suggestion ` block inside an inline comment renders with **Apply suggestion** and replaces
exactly the anchored lines. Use it only when both hold: **the fix is fully determined** (a wrong
constant, an inverted comparison, a missing null check, a typo; no design choice), and **you proved
it** (ran it, measured it, or cited the code that settles it). A suggestion is one click from being
committed, so an unproven one costs more when wrong.

### 5.2 Check run: the verdict (optional)

Only a GitHub App token can create check runs; a personal access token is refused. If one is
available:

```bash
GH_TOKEN="$APP_TOKEN" gh api repos/<owner>/<repo>/check-runs --method POST \
  -f name='review' -f head_sha='<sha>' -f status='completed' \
  -f conclusion='success|failure' \
  -f 'output[title]=READY WITH FIXES: 0 blocking, 2 major' -f 'output[summary]=<a few lines>'
```

**Never use `conclusion: neutral`**: it renders grey and reads as passing. Without an app token,
skip it and say you did.

### 5.3 Job summary or local report: everything else

In CI, `cat report.md >> "$GITHUB_STEP_SUMMARY"`; locally, show it to the user. This is where the
long material goes: every machine check with its command and exit code, every check that could not
run, the SUSPECTED findings, the gate counts, the scope.

### Rules that are not yours to relax

Never merge, never push, never approve. Never quote a secret: in a PR comment it is a second
disclosure, harder to purge than the first. If the review is `NOT READY` because of an exploitable
security finding, ask whether a public comment is the right channel at all.

Never write a live `@`-mention of a bot or agent command in anything you post: a comment that
mentions a command can trigger it, and a chain between two agents has no natural end.

## Reporting to the user

State the verdict, the counts by severity, the machine-check results with their numbers, every check
that could not run and why, and anything still blocking. Never present a review as complete while a
lens did not run or a check silently failed. If the implementation lens did not run for lack of a
ticket, say so first, because it changes what the verdict means.

## When not to use this

- **A one-line change with an obvious effect.** Read it; the pipeline costs more than the diff.
- **Unfinished code.** Findings about absences that were always going to be filled drown the real
  ones.
- **A design question, or a change that does not exist yet.** Review the design document instead.
- **A diff over ~1500 lines.** Split it first (1.3). A large diff is a reason to split, not to skip.
