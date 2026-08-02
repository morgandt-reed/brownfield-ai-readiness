# Intake questionnaire

Questions an assessor asks before estimating anything about agentic development
tooling over an existing estate.

**How to read this.** Questions marked **(★)** are unconditional: without them
there is no assessment, only a guess. The rest narrow a range that the starred
questions establish. Asking all of them at once is a mistake — it converts a
short assessment into a long one and trains everybody answering to treat the
exercise as paperwork. Ask the starred ones, record explicit assumptions for the
rest, and come back to the ones the answers make relevant.

**Where the scanner helps.** Questions marked *[scanner]* have a partial answer
in `brownfield-scan` output. Partial, because the scanner reads files and these
questions are about behaviour. Where the two disagree, the person is right and
the scanner has found something interesting.

Section 1 is answered first and separately. Everything after it is conditioned on
the answer — see [ADR-0001](adr/0001-purpose-before-inventory.md).

---

## 1. Purpose

- **(★) What is the primary use case?** Assisted maintenance inside the existing
  change flow; characterisation test generation; modernisation or migration;
  documentation and comprehension; something else. One primary. If several, rank
  them.
- **(★) What outcome would count as success, and how would you know?** A number,
  a date, and a way to measure it. If none exists, say so — an unfalsifiable
  objective is a finding, not a blocker.
- What is the baseline today for whatever that measure is? If it has not been
  measured before anything changes, it cannot be measured afterwards either.
- What has already been tried, and what came of it?
- Who decided this was worth doing, and what were they comparing it against?

## 2. The estate and its archetypes

- **(★) How many technology families are there, really?** Not how many
  applications. Language, build system and framework, grouped. *[scanner]*
- The inventory itself: per application, language, framework, major version,
  runtime. *[scanner]*
- Approximate size and business criticality per application. Criticality is not
  in the repository and changes where the work should start.
- Dependencies between applications, and on systems outside the estate —
  mainframes, third-party APIs, message brokers, shared databases.
- Which applications are in scope, and who decided the boundary?

## 3. Source control and build

- **(★) Does each application build reproducibly from a clean checkout?** Not
  "is there a build" — has anyone done it recently, on a machine that was not
  already set up? *[scanner, presence only]*
- What is the source control system; one repository per application or several;
  how many live branches. *[scanner, partially]*
- Dependency and artefact management: internal registry or mirror, credentials
  needed, whether the build reaches the public internet. *[scanner, partially]*
- How long does a build take? A forty-minute build changes what an agent loop can
  do without changing any signal a scanner sees.
- When was each application last released, and how often does it change?

## 4. Testing and test data

- **(★) What automated test suites exist, per archetype, and do they pass
  today?** *[scanner, presence only]*
- Which kinds — unit, integration, end-to-end — and how reliable are they? Which
  are known to be flaky, and what is the local convention for dealing with that?
- Is coverage measured, and what is it? *[scanner detects instrumentation, never
  a figure]*
- Do the tests assert behaviour, or do they execute code and assert nothing
  meaningful? A high-coverage suite with no real assertions is a worse oracle
  than none, because it is trusted.
- Do the parts of the system that carry business risk have tests?
- **Is test data available, and does it contain personal data?** If it does,
  anonymisation is a workstream, and it may gate the whole loop rather than one
  application.
- Which quality tools are already in use and does anyone act on their output?
  *[scanner detects configuration]*

## 5. Environments

- **(★) Is there a non-production environment where the code can be run and
  validated?** If nothing can be executed outside production, there is no
  validation loop, and that constrains the design before anything else.
- Can each application be started in isolation — containers, infrastructure as
  code, a documented local setup?
- What CI/CD exists, how automated is it, and who operates it? *[scanner detects
  configuration files]*
- **Are the gates enforced?** Branch protection, required checks, who can
  override, and how often they do. This is not in the checkout.

## 6. Toolchain and observability

- Which editors and IDEs are standard, and how much variation is tolerated?
- Ticketing and change-management systems; the current pull-request and review
  flow, and who has authority to change it.
- Existing observability — application performance monitoring, logs, traces.
- Can agent activity be instrumented: action traces, token consumption, and what
  each gate decided? In a regulated setting this is usually an audit requirement
  rather than an operational nicety.

## 7. Model and infrastructure envelope

- **(★) May source code leave the perimeter?** See section 8; this is the
  question the deployment model hangs on and it is asked here too because it also
  determines which providers are even candidates.
- Which models are permitted or preferred, and are there contractual constraints
  on provider choice?
- What token spend is acceptable, and what rate limits should be assumed?
- If inference must be internal, what hardware exists or is budgeted?
- Is there an existing gateway or proxy that model traffic must route through?

## 8. Security — ask about all three, and rank them

The word means three different things. See
[ADR-0004](adr/0004-three-meanings-of-security.md).

- **(★) Rank these three by importance, and name who signs off on each:**
  1. **Quality guardrails** — the tooling must not break what works.
  2. **Application security** — it must not introduce vulnerabilities, commit
     secrets, or pull in compromised dependencies.
  3. **Data and IP governance** — code must not leave the perimeter; the model
     must not train on it.
- **(★) For concern 3, name the specific obligation.** Which regulation, which
  contract, which clause, which data. An unnamed constraint should be treated as
  absent — and so should an unnamed permission.
- What are the retention and logging requirements on prompts and completions?
- Which security tools are integrated into the pipeline today, and do they block
  or report? *[scanner detects configuration only]*
- Is there a written policy naming permitted destinations for source code, and is
  anything technical enforcing it?

## 9. Governance and compliance

- What regulatory framework applies, and what does it require in the way of audit
  trail and traceability?
- How many human approval points are mandated, by whom, and at what stage?
- Does policy-as-code exist, or would it have to be built?
- What has to be demonstrable to an auditor, and in what form? "We have a
  process" and "here is the record for change 4471" are different obligations.

## 10. Team, adoption and change volume

- **(★) Who owns this after it is built, and do they have time allocated?** A
  sponsor is not an owner. An owner can decline other work to do this.
- **(★) How many developers, and how comfortable are they with the practices this
  depends on** — continuous integration, automated testing, code review?
- What prior experience is there with assisted development, and what came of it?
- What is the appetite for changing the review workflow, and who has to agree?
- Change volume per application: how many changes per iteration, and how large?
  This sizes the return, not the build.
- Is the pilot team representative, or is it the enthusiastic one? Both are
  valid choices and they measure different things.

---

## Using the answers

**Answer section 1 first and write it down.** Every question after it is
interpreted against the purpose, and the same estate looks entirely different
under a different one.

**Run the scanner early.** The facts it collects are use-case independent, so it
can run before the purpose is settled. What must not happen before then is
interpretation.

**Record assumptions explicitly where a question is unanswered.** An explicit
assumption can be challenged and corrected. A silent one becomes a surprise, and
it surfaces at the point where it is most expensive.

**Do not treat unanswered as bad.** The rubric reports unassessed dimensions as
unscored rather than as level 0, for the same reason: an assessment that improves
when a question goes unasked is measuring the assessor, not the estate.
