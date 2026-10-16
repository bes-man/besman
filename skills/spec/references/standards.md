# Specification standards

The project's own rules come first: `.besman/rules.md`, then `.besman/standards.md` and
`.besman/constraints.md` (created by `/besman:project`). Where they and this file disagree, the
project wins.

Shared reference for writing and reviewing a specification. Read the sections your step needs, not
the whole file.

---

## 0. Project sources of truth — read them, do not re-derive them

This file governs **how a specification is written**, not how the project works. That lives in
`.besman/rules.md` (binding rules, safety, branch and review conventions), `.besman/standards.md`
(coding, testing, documentation) and `.besman/constraints.md` (architecture, external systems,
limits), and in whatever they point to: known traps, domain model, glossary. Open the ones your
task touches. Never re-derive what they state, and never contradict them silently — if the code
disagrees with a document, the code wins and the document is fixed in the same change. If
`.besman/` does not exist, say so once and work from the code and the repository's own docs.

### Safety, in short

- **Never write to production** — no infrastructure, settings or database writes. Read-only
  investigation is fine when explicitly requested.
- **Never execute a financial transfer, refund or payout.** Surface the numbers; a human acts.
- **Never commit or quote a secret.** Names and locations only.
- **Never push a branch or open a pull request.** A specification writes a document, not code.
- When a rule blocks you, say so and propose the safe alternative. Do not work around it quietly.

A `change` or a `feature` is also bound by `design-principles.md` in this directory (section 5
lists its questions). A bug fix does not need it.

---

## 1. Evidence rules

These override everything else. A confident wrong statement is worse than an admitted gap.

1. **Verify in the code.** Never state how the system behaves from memory, a ticket, a meeting
   note or another agent's summary. Open the file.
2. **Cite `Repo/path/file.ext:line`** for every factual claim, where `Repo` is the checkout
   directory's name. A claim without a citation is an opinion and is marked as one.
3. **Line numbers move.** For a specific statement, also quote the current source text.
4. **Mark confidence explicitly.** Use exactly these labels:
   - `VERIFIED` — read in the code or observed in command output during this run
   - `INFERRED` — a reasonable conclusion, with the reasoning stated
   - `UNKNOWN` — could not be determined; say what would be needed to determine it
5. **Never invent identifiers.** If you have not seen a class, field, endpoint, environment
   variable or command, do not name it. Search for it, or record it as `UNKNOWN`.
6. **Report the unwelcome finding.** If the evidence contradicts the ticket, the requester, or
   your own earlier conclusion, say so plainly and show the evidence.

If the project has its own marker for unverified claims in text that lands in the repository, use
it there as well.

### Never fill a gap with something plausible

The rule that matters most, because the failure is invisible: invented content reads exactly like
researched content.

| The gap is | Do this |
|---|---|
| **Findable** — it exists in the code, config, tests, history or the ticket | Find it. Do not ask, do not assume |
| **A human's to supply** — a decision, an intent, the content of a screenshot, an unwritten business rule | **Stop and ask.** Say precisely what you need and why it blocks you |
| **Genuinely unavailable** — needs access you do not have, or data that does not exist | Mark it `UNKNOWN`, state what it would take to resolve, and what the specification cannot claim without it |

**Never:** invent an identifier, an expected value, a number, a date or a threshold; invent
reproduction steps you have not traced through the code; describe an image or attachment you
could not read; turn a ticket title into an intent; present a plausible assumption as a finding;
write a requirement whose subject you could not locate; keep going with a gap because it seemed
small.

### How to ask for missing information

A useful request is specific enough to be answered in one message. State:

1. **what is missing** — the exact fact, not "more detail";
2. **why it blocks you** — which requirement, verification case or decision depends on it;
3. **what would resolve it** — a file, a screenshot description, a person, a data query, one answer;
4. **what you already tried** — so the reader does not repeat your search.

> Bad: "The ticket lacks detail, please clarify."
>
> Good: "The ticket says the export was wrong but not what it should contain. Nothing states the
> expected column order, which blocks REQ-3. A corrected sample file, or confirmation that last
> month's export was right, would resolve it. The tests and the docs do not specify it."

**Subagents cannot talk to the user.** A subagent puts the request under `Missing information`
in its report, marked `BLOCKING` or `DEFERRABLE`, and continues with everything that does not
depend on it. A partial report with an honest hole is useful; one with an invented patch is not.

---

## 1b. The ticket is the brief

