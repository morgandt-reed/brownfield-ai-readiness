# ADR-0004: Disambiguate "security" into three concerns before assessing it

- **Status:** Accepted
- **Date:** 2026-08-02

## Context

"We want developers to be able to use AI safely" is a requirement that everyone
in the room agrees with and nobody understands the same way. It contains at least
three distinct concerns, with different controls, different owners, different
costs, and — critically — different consequences for the deployment model.

**1. Quality guardrails: the agent must not break what works.** The risk is
regression. The controls are tests, builds, static analysis, code review and the
gates that enforce them. The owner is engineering. This is the concern that
[ADR-0002](0002-testability-is-the-constraint.md) is entirely about, and it is
the one most people mean.

**2. Application security: the agent must not introduce vulnerabilities.**
Injected flaws, hard-coded secrets, a dependency added because it had the right
name, an insecure default reproduced from a training set. The controls are SAST,
secret scanning, software composition analysis and supply-chain policy, wired
into the loop rather than run monthly against a report. The owner is usually a
security function that is not in the room when the tooling is scoped.

**3. Data and IP governance: the code must not leave the perimeter.** Whether
source may be sent to a third-party inference endpoint at all; whether it may be
retained or trained on; what is logged and where the logs go; what a regulator or
a customer contract permits. The owner is legal, compliance or a data protection
office. The controls are contractual and architectural, not code-level.

The three do not trade off against one another and they do not sum. Concern 3 is
a gate on the entire design: if source code may not leave a defined boundary, the
set of viable deployment models collapses before anything else is decided, and
everything in concerns 1 and 2 gets designed inside what remains. Discovering it
late invalidates a design rather than adjusting it.

## Decision

Treat the three as separate dimensions throughout: in the questionnaire, in the
rubric, and in what the scanner claims to detect.

- The [intake questionnaire](../intake-questionnaire.md) asks for the three to be
  named and ranked, as an unconditional question, and asks explicitly who would
  sign off on each. A concern with no named owner is not a requirement, it is an
  assumption.
- The rubric splits them. **Guardrail coverage** is one dimension covering
  concerns 1 and 2, because both leave configuration in the repository. **Data
  and IP governance constraint** is a separate dimension marked as having *no
  machine evidence at all*.
- The scanner detects what is detectable and says so: CI configuration by system,
  whether it references running tests, and static-analysis, SAST, SCA and
  dependency-update tooling present by filename.

## What the scanner cannot see, stated as such

**Whether a gate is enforced.** Branch protection is a server-side setting. A
repository can contain an immaculate pipeline that nothing requires to pass, and
the checkout looks identical either way.

**Whether a failing gate blocks a merge or is routinely overridden**, and by
whom. This is the difference between a control and a decoration, and it is a
question about behaviour.

**Whether the security tooling is in the pull-request loop** or runs nightly
against a dashboard nobody opens. A configuration file is present in both cases.

**Anything at all about concern 3.** There is no file that says where this source
code is permitted to go. The rubric's level definitions for data governance run
from "nobody has been asked" through "written policy naming permitted
destinations" to "a technical control makes the prohibited path unavailable" —
and every one of them is reached by asking a person.

## Consequences

- The rubric contains a dimension the scanner will never score. That is
  deliberate. Dropping it because it is inconvenient to automate would remove the
  concern most likely to stop the programme from the artefact people read.
- An unscored dimension is reported as unscored, never as level 0. Treating an
  unasked question as a bad answer would let an assessment improve by declining
  to ask.
- The three concerns should be ranked, not weighted equally, because the ranking
  changes the design. An estate where concern 3 dominates needs an architecture
  conversation before a tooling conversation.
- **An unnamed constraint should be treated as an absent one.** "We are
  regulated, so nothing can leave" is not a constraint until somebody names the
  obligation — which regulation, which clause, which data. Providers publish
  regional processing options, data-handling commitments and certifications that
  satisfy a great many requirements; the number of situations where an internal
  deployment is genuinely *required* is smaller than the number where it is
  *preferred*, and the two get conflated early and expensively. The converse is
  equally true: an unnamed permission is also absent, and "someone said it was
  fine" is not a finding.
- **Cost: this makes the intake conversation longer and involves people who did
  not expect to be involved.** A security or data-governance owner brought in
  after a design is chosen either rubber-stamps it or reopens it, and only one of
  those is a real review.

## Alternatives considered

**Fold all three into one "security readiness" score.** Rejected. It would
average a repository-level engineering property together with a legal constraint
that is binary and gates the whole design, and the total would be highest for
whichever of the three happened to have the most files.

**Leave data governance out of the rubric on the grounds that a scanner cannot
assess it.** Rejected for the reason above: the rubric is the assessment method,
and the scanner implements the part of it that is mechanical. Letting the tool's
reach define the method's scope inverts the relationship.

**Detect secrets committed in the repositories being scanned.** Tempting, and
declined. Doing it properly means entropy analysis and pattern matching over full
file contents with a real false-positive rate, which is a different tool that
already exists in better versions. Doing it badly produces a list of findings
that are mostly wrong, attached to an assessment that then inherits their
credibility.
