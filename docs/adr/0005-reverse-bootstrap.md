# ADR-0005: Adopt tooling into existing repositories by reverse bootstrap

- **Status:** Accepted
- **Date:** 2026-08-02

## Context

Tooling for agentic development is almost always designed against a greenfield
flow: a template generates a new repository with the configuration, the gates and
the agent instructions already in place. That flow does not exist for a codebase
that is already running in production, and "adopt the tooling" is exactly what a
brownfield estate is being asked to do.

The naive move is to apply the template to the existing repository. It fails
immediately: the template assumes a directory layout the repository does not
have, a build the repository does not use, and gates the repository cannot
currently pass. What gets produced is a large change touching application code,
proposed by tooling, on a system the team is accountable for. It does not get
merged, and the attempt costs the tooling its credibility with the one team it
most needed.

The estate this repository ships as fixtures illustrates why a single template
cannot work. Two repositories in the same archetype sit at buildability levels 3
and 1; three of the eight have no CI configuration at all; one has an inferable
test command and no tests. Any configuration that assumes a starting state is
wrong for most of them.

## Decision

Adopt in the reverse direction: analyse the repository as it is, then add only
what fits, in three stages.

**Stage 1 — Analyse and plan.** Scan the repository, and produce a written
adoption plan naming three things separately:

- What can be added without touching application code.
- What changes to application code would be needed for full conformance, and what
  each is worth.
- **Residual debt**: what will remain non-conformant, and the consequence of
  leaving it. This item is the one that gets dropped and the one that matters.
  An adoption plan without an explicit residual-debt section is a plan that has
  quietly promised full conformance.

**Stage 2 — The bootstrap change.** One reviewable change that adds
configuration, agent instructions, a pinned version of the tooling and the gates,
and **touches no application code**. It is reviewable in one sitting; nothing in
it can break the running system, because none of it executes in the running
system. The gates it adds are the ones the repository can already pass, plus any
that are configured to report rather than block. A gate introduced in a blocking
state that the repository cannot pass makes the bootstrap change itself unmergeable.

**Stage 3 — Incremental conformance, optional and separate.** Everything that
does need application changes, one change at a time, each justified on its own
merits and each declinable. A repository that stops after stage 2 has still
gained something real.

## Why the boundary at stage 2 is the whole design

The bootstrap change is reviewable precisely because a reviewer can verify the
claim "this touches no application code" by looking at the file list. That is a
much cheaper thing to check than "this refactoring is behaviour-preserving", and
it is what makes the change mergeable by a team that has no reason yet to trust
the tooling.

Collapsing stages 2 and 3 to save a review cycle destroys that property. The
combined change is one where the file list no longer answers the question, and it
will be reviewed at the speed of the application changes inside it — which is to
say, eventually.

## Consequences

- **Expect weeks, not minutes.** Stage 1 requires reading the repository and
  talking to the team that owns it. Stage 2 is a change that a busy team has to
  review. Stage 3 is ordinary engineering work with ordinary engineering
  timescales. Tooling that presents adoption as a button produces stage 2 and
  calls the job done, leaving the residual debt undocumented.
- This is a distinct workstream from building the tooling, and it repeats per
  repository — amortised across an archetype, which is
  [ADR-0003](0003-archetypes-not-applications.md)'s point. It belongs in a plan
  as a line of its own.
- Where an estate is fragmented, stage 1 dominates, because the analysis cannot
  be reused across repositories that share nothing.
- The scanner supports stage 1 and no further. It produces the facts a plan is
  written from; it does not write the plan, and it does not open the change.
  Generating a bootstrap change would mean asserting the residual debt is empty,
  which is exactly the claim a human has to make and be accountable for.
- **Cost: three stages is more process than one, and the third stage frequently
  never happens.** That is an acceptable failure mode — a repository stuck after
  stage 2 has gates and configuration it did not have — but it should be named
  rather than discovered. If stage 3 is where the value was, stopping at stage 2
  is a project that delivered its scaffolding.
- Upgrades follow the same shape. When the tooling version moves, the repository
  gets a new stage-2 change: regenerate the managed configuration, diff it
  against what is committed, propose the difference. Anything a team wrote by
  hand is outside the managed region and is not touched.

## Alternatives considered

**Apply the template and let teams resolve the conflicts.** Rejected. It converts
a one-time central cost into a recurring per-team cost, and the teams paying it
did not choose the tooling.

**Require conformance before adoption — remediate the repository first, then
onboard.** This produces the cleanest end state and asks for the entire
investment before any of the value. In practice it means nothing is onboarded
until everything is remediated, and remediation without a working example of the
benefit is difficult to fund.

**Generate the bootstrap change automatically from the scan.** Attractive, and
the reason it is not here: the residual-debt section is the point of stage 1, and
it is a judgement about what the repository can live without. A generated change
either omits it or invents it. The scan feeding a human who writes the plan is
the correct division of labour, and it is a smaller claim than the one an
automated pipeline would be making.
