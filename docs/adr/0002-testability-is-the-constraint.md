# ADR-0002: Testability and buildability are the constraint, not documentation

- **Status:** Accepted
- **Date:** 2026-08-02

## Context

Assessments of legacy estates conventionally lead with documentation quality and
lifecycle maturity: is there an architecture document, is it current, how often
does the application release, is there a defined process. These are reasonable
things to know and they are not what determines whether agentic tooling can
operate on a codebase.

What determines that is whether the agent can **build** the code and whether it
can **check** its own output.

An agent working on a codebase generates candidate changes. The value of the
loop is a function of how cheaply a bad candidate can be rejected. With a build
and a test suite, rejection is automatic and takes seconds; the human sees only
candidates that already pass. Without them, every candidate has to be evaluated
by a person reading it, and the throughput of the whole system collapses to the
reading speed of the reviewer — which is roughly where it was before the agent
arrived, with the added cost of reviewing plausible-looking wrong answers rather
than obviously incomplete ones.

Documentation does not close that loop. An accurate architecture document tells
an agent what the system is supposed to do. It does not tell it whether the
change it just made broke something, which is the question that governs how much
autonomy the agent can safely be given.

There is a second-order effect that makes this worse in brownfield specifically.
Where a test suite is missing, the honest options are to build characterisation
tests first — pinning down current behaviour, whatever it is, so that changes can
be detected — or to run without an oracle. Building characterisation tests is
frequently the larger part of the work, and it is work on the *existing* system,
so none of it is visible as progress on the thing that was actually commissioned.
An estimate that treats it as a contingency rather than a phase is wrong in the
direction that hurts.

## Decision

Weight buildability and testability above documentation and lifecycle in the
rubric, and assess them per archetype rather than in aggregate.

The scanner detects, per repository:

- **Buildability** — a build manifest, a lockfile where the ecosystem has one,
  the share of direct dependencies pinned to an exact version, and whether a
  container or devcontainer build definition exists. Levels run from "no build
  definition" to "dependencies fixed and the build environment declared".
- **Testability** — files matching the ecosystem's test conventions, whether a
  test command can be inferred and from what, coverage instrumentation in
  project configuration, and whether a CI definition references running tests.

## The distinction this repository is most careful about

An inferable test command is not evidence that tests exist.

For Maven, Gradle, Go and .NET the toolchain defines a test phase. `mvn -B test`
is a valid command in every Maven repository ever created, including one with no
test sources at all. A tool that treated "a test command was found" as
testability would rate such a repository as having an oracle. The fixture estate
here contains exactly that case, and the scanner reports the command together
with the basis that produced it — "Maven lifecycle (exists whether or not tests
do)" — while scoring testability at level 0 on the file evidence.

The inverse also holds and is reported separately. For Python and Node the runner
has to be declared somewhere, so its absence is real evidence that nobody has
written down how to run the suite.

## Consequences

- Test presence is measured, test quality is not. The scanner counts files and
  computes a test-to-source *file* ratio. That is a much weaker instrument than
  coverage and far weaker than an assessment of whether the assertions mean
  anything. The rubric marks the difference explicitly: passing, meaningful,
  non-flaky tests over the code that carries business risk is human evidence.
- **A high-coverage suite with no real assertions is a worse oracle than no suite
  at all**, because it is trusted. No file listing can distinguish the two, and
  the assessment must not pretend otherwise.
- Test data is a separate constraint from tests, and often the binding one.
  Fixtures containing personal data cannot be used in a loop that sends context
  to a model outside the perimeter, and anonymising them is its own workstream.
  This is human evidence in the rubric because nothing in a repository declares
  it.
- Where testability is weak, the correct output of an assessment is not a lower
  readiness score. It is a phase: build the oracle, then start. Naming it as a
  phase makes it schedulable; leaving it as a risk makes it a surprise.
- **Cost: this is unwelcome news.** "Your documentation is out of date" is a
  finding people accept. "Your estate has no oracle and building one is the first
  half of the project" reads as scope inflation, particularly from anyone with an
  interest in the total. The defence is that every signal behind it is a file
  anybody can go and look at.

## Alternatives considered

**Score documentation as a first-class dimension.** Rejected for the rubric,
though it belongs in the questionnaire. Documentation improves how well an agent
understands intent, which affects the quality of its first draft. Testability
affects whether a wrong draft can be caught. The second is a gate on autonomy;
the first is a modifier on output quality.

**Attempt to run the build and the test suite during the scan.** This is the
right answer and it is out of scope for a file scanner. It needs toolchains,
credentials, network access to internal artefact repositories, and time
proportional to the estate. The scanner therefore reports presence and says so
in those words, and the README names executing a representative sample as the
next thing a human does.
