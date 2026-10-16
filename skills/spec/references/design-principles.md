# Design principles

The project's own rules come first: `.besman/rules.md`, then `.besman/standards.md` and
`.besman/constraints.md` (created by `/besman:project`). Where they and this file disagree, the
project wins.

Binding on every specification that adds or changes behaviour. Read together with `standards.md`.

The goal is code that can grow without being rewritten — **and** without being over-built for
growth that never comes. Both failures cost the same; only the second one feels responsible while
you are doing it.

---

## 1. Know what the system actually is

Establish the shape of the system from `.besman/constraints.md` and the code: one deployable or
many, which parts deploy independently, how they talk (in-process calls, a database, a queue,
HTTP), which external systems sit outside. The properties below mean different things in a modular
monolith than in a set of services. **Do not specify a network boundary where a module boundary is
the right answer**, nor an in-process call across two things that deploy separately.

---

## 2. The three properties

### 2.1 Isolation — one rule, one owner

A business rule must have exactly one definition. Everything else reads it.

The recurring failure is the opposite: the same status set, allowed-state list or queue definition
**copied** into several components, which then drift apart. It is invisible until the copies
disagree in production, usually on a path that matters.

A specification satisfies isolation when it can answer: *if this rule changes, how many files must
change?* If more than one, say why, or move the rule.

Isolation also means a change should not require knowledge of unrelated modules. Adding a payment
provider should not require understanding how notifications are sent.

### 2.2 Extensibility — a seam where variation is real

Put the seam where the system genuinely varies, not where it might one day vary.

Systems vary along axes you can name — payment provider, customer type, delivery method,
notification channel. Find the real ones by counting implementations, not by imagining them.

A seam is justified when **at least one** holds:

- a second implementation exists;
- a second is committed — named, dated, or already agreed with a customer;
- retrofitting the seam later would be expensive because it crosses a stored data shape, an
  external contract, or a money path.

A seam is **not** justified by "we might want to swap this out". That sentence has built more dead
abstraction than any other in software.

### 2.3 Scalability — know which dimension actually grows

Ask which number grows, and what breaks first when it does. The answers are usually concrete:

| Dimension | What breaks first | Where to look |
|---|---|---|
| Records per partition, table or key | Partition limits, hot keys, full scans | Key and index choice; the project's data model |
| Items per scheduled run | A fixed-timeout batch silently starves its later steps | Batch size and ordering |
| Providers or variants | Every `if provider ==` site must be edited | Number of call sites |
| Concurrent writers | Lost updates without an optimistic-concurrency guard | Version or etag checks on write |

In a fixed-timeout batch job, **ordering is a correctness concern**: a slow early step starves
everything after it, and nothing fails loudly.

Scalability rarely means "add servers". Find the number first.

---

## 3. The counterweight — do not over-engineer

Every abstraction costs: a reader must hold one more indirection in their head, and a debugger must
step through it. Pay that cost only when it buys something.

**Right-size with the rule of two.** The first implementation is written concretely. The second
creates the seam, because now the variation is a fact rather than a forecast. The third proves the
seam was in the right place.

**Exception, and it matters:** create the seam at the first implementation when retrofitting would
be expensive — anything touching a stored data shape, an external contract, or money. Changing a
persisted record shape after the fact is a migration; changing an internal method signature is
not.

**Things that are not extensibility:**

- a configuration flag for behaviour nobody has asked to configure
- an interface with exactly one implementation and no second in sight
- a generic parameter that is always the same type
- an event that nothing subscribes to
- a plugin mechanism for a set that changes once a year

**Fix the cause, not the symptom.** A guard added where the wrong value shows up, while the place
that produces it stays wrong, is a second copy of the rule waiting to drift. Specify the
correction where the value is produced; a downstream component that becomes correct because its
input becomes correct needs no change, and the specification says so.

**Team constraints bound the design**: simplicity first, minimal blast radius, pull requests within
the size limit in `.besman/rules.md` (about 200 lines if it names none). A design that cannot be
delivered in reviewable pieces is wrong, however elegant.

---

## 4. Worked example — a seam half done

The shape below recurs in almost every codebase that integrates more than one external provider.

### What is right

A provider-agnostic service interface exists, with one implementation per provider. The seam sits
at the service layer, and it is justified: two providers are live.

### What is not

The domain entity carries one method **per provider, per operation** — "is provider A enabled",
"is provider B enabled", "add provider A account", "add provider B account", and the same for
enable and disable. The stored value object names each provider as a fixed field rather than
holding a collection keyed by provider.

So a third provider costs two new fields, six new methods, and an edit at every "is provider X
enabled" call site — and those call sites gate real behaviour, such as whether an account can be
activated at all.

### What the principle asks for

Keep the service interface. At the domain layer, replace the per-provider method families with one
operation taking the provider as a parameter, and hold providers in a keyed collection rather than
named fields. Adding a provider then touches configuration and one implementation, not the entity.

### What the principle does not ask for

No plugin loader. No dynamic registration by reflection. No provider-agnostic rewrite of a webhook
handler that parses one provider's specific event shapes — that code is correctly
provider-specific. The seam belongs where the *domain* is provider-agnostic, not where the
*integration* is inherently provider-specific.

### The migration caveat

The value object is persisted. Changing named fields to a collection changes the stored shape, so
it is a data migration, not a refactor. That is exactly the "expensive to retrofit" case in
section 3 — which is why the seam should have been created when the second provider arrived, and
why a specification proposing it now must treat it as a migration with its own risk and rollback.

---

## 5. Questions a specification must answer

Answer these while writing the specification. An answer that changes what ships becomes a
requirement (see the trigger list in `standards.md` section 6); the rest is one line in the
supporting material. Each answer is one or two sentences; a long answer means the design is not
settled.

**Isolation**

1. Which single place owns the rule this change introduces or modifies?
2. If it changes again, how many files must change? If more than one, why?
3. Does this duplicate a list, status set or constant that already exists elsewhere?

**Extensibility**

4. Along which axis is variation real *today*? Name the second implementation, or state there is
   none.
5. If a seam is proposed, which of the three justifications in section 2.2 applies?
6. If no seam is proposed, what would it cost to add one later? If the answer involves stored data,
   an external contract or money, reconsider.

**Scalability**

7. Which number grows, and what breaks first when it does?
8. Does this run inside a fixed-timeout batch? If so, where does it sit in the ordering, and what
   does it starve if it runs long?
9. Are concurrent writers possible? Is the write guarded against lost updates?

**Right-sizing**

10. What is the simplest version that satisfies the requirements? If the proposal is not that, what
    specifically justifies the difference?
11. Does it fix the cause, or guard against a symptom downstream?
12. Can it be delivered in reviewable pull requests within the project's size limit? If not, how is
    it split?

---

## 6. How to report a violation

If the simplest solution to a ticket would entrench a duplication or block a known-coming
variation, say so **as a finding with a cost**, not as a preference:

> Doing X the direct way adds a fourth copy of the account-enabled check. A third payment provider
> is on the roadmap for next quarter, at which point all four must change together. Creating the
> seam now costs about a day and one data migration; deferring it costs that day plus the risk of
> the four copies drifting.

Then let the human decide. Design ambition is a business decision when it changes cost or
timeline — section 8 of `standards.md` applies in full.