**Everything starts from what was asked.** The author decided what they want; the job is to make
that buildable and verifiable, not to improve on it. A requirement that contradicts the ticket's
statement of the desired behaviour is wrong even when it is better engineering. Never propose an
option the ticket already settled, and never widen the ask: an adjacent improvement is a follow-up,
reported in one line.

**When the ticket is short or ambiguous, ask.** Two readings of one sentence produce two different
systems. Look for the answer in the code and the docs first; if it is genuinely intent, ask — one
question, in business language, with the readings spelled out:

> The ticket says the banner should be dismissible. Two readings: dismissed for this visit, or
> dismissed permanently for this device? The current banner uses a one-year cookie, so
> "permanently" would match what exists. Which did you mean?

Do not pick the likelier reading and carry on: an assumption written as a requirement looks exactly
like a decision the author made, and the guess ships.

---

## 2. Requirement quality — ISO/IEC/IEEE 29148:2018

Every requirement statement must be:

| Characteristic | Practical test |
|---|---|
| Necessary | Removing it changes the delivered result |
| Implementation free | Describes observable behaviour, not code, classes or algorithms |
| Unambiguous | Only one reading is possible |
| Singular | One requirement, one statement. No "and" joining two obligations |
| Verifiable | A test or an observation can prove it true or false |
| Feasible | Achievable within the system and the constraints |
| Complete | Needs no other text to be understood |
| Conforming | Uses `shall` for obligation — exactly one `shall` per requirement |

The requirement **set** must additionally be complete, consistent, feasible, comprehensible and
able to be validated.

**Implementation free is the rule most often broken.** "The handler shall call
`CalculateX(a, b)`" is not a requirement. "The cut-off shall equal the delivery date minus the
notice period in calendar hours" is.

**Statement patterns** keep the trigger and the response apart and make the verification case
obvious: "The `<system>` shall …" (always); "When `<trigger>`, the `<system>` shall …" (event);
"While `<state>`, …" (state); "If `<condition>`, then the `<system>` shall …" (unwanted
behaviour); "Where `<feature is present>`, …" (optional feature). A requirement that needs two
triggers or two responses is two requirements.

---

## 3. One artifact — requirements only

The skill produces **one file**, `<id>-spec.md` (for ticket 42, `42-spec.md`), in `.besman/specs/`
unless the project's rules name another place. It contains no code.

| The specification contains | It never contains |
|---|---|
| Purpose, scope with a reason per exclusion, definitions | New code, diffs, replacement snippets, proposed signatures |
| Requirements and attributes, `REQ-n` and `ATT-n` | Ordered edit steps, anchors, file-by-file instructions |
| Verification cases `VC-n` with their method, and traceability | Test method bodies, computed expected literals |
| Acceptance criteria `AC-n`, decisions with who took them, risks, limitations | A design or architecture proposal |

**Quoting existing code as evidence is allowed** — inline in backticks, to show what the system
does today. Prescribing new code is not, in any form, and no fenced code block appears at all: the
lint refuses them. The test: a statement that tells someone what to type is not a requirement; one
that states what must be true when the work is done is. No design document and no task list:
keeping the plan out keeps each requirement verifiable whatever implementation is chosen.

---

## 4. Document structure — ISO 29148 clause 9.6

    0. TL;DR                              four lines, for a person
    1. Introduction
       1.1 Purpose                        the detailed goal, for whoever implements it
       1.2 Scope (in scope / out of scope with a reason per item)
       1.3 Product overview (perspective, functions, user characteristics, limitations)
       1.4 Definitions
    2. References (production code, test code, tickets, commits)
    3. Requirements
       3.1 Functional requirements        REQ-n, "shall"
       3.2 Design constraints             externally imposed only
       3.3 Software system attributes     ATT-n
       3.4 Supporting information         analysis, no requirements
    4. Verification
       4.1 Approach
       4.2 Assessment of existing coverage
       4.3 Verification cases             VC-n
       4.4 Traceability
       4.5 Manual verification
       4.6 Acceptance criteria            AC-n
    5. Appendices
       5.1 Assumptions and dependencies   A-n
       5.2 Implementation order
       5.3 Rejected alternatives
       5.4 Risks
       5.5 Follow-ups                     adjacent problems, one line each

Identifiers are mandatory: `REQ-`, `ATT-`, `VC-`, `AC-`, `A-`, numbered from 1 without gaps.
Traceability is impossible without them.

