---
name: test
description: Verifies one task end to end before and after the change, with the same inputs on both sides. Reads the ticket, specification and acceptance criteria, derives every test case worth checking (Gherkin where the behaviour is business-facing), checks backend changes for efficiency, correctness, best practices and overcomplication with four parallel subagents, drives the UI live through Playwright and with the cursor in a real browser, keeps local, test and production strictly apart, and adds the automated tests that were missing. Use when asked to test, verify or quality-gate a ticket, a branch or a completed change.
---

# Testing an implementation

**Evidence before verdict. The same inputs on both sides. Test the artefact that runs, not the
source you edited. A check that did not run is not a check that passed. Know which environment you
are in before you touch anything.**

This pipeline decides whether a change does what the task asked and breaks nothing else. Every
check has a name, a fixed input, a measured value and a threshold, and the base and the branch are
measured the same way.

It writes tests. It does not write production code. When a check fails, report it; do not fix it
here, because a pipeline that repairs what it measures cannot be trusted with the next measurement.

## Paths

`<skill>` is this skill's directory, `${CLAUDE_SKILL_DIR}`, resolved to an absolute path; its
`references/` hold the mechanics. The four subagents are installed beside it, named
`besman:test-*` as a plugin or `test-*` when installed by script; use whichever the available agent
types list. Every subagent prompt carries `Skill: <absolute path>`.

## Invocation

```
/besman:test <ticket>                  find the ticket's branch or pull request and test it
/besman:test                           the current branch of the repository you are in
/besman:test --pr <n>                  a pull request
/besman:test --env local|test|prod     the environment to verify in (default: local)
/besman:test --no-baseline             skip the before run, only when the base cannot be built
/besman:test --surfaces <a,b>          limit the browser surfaces
/besman:test --no-automate             measure only, add no tests
/besman:test --quick                   acceptance criteria only, skip the dimension sweep
```

## Phase 0: Knowledge base and environment, before anything else

### The knowledge base

Read `.besman/` at the project root (`git rev-parse --show-toplevel`): `rules.md` always, then
`environments.md`, `testing.md`, `constraints.md`, `standards.md`, `pitfalls.md`, `project.md`.
Rules there outrank this skill's defaults; only the ticket's own acceptance criteria outrank
`rules.md` for this ticket.

**If `.besman/` does not exist**, say so and offer `/besman:project init` before continuing. If the user
declines, continue on what the project itself documents, and treat every host you cannot place as
production (below).

### Which environment, said out loud

Read `<skill>/references/environments.md`. Then, before the first command that touches a running
system, state in one line: the target environment, its URLs, the env file in use, and how you know.

| | Local | Test (staging, QA, preview, shared dev) | Production |
|---|---|---|---|
| Build, restart, rebuild | Yes | No: it runs what was deployed | No |
| Create fixtures, write data directly | Yes: guarded, recorded, restored | **No**, unless the user instructs that one write now | **Never** |
| Act through the UI or API as a user | Yes | Yes, with test accounts; clean up what you create | **Only reads, only when the user asked** |
| Load, fuzzing, security probes | Yes | Only if the user asks | **Never** |
| Send email, SMS, payments, webhooks out | Only to sandboxes | Only to sandboxes | **Never** |

**A host you cannot place is production.** Placement comes from `.besman/environments.md`; failing
that, from the rules in the reference (localhost and compose names are local; `staging`, `stage`,
`qa`, `test`, `dev`, `preview`, `sandbox` in the host are test). Anything else is production until
the user tells you otherwise.

**A PASS in one environment never clears another.** Every row of the ledger records where it ran.
Production credentials are never used for a test run, and secrets are never copied between env
files.

### Credentials and sign-in

Find the variables the run needs (API tokens, test-account logins, provider keys) by **name** in the
env file for the target environment and in `.besman/testing.md`. Check presence without printing:

```bash
set -a; . ./.env.local; set +a; for v in E2E_USER_EMAIL E2E_USER_PASSWORD API_TOKEN; do [ -n "${!v}" ] && echo "$v set" || echo "$v MISSING"; done
```

When something is missing, **stop that part and ask the user**, precisely:

- for a browser session: "please sign in at <url> in <the browser I am driving>, then tell me";
- for a token or test account: "add `API_TOKEN` to `.env.local` (a token for the **local**
  environment, not production), then tell me".

Never ask for a secret in the chat, never type a password or one-time code yourself, never print a
value, never take a credential from one environment's file to use in another. Checks that need the
missing access are `NOT RUN` until it arrives; everything else continues.

## The pipeline

