# ADR-0003: Size the work by archetype, not by application count

- **Status:** Accepted
- **Date:** 2026-08-02

## Context

Estate work gets scoped by counting applications. It is the number everyone has,
it appears in every inventory, and it is nearly useless for sizing agentic
tooling.

The work of onboarding a repository divides into two parts. One part is specific
to that repository: its conventions, its quirks, the things only this codebase
does. The other part is specific to its *technology family*: how the build works,
where tests live, how the container is defined, what the agent needs to be told
about the framework's structure. The second part is done once per family and
reused across every repository in it.

That makes family count, not repository count, the multiplier. An estate of
twenty repositories over four technology families is a fundamentally different
piece of work from twenty repositories over twenty families, and the difference
is not marginal — in the first case the fifth repository onward is incremental,
in the second there is no economy of scale at all.

## Decision

Group repositories into archetypes and report the grouping as the primary
estate-level finding. Define an archetype as the triple **(language, build
system, framework family)**.

The framework family is in the key deliberately. Two Maven repositories, one
Spring Boot and one plain Java, share a build command and very little else: not
the test scaffolding, not the configuration surface, not the conventions an agent
has to be told about. Grouping on language and build system alone would merge
them and overstate reuse — which is the direction of error that makes an estimate
too small.

The scanner reports two derived figures:

- **Reuse factor** — the share of repositories that are not the first of their
  archetype. It is `1 - archetypes / repositories`.
- **Mean repositories per archetype.**

The rubric bands the reuse factor into four levels, from *fragmented* (below
0.25) to *highly concentrated* (0.75 and above).

## What the reuse factor is, exactly

It is arithmetic over the grouping. Nothing more.

It says how many onboardings *could* draw on work already done for a sibling. It
does not say how much of that work is genuinely reusable, which is a judgement
about how alike two repositories are beyond their build manifest. Two Spring Boot
services in the same estate can share a manifest shape and disagree about
everything the tooling would need to encode. The rubric records that as human
evidence against this dimension in as many words.

The committed fixture estate makes the point without flattering it: eight
repositories, seven archetypes, reuse factor 0.12 — level 0, *fragmented*. That
is close to the expensive case, where the application count and the archetype
count are nearly the same number and every repository is its own onboarding.

## Consequences

- The single most valuable question in an intake conversation is "how many
  technology families, really?" and the answer is very often not known. It is
  worth measuring before it is worth estimating, which is what the scanner is
  for.
- Where an estate is fragmented, the useful response is usually to narrow scope
  rather than to accept the multiplier: pick the largest one or two archetypes,
  do those properly, and let the rest wait for evidence that the approach works.
  An assessment that reports fragmentation without offering that option has
  described a problem and withheld the obvious move.
- An archetype is onboarded against its **weakest** member, not its average one.
  The scanner therefore reports the worst level within each archetype alongside
  the per-repository table. Averaging within an archetype hides the repository
  that stops the work, which is the only one whose state changes the plan.
- **Detection is manifest-shaped and gets things wrong.** A repository with an
  unusual layout, a polyglot repository, or one whose framework is loaded
  dynamically rather than declared will be misfiled. The output lists every
  manifest found, including manifests belonging to ecosystems that were not
  chosen, so a reader who knows better can see where the tool went astray. The
  grouping is a starting point for a conversation, not a finding.
- **Cost: the archetype count is not stable under scope changes.** Adding one
  unusual repository to a scan can move the estate down a band. That is arguably
  correct — it genuinely is another onboarding problem — but it makes the figure
  easy to move by argument about what is in scope, and anyone quoting it should
  say what was scanned.

## Alternatives considered

**Group by language only.** Simpler, more stable, and overstates reuse. It merges
a Spring Boot service with a plain Java batch job, and those are not one problem.

**Group by language, build system, framework *and* runtime version.** Splits more
finely and is defensible — a Java 8 repository and a Java 21 repository do differ
in what tooling can be applied. Rejected because runtime version is reported per
repository anyway, and adding it to the key would fragment nearly every estate
into singletons, at which point the metric stops discriminating between estates.
Version spread is a fact about repositories; family is a fact about the work.

**Weight archetypes by repository count, size or business criticality.** Worth
doing in a real assessment and left out of the tool. Lines of code is a bad proxy
for onboarding effort, and criticality is not in the repository. Both would
require the tool to assert something it cannot see, in service of a single
prettier number.