**The structure is a superset, not a form.** Include the clauses the change needs and delete the
rest. An empty heading, or one carrying "None", "N/A" or "Nothing", costs a reader the same
attention as a real one — and the lint refuses it.

### Line shapes the lint reads

The lint rebuilds the document from these shapes, so keep them exact:

- the TL;DR is a heading `## TL;DR` (or `## 0. TL;DR`) followed by four lines starting
  `**Problem.**`, `**Cause.**`, `**Action.**`, `**Result.**`, in that order;
- each requirement is a list item starting `- **REQ-n**`, and it contains `shall` once;
- each attribute is a list item starting `- **ATT-n**`;
- each verification case is a list item starting `- **VC-n**` that names its method (`test`,
  `inspection`, `analysis` or `demonstration`) and the `REQ-n` or `ATT-n` it verifies;
- each acceptance criterion is a list item starting `- **AC-n**`;
- a citation is a code span `` `Repo/path/file.ext:line` `` or `` `Repo/path/file.ext:first-last` ``;
- the folded half starts at the first `<details>`;
- the document ends with the marker `<!-- besman:spec-document -->`.

### What the reader sees, and what is folded away

Left alone, requirements, verification cases and acceptance criteria end up a quarter of the text,
behind three quarters of scaffolding. So the document has two halves.

**Open, and budgeted at 8 000 characters** (everything before the first `<details>`):

    0. TL;DR              four lines
    3.1 Requirements      REQ-n
    4.3 Verification      VC-n
    4.4 Traceability
    4.6 Acceptance        AC-n
       Decisions taken    what was settled, by whom
       Open items         anything still unanswered

**Folded, in two layers.** An outer `<details>` titled "Supporting material" holds clauses 1.x,
3.2 and 5.x — specification content that did not fit the open half. Nested inside it, a second
`<details>` titled "Investigation evidence and run log" holds clauses 2 and 3.4 as citations,
`fact | Repo/path:line | VERIFIED/INFERRED/UNKNOWN`, one row each, not the paragraph that explained
them during the investigation, plus the run's notes: what it did not do, which limits applied. A
reader checking the scope does not scroll past the citation trail.

If the open half will not fit, the cause is almost always rationale grown into paragraphs; cut that
before cutting a requirement. The **whole** document must also be short enough to post as one
comment in the tracker (GitHub: 65 536 characters). One that will not fit is a ticket that covers
too much: decompose the ticket, do not split the comment.

### Do not restate the ticket

The ticket sits directly above the document. State only what it does **not** say: what the code
contradicts or completes, the requirements it implies, the decisions taken since. Point at it
rather than quoting it — except a claim the code contradicts, because the disagreement is the
finding.

### Rationale is one line

A requirement may carry one line of reasoning where the reason is not obvious, as an indented note
marked as not being a requirement. Not a paragraph, not a worked example.

### Risks, assumptions and rejected alternatives earn their place

Include one only if it changes something: a risk that produced a requirement or criterion, an
assumption a requirement rests on, an alternative someone actually proposed or the ticket left
open. Listing as "rejected" an option the ticket already ruled out shows it was not read. For most
changes the section is absent.

**References are inline.** Every requirement already cites `Repo/path:line`; a separate list goes
stale independently. Clause 2 survives only as the folded citation table.

### Clause 0 — the TL;DR

Every specification opens with it, and it is the one part written **for a person rather than for
an implementer**. Four labelled lines, in this order:

    ## TL;DR

    **Problem.**  What goes wrong today, and for whom.
    **Cause.**    Why it happens.
    **Action.**   What we are going to change.
    **Result.**   What will be true afterwards that is not true now.

Rules, strict because this is the only part most readers finish:

- **Simple English**, for a junior who joined this week. A sentence that needs a second reading is
  rewritten.
- **Names, not paraphrases.** No `REQ-3`, no `VC-7`, no class name, no file name or path — but the
  thing itself is named: the parameter `projectId`, the status Cancelled, the response `403`, the
  route, the amount. "One part of the web address" hides the one fact the reader needs; the lint
  warns when Problem and Cause carry no code span and no number. A code span over about forty
  characters is code, not a name.
- **Four lines, about eighty words, never more than 120.** Longer means two tickets.
- **No obligation.** It orients; anything that matters also appears as a `REQ`.
- **For a change or a feature, `Cause` means why the system cannot do this today.**
- **Write it last**, when you know what the document actually says.

### Clause 0 and clause 1.1 are different jobs

