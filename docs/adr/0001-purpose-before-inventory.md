# ADR-0001: Fix the primary use case before taking any inventory

- **Status:** Accepted
- **Date:** 2026-08-02

## Context

The obvious first move when assessing an estate for agentic development tooling
is to inventory it: what languages, what frameworks, what runtimes, what state
the documentation is in, which model to use. That inventory describes the
*estate*. It does not describe the *task*, and the task is what determines the
size of the work.

Consider four things somebody might mean by "we want agentic tooling for these
applications":

- **Assisted maintenance.** An agent works inside the existing change flow,
  proposing small changes that a human reviews. The binding requirement is a
  fast, trustworthy signal on every proposal, because the value is the number of
  changes that get through the loop per unit of human attention.
- **Characterisation test generation.** The agent's output *is* the test suite.
  Existing tests barely matter as an input; what matters is whether the code can
  be executed at all, and whether the behaviour being pinned down is observable
  from outside.
- **Modernisation or migration.** A large, mostly-mechanical transformation with
  a verifiable end state. Here the oracle question is total: without a way to
  prove behaviour is unchanged, the transformation cannot be accepted, and the
  test-building effort routinely exceeds the transformation itself.
- **Documentation and comprehension.** The agent reads and writes prose. It
  needs no build and no tests. This is by a wide margin the cheapest of the four
  and it is also the one with the least defensible business case, which is why
  it is often quietly substituted for one of the others.

These are the same repositories and four different projects. The scanner in this
repository reports identical facts for all four; what changes is which facts are
load-bearing. For documentation, the buildability column is irrelevant. For
modernisation, a repository at buildability level 1 is not a minor finding, it is
the whole first phase.

## Decision

Establish the primary use case first, in writing, before collecting a single
fact about the estate. Where more than one use case is in scope, rank them, and
assess against the top one.

Concretely, this ordering is built into the artefacts here:

- The [intake questionnaire](../intake-questionnaire.md) opens with purpose. Its
  first section is unconditional and everything after it is conditioned on the
  answer.
- The scanner does not produce a readiness verdict. It produces facts and
  per-dimension levels, because "ready" is only defined relative to a use case
  that the tool has not been told.
- The rubric refuses to compute a composite score. A total would have to weight
  the dimensions against each other, and the correct weights are a function of
  the use case.

## Consequences

- An assessment that skips this step produces a number with no denominator.
  Whatever effort figure comes out of it is a guess wearing evidence as a
  costume, and it will be defended later on the strength of the evidence rather
  than the guess.
- Some questions become unnecessary rather than merely lower priority. If the
  use case is documentation generation, test coverage is not a lower-priority
  question — it is not a question. Asking it anyway lengthens the assessment and
  trains the people answering to treat the whole exercise as a form-filling
  exercise.
- The use case will be contested, and that is the point. The disagreement is
  real and surfacing it early is cheaper than discovering it against a delivered
  artefact. A stakeholder who says "assisted maintenance" and a stakeholder who
  says "clear the backlog of technical debt" have not agreed on anything.
- **Cost: it puts a judgement call at the front, and judgement calls stall.** An
  assessment can sit waiting for an answer nobody feels able to give. The
  mitigation is to state an assumed use case, write it at the top of the output,
  and proceed — an explicit assumption is falsifiable, which a silent one is not.
- The scanner can and should run before this is settled, since the facts it
  collects are use-case independent. What must not happen before it is settled is
  interpretation.

## Alternatives considered

**Assess against all plausible use cases and produce a range.** Rejected: the
range spans an order of magnitude between "generate documentation" and "migrate
with proof of behavioural equivalence", so it carries no information. A range
that wide is a refusal to answer, formatted as an answer.

**Assess the estate generically and let the use case be chosen later, informed by
the findings.** Superficially attractive — the facts are use-case independent, so
why not gather them first? The problem is that the facts are not what an
assessment produces. It produces an interpretation, and interpretation cannot be
deferred without deferring the assessment. This ADR's position is the compromise:
gather facts whenever you like, interpret only against a named purpose.

**Infer the use case from the estate.** Rejected. It is a business decision about
where value is expected, and nothing in a repository knows the answer. A scanner
that guessed would be inventing the most important input to its own output.