```
 0. Knowledge     .besman/, the environment, credentials
 1. Context       you, inline: ticket, comments, spec, acceptance criteria, Gherkin, diff
 2. Analyse       four subagents in parallel, one message:
                    test-survey      what automated tests already cover, where the gaps are
                    test-designer    every test case worth checking, Gherkin where it belongs
                    test-efficiency  backend efficiency, correctness, overcomplication
                    test-verifier    requirement trace, concurrency, authorisation, from the code
 3. Plan          you: one checklist of named checks from their output
 4. Environment   bring up what the target environment allows; prove every component runs the branch
 5. Before        base build, fixed inputs, every measurement recorded
 6. After         branch build, the same inputs, the same measurements
 7. Compare       defect reproduces before, gone after; nothing else regresses
 8. Trace         every criterion to evidence; say what could not be tested
 9. Automate      unit, integration, API, Gherkin and Playwright tests for what was checked by hand
10. Report        the ledger, failures, efficiency, environment, gaps
```

## Phase 1: Context, not the ticket title

Fetch the ticket with whatever tracker the project uses (`gh issue view <n> --json
title,body,comments`, or a connected Jira/Linear tool). Read every comment in order. Then, in order
of authority: the specification and its acceptance criteria (`.besman/specs/<id>-spec.md` from
`/besman:spec` first, then the project's docs), the Gherkin scenarios, the latest
agreed decision in the comments, the diff, then `.besman/` and the project's documented rules.

Where the ticket body and a later comment disagree, the latest agreed decision wins; say which you
followed. With no specification, say so at the top of the report and derive the criteria from the
ticket and the code, labelled as derived.

**Read the diff before planning.** A checklist written without it tests the ticket, not the change.

```bash
mkdir -p /tmp/tv
git -C <repo> diff <merge-base> HEAD > /tmp/tv/<repo>.diff
```

## Phase 2: Four subagents, in parallel

Dispatch all four in **one message**, foreground (`run_in_background: false`), each with the same
header:

```
Skill: <absolute path>
Knowledge base: <path to .besman/, or "none">
Repository: <absolute path>
Base commit: <sha>
Diff file: /tmp/tv/<repo>.diff
Changed files: <name-status list>
Ticket file: /tmp/tv/ticket.md   (or "none")
Specification: <path, or "none">
Environment: <local | test | production>
Write to: /tmp/tv/<agent>.md
```

| Subagent | Returns |
|---|---|
| `test-survey` | Existing coverage of the changed behaviour, gaps, weak assertions, the test projects and helpers to extend, the BDD runner and e2e setup if any |
| `test-designer` | The full case matrix for this task, each case with technique, input, expected result, level, priority; Gherkin for business-facing behaviour |
| `test-efficiency` | Backend efficiency risks (N+1, unbounded reads, missing indexes, chatty calls, missing timeouts, complexity), each with the measurement that will confirm it; overcomplication with the simpler version; errors in error handling |
| `test-verifier` | Requirement trace over the diff, and the concurrency and authorisation behaviour the code implies |

They read code; you run the system. Where their reading and your measurement disagree, say so: that
line is often the most valuable in the report.

## Phase 3: The checklist, before any measurement

Merge the four outputs into one checklist. **Every check has five things**; a check missing one is
not ready to run:

| Field | Rule |
|---|---|
| `id` | `dimension.thing.surface`, for example `function.cutoff.create`, `perf.orders-list.query-count` |
| Input | Fixed and written down: an identifier, a payload, a date in UTC. Never "today", never "some user" |
| Measurement | The command, query or browser action that produces the value, and where it is read |
| Threshold | What makes it pass, stated before the run |
| Traces to | The criterion, scenario, rule in `.besman/` or the efficiency risk it verifies |

Start from the specification's verification cases and the Gherkin scenarios, then the designer's
matrix, then sweep the dimensions. The sweep is what catches what nobody was looking for; only
`--quick` skips it, except `Viewport`, which always runs when there is a UI.

| Dimension | Ask |
|---|---|
| Correctness | Does each acceptance criterion hold on the data the ticket describes? |
| Boundaries | Zero, empty, null, first and last permitted value, one past it |
| Time | Midnight, month end, DST change, leap day, a stored timestamp without a zone, a date in the past |
| Idempotency, concurrency | The same request twice, two users at once, a message delivered twice, a button clicked three times |
| Authorisation | Every touched route and job as anonymous, as the owner, **as another user**, as a higher role |
| Data | Records written before the change still read; a needed migration exists and runs both ways |
| Compatibility | The other side of every contract the diff changes: clients, queues, stored shapes, public responses |
| Failure | A dependency down, a query empty, an external call timing out |
| **Efficiency** | Query count, rows read, latency at realistic size, memory: **measured**, see below |
| Observability | When this fails in production, does a log, metric or alert say so? |
| Interface | Driven live, not rendered: see below |
| Media | Every image and file the surface should show actually loaded |
| Lifecycle | How the surface changes over time, not only the settled state (`references/lifecycle-recorder.md`) |
| Viewport | Every touched surface at a phone width and a desktop width |
| Documentation | A document that now describes behaviour that no longer exists |

Rule out the dimensions that do not apply, one line each. "Not applicable" is a finding; silence is
not.

### Backend tasks: efficiency, correctness, simplicity, measured

For a backend change, the efficiency subagent predicts; you measure. Turn each of its risks into a
check with a realistic input size and a threshold (from `.besman/constraints.md` where it states a
budget):

- **Query count per request** with N related rows (1, 10, 100): constant is a pass, growing with N is
  an N+1. Measure with the ORM's SQL logging, the database's statement log, or the APM span count.
- **Rows read and plan**: `EXPLAIN`/`EXPLAIN ANALYZE` (or the store's equivalent) on every new query
  shape; a full scan on a table that grows is a fail.
- **Latency and memory** at a realistic size, base against branch, same data.
- **Outbound calls**: count them, check timeouts and retries are set, and that a failure is handled.
- **Errors**: drive every error path the diff adds; the response, the log line and the state after
  must all be right.

An **overcomplicated** solution the subagent found goes in the report with its simpler version and
the proof they behave the same; it is not a test failure, and it is not fixed here.

### Every test case worth checking, and Gherkin where it belongs

The designer's matrix is the floor, not the ceiling: add what you think of while running. Each case
names the technique that produced it (partition, boundary, decision table, state transition,
pairwise, error guessing), so a reader can see what was covered systematically.

**Gherkin** is for behaviour a business person would recognise: user journeys, business rules, API
contracts clients depend on. Use `Scenario Outline` with `Examples` for partitions and boundaries.
Internal helpers and pure functions get unit cases instead. If the project has a BDD runner (see
`.besman/testing.md` or the survey), the scenarios become `.feature` files in its location with step
definitions; if it does not, they go in the report and are implemented as ordinary tests named after
the scenario. Do not add a BDD framework to a project that has none without asking.

### An interface change is driven live, with the cursor

**When the diff touches anything a person sees or clicks, and whenever an existing screen shows the
effect of a backend change, the interface is exercised in a real browser.** Unit tests proving a
rule say nothing about whether the screen reflects it. Mechanics:
`<skill>/references/browser-verification.md`.

| Need | Tool |
|---|---|
| The user's own signed-in session, exploratory driving with the cursor like a person | Claude in Chrome (`mcp__claude-in-chrome__*`), or the desktop app's browser pane (`mcp__Claude_Browser__*`) |
| Phone width, isolated session, scripted steps driven live | Playwright MCP (`browser_navigate`, `browser_click`, `browser_resize`, `browser_snapshot`, `browser_evaluate`) |
| The repeatable regression this run leaves behind | A Playwright test in the project's e2e folder |

Drive it yourself, step by step, watching what comes back; a green `playwright test` run is what you
leave behind, never a substitute for the live pass. Map every control from the component source
before the first click, scroll past the fold, confirm writes reached the server, run the QA cases
(double click, back/forward, reload mid-flow, empty and maximum input, two tabs, keyboard only, slow
network), and measure at 390×844 and at desktop width. A run that did only one of live and automated
is half a run: say which half.

## Phase 4: The environment, and proof it runs the branch

**Local**: bring the stack up as `.besman/project.md` or the project README says. **Rebuild and
restart every component that carries the change, and prove it**: a service started before the branch
is running the old code, and every green check against it is worthless.

```bash
git -C <repo> rev-parse --short HEAD
# rebuild, restart, then prove the running artefact holds the change:
# a symbol the diff removed is gone, a new route answers, the version endpoint reports the commit
```

Record one row per component: repository, commit, built at, restarted at. The same applies to a dev
server holding a stale build cache and a browser tab holding an old bundle.

**Test environment**: you do not build or deploy. Prove which commit is deployed (a version endpoint,
a build-info header, the deploy log) and that it contains the branch; if it does not, the run is
`NOT RUN` for that environment, not a verdict on the change.

**Production**: read-only verification of something already released, and only when the user asked.

### Identities

Authorisation cannot be measured with one account. Establish anonymous, the owning user, **another
user of the same role**, and a higher role where one exists; say which you had. **An account with
more than one role hides every horizontal-access defect**: use single-role test accounts.

### Fixtures: local only, under four rules

A check that needs a state the seed lacks is not blocked: build the fixture, **locally**. Prefer the
API or the project's own seed scripts; write data directly only as a last resort.

1. **Guard the target**: the fixture script refuses to run unless the connection is local.
2. **Record, then restore**: save the original, restore it at the end, print both.
3. **Patch the field, do not rewrite the record.**
4. **Respect the store's keys and invariants**, and read the result back through the API.

In a test environment, reach the state through the API or the UI as a user would; if neither reaches
it, the check is `NOT RUN`. A direct write there needs the user's explicit instruction for that one
write, now, and is reported.

## Phases 5 and 6: Before, then after, with the same inputs

Run the whole checklist on the base build and record every measurement, then the branch build with
the same inputs. Locally, use a worktree for the base:

```bash
git -C <repo> worktree add /tmp/tv/base <merge-base>
```

- **Identical inputs, pinned.** Dates in UTC. Fixed expected values, never recomputed with the
  production formula.
- **The defect must reproduce on the base.** If it does not, stop and say so.
- **Collapse waiting into data.** Choose inputs that put a timer's moment in the past instead of waiting.
- **Prove the route reaches the code under test**, and that the branch of every `if` on config,
  credentials or feature flags you exercised is the one the target environment takes.
- **Prove each passing check is not vacuous**: change one input so it must fail, and watch it fail.
- **A negative control must fail for the right reason.**

A surface the change adds has no baseline: judge it on its own against the criteria, with absolute
checks ("no console error"), not relative ones ("no new console error").

## Phase 7: Compare, and classify

| Verdict | Means |
|---|---|
| `PASS` | Measured, meets the threshold |
| `FAIL` | Measured, does not: worse than base, or a criterion does not hold |
| `INFO` | Measured, changed, and the change is intended: say why |
| `NOT RUN` | Could not be measured: say what blocked it. **Never PASS** |

Before reporting a failure, classify it: **the change is wrong** (fails on branch, not on base),
**the environment is limited** (fails on base too: a limit, and the affected checks are `NOT RUN`), or
**the environment is flaky** (retry once; a non-repeating failure does not decide the verdict). Unwrap
wrapped exceptions to the real error before classifying.

## Phase 8: Trace against the ticket

Every acceptance criterion, requirement, Gherkin scenario and rule from `.besman/rules.md` that the
change touches gets a row: the check that covers it and the evidence. Anything without a row is a
gap and is reported as one. Never convert an absence of evidence into a clearance.

## Phase 9: Leave the checks behind

For every check that can be automated and is stable, add or extend a test, following
`.besman/testing.md` and the survey (extend before duplicating):

| Where the behaviour lives | What to write |
|---|---|
| A domain rule, a calculation, a handler | Unit tests in the project's framework, one case per partition and boundary |
| A route, its authorisation, its status codes, its query count | API or integration tests, including another-user and anonymous calls, and a query-count assertion where efficiency was the risk |
| A business-facing behaviour | Gherkin `.feature` with steps if the project has a BDD runner; otherwise a test named after the scenario |
| A user journey in the browser | Playwright in the project's e2e folder, reusing its auth setup; cover the controls you operated and the QA cases that fired |

Run a new browser test three times before keeping it; an unstable test teaches people to ignore the
suite. Run the suites the change touches and report the numbers. Failures that also fail on the base
are not yours: report them in one line and leave them.

## Phase 10: Report

Lead with the verdict, the environment and the counts, then the ledger:

```
| Env | Dimension | Check | Verdict | Base | Branch | Threshold |
|---|---|---|---|---|---|---|
| local | Efficiency | `perf.orders-list.query-count` | FAIL | 3 | 3 + N (103 at N=100) | constant in N |
```

Then, in this order:

1. **Failures**, each with input, measurement and what it means for the ticket.
2. **Efficiency and simplicity**: measured results, and every overcomplicated part with its simpler
   version.
3. **The requirement trace**: criterion or scenario, check, evidence.
4. **Environment and provenance**: which environment each check ran in, component, commit, built at;
   which branch each environment-dependent `if` took.
5. **Interface**: widths measured at, the control map and which controls were operated, the tool used
   for each pass, the QA cases run and skipped.
6. **Not run**, and what blocked each, including access the user still has to provide.
7. **Tests added or extended**, with suite results; Gherkin scenarios written and where.
8. **Environment changes you made**, and which are still in place.
9. **Unrelated things you noticed and did not touch**, one line each.
10. **Knowledge to keep**: anything durable learned (a trap, a missing test account, an environment
    quirk), offered for `/besman:project rule`, never written silently.

Do not post the report to the ticket or pull request on your own; offer, and post only when the user
agrees. Never write a live `@`-mention of a bot command in anything you post.

## Scope

Test what the change touches and the contracts it crosses. Do not audit the repository, do not
rewrite unrelated tests, do not fix what you find. Two narrow exceptions: a test you had to make
deterministic for this run, and a document this change made wrong; say what you did and why.

## When not to use this

- **Judging code quality, security and standards on a diff**: that is `/besman:review`.
- **Deciding what the behaviour should be**: that is a specification, before code.
- **Nothing has been implemented yet**: a checklist without a before and an after is a plan.