The TL;DR answers, for a person deciding whether this is the right work: is this the right problem,
and will this fix it? The Purpose (1.1) answers, for the implementer and the reviewer: what exactly
must become true, and where is the boundary? It is exact — names the rule, the owning component,
the entities and states, what the change deliberately does not try to achieve — and it is where an
implementer looks when a requirement can be satisfied two ways. Neither binds; neither may
contradict the other or carry a fact the other lacks. If the Purpose is a longer TL;DR, make it two
sentences — do not pad it.

### Verification methods

ISO 29148 recognises four. Label every `VC` with one; they are not interchangeable.

| Method | Use when | Evidence |
|---|---|---|
| `test` | An automated case can decide it | A passing suite |
| `inspection` | Reading the source or configuration decides it | A search result, a quoted file |
| `analysis` | Reasoning over the design decides it, with no execution | A written argument |
| `demonstration` | Observing the running system decides it | Manual steps and an observed outcome |

Do not label something `test` when nobody will run it automatically. A search for a symbol that
should no longer appear is `inspection`. A manual run on a shared environment is `demonstration`.

### Traceability

A table mapping every `REQ` and `ATT` to at least one `VC`, and every `VC` back to a requirement:
each row names both sides on one line. A hole in either direction is a missing requirement or a
pointless test — resolve it, do not ship it.

### Acceptance criteria are about the software, not about the paperwork

An `AC-n` states a property of the delivered change that a person or a command can decide **by
exercising the system**. Keep them few: one per behaviour a stakeholder would actually sign off.
Past about six for a single-rule change, the list has turned into a task breakdown.

Administrative obligations are not acceptance criteria: who was told, what was pasted into a
ticket, which follow-up tickets were raised, which tracker field was set, who a number is
attributed to, whether the specification was published. None can honestly fail, and criteria that
are never green stop being read, taking the real ones with them. Each has a home already:

| Obligation | Where it goes |
|---|---|
| Something still wrong after the work | Limitations, clause 1.3. Writing it down is how testers are told |
| An adjacent problem found on the way | Follow-ups, clause 5.5. One line with its citation |
| Who took a decision, and when | The decisions table |
| A tracker value a finding determined | Stated as a value to set, not as something to pass |
| Provenance — an account, a date, a run | Nowhere. It is not a requirement |

The test before writing any `AC-n`: **could a tester decide this by exercising the system?**

### Gherkin scenarios

For a **feature**, write the Given/When/Then scenarios here, consistent with the `AC-n` items:

- one scenario per criterion it illustrates, named after it ("AC-2: ...");
- plain lines, `Given` / `When` / `Then` / `And`, one step each — **never in a code fence**;
- real values — a real status, amount or role — not `X` and `Y`;
- `When` is one action; `Then` is an observable outcome, never an internal call;
- no obligation the requirements do not already state.

---

## 5. Verification policy

A verification case says **what must be observed**, not how to write the test. Writing the test is
the implementer's work, and specifying it here ties the requirement to one implementation.

1. **State the observable outcome**, in the terms of the requirement it verifies. "The cut-off for
   a Wednesday delivery with 24 hours' notice falls on Tuesday at 00:00 local time" is a
   verification case. A test method is not.
2. **Red first.** State which assertion must fail on the unmodified code. A case that already holds
   proves nothing, and saying so is what stops a tautological test being written.
3. **Adapt before adding.** Where the existing suite covers the area, the case belongs there.
4. **Do not compute expected literals**, nor write "update the expectations". State the rule that
   produces the value and the worked example found; the implementer does the arithmetic.
5. **Say what must be mocked**, per the project's testing standards. Absent a rule: external
   services, the database layer, queues, HTTP clients and secret stores in unit tests, and no test
   calls a real shared or production API.
6. **Name the coverage still missing** after the work, and whether that is acceptable.

Two failure modes deserve a requirement of their own when the investigation found them: a test
that mocks the component under test verifies wiring rather than behaviour, and test data outside
the range a validator allows describes an impossible situation.

---

## 6. Requirements the standards demand

The half nobody writes by hand — but a **trigger list, not a checklist to complete**. Most tickets
trip two or three rows. Skip, silently, every row whose trigger the investigation did not find.

- **Prefer amending an existing requirement to adding one.** If the ticket's requirement becomes
  correct by widening it — "at every site that applies the rule", "including records already
  stored" — widen it. A second `REQ` for the same obligation splits traceability in half.
