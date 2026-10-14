# Code review reference

Shared by the `review` skill and the four `review-*` subagents. Each of them reads **only the
sections its own definition names**, not the whole file.

This file states defaults that hold in any repository. Where the project's own written rules
(`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, a docs directory) disagree with it, the project wins
and this file is wrong for that project. Say so in the review.

---

## 1. Evidence and honesty

Binding on every lens.

1. **Cite `file:line`** for every finding, and quote the current source. A finding nobody can
   locate is a suspicion; label it as one or drop it.
2. **A failure scenario is mandatory** above `Note`: the inputs or the state, then the wrong
   outcome. Without one you have an opinion, not a finding.
3. **Never report a check you did not run.** "No security issues found" after the scanner failed
   to start converts an absence of evidence into a clearance, and nobody downstream can tell.
4. **Measured output beats documentation.** Project documents go stale without anyone noticing.
   When a doc and the code disagree, the code wins and the doc is then a finding.
5. **Label material claims** `VERIFIED` (read it), `INFERRED` (follows from what you read) or
   `UNKNOWN` (could not settle it).
6. **A gap you cannot close by searching** goes in `Missing information`, marked `BLOCKING` or
   `DEFERRABLE`. You cannot talk to the user; the orchestrator asks.
7. **Do not fix anything.** Not the trivial ones, not while you are in the file. An author who
   receives a review with half the findings silently applied cannot tell which half.

Safety: read-only. Never run anything that mutates state, deploys, or calls an external service.
Never quote a secret — name the file and the line.

---

## 1b. Say it in ordinary words first

**A finding nobody understands has not been reported.** The person deciding what to do about it is
often not the person who wrote the code, and never the person who wrote the review.

**Open with one sentence, in ordinary words, saying what happens.** No file path, no identifier, no
requirement number until after it. "A customer who edits their saved address loses the second line
of it" is a finding. "REQ-4 is unreachable on two of the five paths the flag was threaded through"
is a note to yourself.

**Names are labels, not meaning.** `REQ-4`, `D5`, `m1`, `IOrderSummaryFactory` are useful for
finding things again. A sentence that stops making sense when they are removed has said nothing.
Write the sentence so it survives without them, then add them.

**Everything else stays.** The evidence, `file:line`, the measured output, the failure scenario:
they follow the plain sentence, they do not replace it and are not replaced by it. Being
understandable is not being vague.

**A question to a human is not a finding.** When a finding needs a decision that is not yours,
write the question separately and make it answerable:

- what the situation is, in ordinary words
- the choices, as few as are real
- what each one costs, and what becomes impossible

"Worth considering whether the four-field list was meant to be exhaustive" is not answerable.
"A user can type a phone number into the free-text company field and every other user sees it.
Mask that field too, or leave it and record why?" is.

**The test.** Read it back as though you had not seen the diff. If you cannot say what happens and
what is being asked, rewrite it, however accurate it already is.

---

## 2. Severity

| Severity | Meaning |
|---|---|
| **Blocking** | Data loss, money moved wrongly, an authentication or authorisation hole, a secret exposed, a production failure path with no recovery. Also: a requirement the ticket asked for that is not implemented |
| **Major** | Wrong behaviour under conditions that will occur, a silent failure, a standard breached in a way that will bite later |
| **Minor** | Real but survivable — naming, duplication, a weak test, a stale document |
| **Note** | Observation with no failure scenario. Keep these few, and never let one outrank a Minor |

Money paths and lifecycle changes get the highest scrutiny. For a payment change, verify the
*direction*: could it charge or pay twice, or fail to at all?

---

## 3. Production telemetry

You should rarely need it. Read-only, and only when explicitly requested.

**Query the unsampled raw source, not a sampled or aggregated view.** Many observability stacks
expose both, and the convenient one silently returns a fraction of the data or a shorter window:
an Azure Application Insights component versus the Log Analytics workspace behind it, a sampled
APM trace view versus the raw logs, a dashboard of pre-aggregated metrics versus the events under
it. Find out which you are querying before drawing a conclusion from an absence.

Every telemetry claim states the **time window** queried and whether the source is **sampled**.
"No errors" from a sampled view over the last hour says little about last week.

---

## 4. Machine checks — commands and measured environment

Read by the **orchestrator only**, in phase 3. The lenses do not run these.

### Discover the commands from the project

Do not guess a toolchain. Read what the project declares, roughly in this order of authority:

1. **CI workflow files** (`.github/workflows/*.yml`, `.gitlab-ci.yml`, and the like): the most
   reliable statement of what is actually gated on a pull request. Run what they run.
2. **Task runners**: `package.json` scripts, `Makefile`, `justfile`, `Taskfile.yml`.
3. **Language manifests**: `pyproject.toml` (with `tox.ini`, `noxfile.py`, hatch environments),
   `*.sln` / `*.csproj`, `go.mod`, `Cargo.toml`, `pom.xml` / `build.gradle(.kts)`.

**Run only what the diff touches.** A change confined to one package does not need every suite in
the repository; a change to shared code does need its dependants.

### Typical commands, as examples

| Ecosystem | Type check / build | Lint / format | Tests |
|---|---|---|---|
| TypeScript / JavaScript | `npx tsc --noEmit` | `npx eslint .`, `npx prettier --check .` | `npm test` |
| Python | `mypy .` or `pyright` | `ruff check .`, `ruff format --check .` | `pytest` |
| .NET | `dotnet build` | `dotnet format --verify-no-changes` | `dotnet test` |
| Go | `go build ./...`, `go vet ./...` | `gofmt -l .`, `golangci-lint run` | `go test ./...` |
| Rust | `cargo check` | `cargo clippy -- -D warnings`, `cargo fmt --check` | `cargo test` |
| Java / Kotlin | `./gradlew build` or `mvn -q compile` | the configured `spotless`, `checkstyle`, `ktlint` task | `./gradlew test` or `mvn test` |

Prefer the project's own wrapper (`npm run lint`, `make check`, `hatch run test`) over these when
one exists: it carries the project's flags and config.

### Compare against a baseline

**A linter that exits 0 with warnings proves nothing.** Many projects tolerate a standing set of
warnings, so the exit code alone cannot show whether the diff added one. Measure the base commit
the same way and compare:

```bash
git -C <repo> worktree add /tmp/rv/base <base sha>
# run the same command in /tmp/rv/base and in the branch, then:
git -C <repo> worktree remove /tmp/rv/base
```

Report counts and **rule names**, not only totals: one new warning of an unusual rule matters more
than the count suggests, and a total that stayed flat can hide one fixed and one introduced.

### Environment faults are not defects

A check that cannot start for reasons the diff did not cause is **not run**, never **failed**.
Reporting it as a break sends the author after something they did not do. Typical causes:

- **Uninitialised git submodules.** `git submodule status` shows a leading `-`; try
  `git submodule update --init --recursive`. If it needs credentials you do not have, stop there.
- **Wrong SDK or runtime selected.** Without a `global.json`, `.nvmrc`, `.python-version`,
  `rust-toolchain.toml` or similar pin, the machine's default may not be what the project targets.
  On a framework or version error, check the installed versions (`dotnet --list-sdks`,
  `node --version`, `python --version`) before calling it a defect.
- **Missing services**: a database, a queue, an emulator, a container the tests expect to be
  running.

State the cause and the command you tried.

### Monorepos and multiple solutions

**The main project is not the whole repository.** Services, workers and packages often have their
own solutions, test projects or `package.json`. Build and test every one the diff touches;
running only the top-level suite and reporting "tests pass" is a false clearance.

### Never run tests that leave the machine

**Never run integration or end-to-end suites that call real external, staging or production
services**, even if the project's scripts make it easy. Reviewing does not license it. If those
suites are the only coverage for the change, list them under `Checks not run` with that reason.

### SAST

Two mechanisms may exist. Check both, use whichever is present, **say plainly when neither is**.

1. **A local scanner.** `semgrep --version`; if present:

   ```bash
   semgrep scan --config auto --error --json <changed paths>
   ```

   Scope it to the changed paths: a whole-repository scan returns the standing backlog and buries
   the diff.
2. **Results fetched through an MCP server or a dashboard.** **These do not scan.** They return what
   a previous scan uploaded. If that scan predates this branch it says nothing about this diff —
   state which scan, how old, and that the diff itself was not scanned.

If neither is available, the review says so in `Checks not run`.

Never substitute a keyword grep for a scanner and call it SAST — grep finds string literals, not
taint paths, and presenting one as the other is a false clearance in a different costume. Offer to
install the scanner; install nothing without asking.

`review-security` reads the code with judgement and does not depend on the scanner. A missing
scanner narrows that lens; it does not remove it.