- **Past about five added requirements, stop and re-read them.** Keep the ones whose absence would
  let someone ship something wrong.

| Area | Add a requirement when | The spec must answer |
|---|---|---|
| Blast radius | The work changes when or how a field is set, or a state transition | Is the rule applied at every site the sweep found, not only the one being edited? |
| Known traps | The investigation matched a trap the project documents | Which trap, and what stops it recurring? |
| One owner | The rule is defined in more than one place | Does the rule end with one owner, or is the duplication accepted with a reason? |
| Over-building | The proposal adds a seam, plugin point or configuration surface | Does a second implementation exist or is one committed? If not, drop it |
| Testing | Always | What must be verified, at which level, and what must be mocked? |
| Documentation | The work alters behaviour a project document describes | Is that document updated in the same change? |
| Authorisation | The work touches an endpoint, a permission or a role | Who may call each touched route or action, and what does everyone else get? |
| Secrets and personal data | The work handles a secret or personal data | Is no secret in code or config, and no personal data in a URL or a log? |
| Stored data | The change is retroactive, or changes the shape of stored records | Which existing records are affected, and is a migration needed — or are they left, with the consequence for testers stated? |
| Compatibility | The work spans deployables or repositories, or changes an API, event or file contract | Is the intermediate state between the deployments safe, and do old clients keep working? |
| Error handling | The rule can fail on bad input or a failing dependency | What does the caller or user see, and is anything left half done? |
| Idempotency and retries | The work runs from a queue, a webhook, a scheduled job or a retried request | Does running it twice produce the same result as running it once? |
| Concurrency | Two writers can touch the same record | Is a lost update prevented, and how is the conflict reported? |
| Observability | A failure of this rule would be silent | Where does it become visible — an audit record, a log, a metric — and where does a tester look? |
| Boundaries | Always | One requirement per boundary case the investigation listed that the ticket does not cover |
| Backward behaviour | The change alters something users rely on | What must **not** change, stated as an obligation |
| Project conventions | The project's rules name branch, commit or review conventions | Cite them; do not invent them |

Each added requirement carries its source: "REQ-7 … (blast radius: two more sites apply the rule)"
is auditable; the same sentence without the source reads as an opinion.

**Requirements satisfied without code.** When a component becomes correct because its input
becomes correct, state it as a requirement and record that it needs no change there. This stops an
implementer editing files that are already right.

---

## 7. What the specification does not decide

The specification stops at the boundary of behaviour. It does not name files to edit, order steps,
give commands or prohibit particular edits — that is a plan, a separate job. It **does** owe the
implementer a scope clause precise enough that widening the change is visibly out of scope: every
site the rule applies at, everything not being solved and why, every limitation still true after.

Where a finding determines a tracker attribute (priority, affected users, risk), state the value so
it can be set. **Never state an estimate** — the team estimates, an analysis does not.

---

## 8. Business decisions belong to the human

**A fact is looked up. A decision is asked.** This rule outranks convenience, speed and
confidence.

Anything determinable from the code, the configuration, the tests, the history or the ticket is a
**fact**. Find it yourself; asking wastes the stakeholder's attention and teaches them to skim your
questions. A data fact that one read-only query would settle is not a question for a person either:
record it as `UNKNOWN` with the query that would settle it.

Anything that changes what a user experiences, what the business promises, what something costs or
what risk is accepted is a **business decision**. No agent takes it — not by choosing, not by
"recommending and proceeding", not by leaving it to whoever writes the code. Silent resolution is
how a system ends up behaving in a way nobody chose.

**Before asking, analyse the code.** Establish which options are cheap and which expensive, and
find the simplest effective one — often an existing setting, a rule enforced elsewhere, a default
that can change. A question that offers a one-hour option next to a three-week one without saying
so is not fair.

### What a question is

A question reaches a person only when **the ticket, the code and the documentation together leave
it open, and the answer changes a requirement**. Everything else is a fact (looked up), a technical
choice (left to the implementer), or an assumption (recorded as `A-n`, marked `INFERRED`). Each
question carries:

- **Three anchors**: the sentence of the ticket it refines, quoted; what the code does today
  (`Repo/path:line`); what the docs say, or `silent`; and one line on why that still leaves it open.
- **A type**: `business` (what we promise, show or charge), `flow` (what happens at which step,
  for whom) or `constraint` (dates, rules, limits). A question that fits none is technical and is
  not asked.
- **A status**: `BLOCKING` when its answer would change the requirements or the approach, else
  `DEFERRABLE`. Blocking questions are answered before the document is written; never present a
  specification as complete while one is open.
- **Options with consequences, and a recommendation with its reason.** Nobody chooses blind.
- **No dependent questions.** "If A, then also…" is a condition on the parent, not a second
  question.

**At most four `BLOCKING`, six in all.** Past that, keep the ones whose wrong answer costs most
and carry the rest as assumptions, each with the answer you would have given and why. The author
sees them and can object.

### How to ask

- **In business language.** No class names, file paths or framework terms; the project's domain
  names (entities, statuses, roles) are welcome. Could someone who knows the business but never
  opened the code answer it?
- **With real numbers.** "Should a branch with 24 hours' notice stop accepting a Wednesday
  delivery at 1am on Tuesday?" is answerable. "Time-based or business-hours-based?" is not.
- **One question at a time** when interactive, in dependency order; **one decision per question**,
  each option with who it affects and what it costs to reverse if wrong.

Ask now everything the implementer would otherwise have to ask: the wording shown to a user, the
exact rule at each boundary, what happens to data that already exists, which behaviour must not
change, one measurable acceptance criterion per requirement.

**An answer to a different question is not an answer.** Say which question is still open, restate
it, and wait.

### Walk every branch, then confirm

The interview is a decision tree: an answer can close three later questions or open a new branch.
Cover every branch, but press any one question once, when the answer is vague or does not survive
the evidence; then take the second answer and move on.

**Then confirm before writing.** State back in a few lines the problem, what changes, what
deliberately does not, and every decision with who took it. Ask whether that is right, and wait. If
the person corrects it, fold the correction in and confirm again. Silence is not agreement.

---

## 9. The premise check

ISO 29148 separates stakeholder (9.4), system (9.5) and software requirements (9.6, this document).
A software specification on an unestablished need is internally perfect and possibly about the
wrong thing. A ticket claims that something is wrong, that it matters, and often that a particular
change is the answer; all three can be false. So challenge it — **after a fast read of the code,
never before**, bringing what you found. These are questions like any other, asked only when the
ticket leaves them open.

| # | To establish | The question, in business language |
|---|---|---|
| 1 | The problem | What goes wrong today, for whom, and how often? |
| 2 | Cost of doing nothing | What does that cost? If "nothing measurable", say so |
| 3 | Affected parties | Who is affected, and who else notices if this changes? |
| 4 | Desired outcome | What should happen instead — as an outcome, not a feature? |
| 5 | Measure of success | How will you know it worked? What would you look at in a month? |
| 6 | Boundaries | What must **not** change? What is explicitly not being solved? |
| 7 | Constraints | Any date, budget, regulation or commitment that limits the options? |
| 8 | Existing workaround | What do people do today instead? Why is that not enough? |

For a **feature**, and a **change** whose outcome is not stated plainly, all eight. For a **bug**
and a plainly stated **change**, rows 1, 2, 4 and 6; the rest only when still open.

Three challenges beyond the table: **is the stated solution the need, or one solution to it?**
(when the ticket names a change — "add a button" — rather than a problem); **is there a cheaper
option already in the system?** (always, after looking); **what happens if we do nothing?**
(always — "nothing measurable" is a finding, not rudeness).

- **Ask about the measure of success even when it feels awkward.** A need with no measure cannot
  become a verifiable requirement; if nobody can answer, that is the finding.
- **Never conclude the ticket is wrong yourself.** Put the evidence in front of the person.
- **The human can end it at any point.** "That's enough, carry on" ends it. Record every open point
  as `A-n`, marked `INFERRED`, with the answer you would have given and that it was not confirmed,
  and say in the report which of the eight were not established. An assumption written down is
  fine; one quietly promoted to a finding is the failure this skill exists to prevent.
- **Record answers faithfully** — in Problem and Result, clause 1.1 and, for a feature, clause 1.3,
  with who gave each. Someone who said "quite often" did not say "weekly".

---

## 10. Domain vocabulary and language

Use the project's own terms, from its glossary or domain model. Keep an identifier in its original
form when naming a class, table, field or route; translate only running prose. Entities with
similar names are not interchangeable — when unsure of a term, ask rather than guess.

Default language: technical English at B2 level, unless `.besman/rules.md` names another. Short
sentences, no idioms, no filler. No live mention of a bot in front of a command: write `/spec`,
never an `@`-mention. The last line is `<!-- besman:spec-document -->`.
