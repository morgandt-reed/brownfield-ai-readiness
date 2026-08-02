# Brownfield AI Readiness

[![CI](https://github.com/morgandt-reed/brownfield-ai-readiness/actions/workflows/ci.yml/badge.svg)](https://github.com/morgandt-reed/brownfield-ai-readiness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org/)
[![Rubric](https://img.shields.io/badge/rubric-v1-2c3e50)](rubric/readiness-v1.yaml)

A method for deciding whether an existing application estate is ready for
agentic development tooling, and a scanner that does the part of it a machine can
actually do.

> **The four claims this repository is built on.**
>
> **Fix the purpose before taking any inventory.** Assisted maintenance,
> characterisation test generation, modernisation and documentation are
> radically different efforts over the same repositories. Without a named
> primary use case, an estimate has no denominator.
> ([ADR-0001](docs/adr/0001-purpose-before-inventory.md))
>
> **Testability and buildability are the constraint — not documentation
> quality, not lifecycle maturity.** An agent needs an oracle and a gate to
> operate with any autonomy. Where there is no test suite, the honest options
> are to build characterisation tests first, routinely the larger half of the
> work, or to run blind. ([ADR-0002](docs/adr/0002-testability-is-the-constraint.md))
>
> **It is not N applications, it is N archetypes.** Onboarding work is done per
> technology family and reused per repository, so family count is the
> multiplier and application count is nearly irrelevant.
> ([ADR-0003](docs/adr/0003-archetypes-not-applications.md))
>
> **"Security" means three separate things** — quality guardrails, application
> security, and data/IP governance — with different owners and different
> consequences. Only two of the three leave any trace in a repository.
> ([ADR-0004](docs/adr/0004-three-meanings-of-security.md))

**And the part that is not a claim so much as a warning.** The scanner reads
files. It does not build, test, resolve or fetch anything. Two of the six rubric
dimensions have no machine signal at all, and they are frequently the two that
decide whether the programme happens. See
[What the scanner cannot tell you](#what-the-scanner-cannot-tell-you) — that
section is the point of this repository, not a disclaimer at the bottom of it.

## What is here

| | |
|---|---|
| [`brownfield-scan`](src/brownfield_readiness/) | A CLI that walks a directory of repositories and emits an archetype map, a per-repository fact sheet, and rubric levels. Text and JSON. |
| [`rubric/readiness-v1.yaml`](rubric/readiness-v1.yaml) | Six dimensions with explicitly defined levels and the evidence that moves one. Four are machine-scored in part; two are marked as requiring human assessment. |
| [`docs/intake-questionnaire.md`](docs/intake-questionnaire.md) | The questions an assessor asks, with the unconditional ones marked. |
| [`docs/adr/`](docs/adr/) | Five decision records — the argument, not the code. |
| [`fixtures/`](fixtures/) | Eight committed repositories and one unrecognised directory. Every number below comes from scanning them. |

## Quick start

```bash
git clone https://github.com/morgandt-reed/brownfield-ai-readiness.git
cd brownfield-ai-readiness
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

brownfield-scan scan fixtures
brownfield-scan score fixtures
brownfield-scan rubric
```

`scan` takes a directory whose immediate children are repository checkouts.

## A real run

Output below is produced by the command shown, against the committed fixture
estate. It is stored at [`tests/golden/scan.txt`](tests/golden/scan.txt) and
[`tests/golden/score.txt`](tests/golden/score.txt), and CI diffs the live CLI
against both — so this README cannot drift away from the tool.

### The archetype map

```console
$ brownfield-scan scan fixtures
ARCHETYPE MAP
  root: fixtures

  Archetype                                 Repos  Repositories
  java / maven / spring-boot                2      customer-portal, inventory-api
  dotnet / msbuild / no framework detected  1      reporting-tool
  go / go-modules / no framework detected   1      notify-worker
  java / maven / no framework detected      1      legacy-batch
  javascript / npm / react                  1      web-frontend
  python / pip-requirements / fastapi       1      invoicing-api
  python / pyproject / fastapi              1      orders-api

  8 repositories fall into 7 archetypes.
  Mean repositories per archetype: 1.14
  Reuse factor: 0.12
  ...

  Skipped — no recognised build manifest at the repository root:
    platform-docs: no recognised build manifest at the repository root
```

An estate of eight that is nearly eight separate onboarding problems. Two things
in that table are worth pausing on.

**`legacy-batch` and `inventory-api` are both Java and both Maven, and they are
not the same archetype.** One is Spring Boot and one is not. They share a build
command and almost nothing the tooling would need to encode — not the test
scaffolding, not the configuration surface, not the conventions an agent has to
be told about. Grouping on language and build system alone would merge them and
overstate reuse, which is the direction of error that makes an estimate too
small.

**`platform-docs` is reported, not dropped.** A scanner that silently ignores a
third of the estate is worse than one that finds nothing, because the omission is
invisible.

### Two fact sheets from the same archetype

```console
  customer-portal
    build manifests:      pom.xml
    lockfile:             n/a — this build system has no lockfile
    dependencies pinned:  3/3 (100%)
    container build:      Dockerfile
    declared runtime:     java 17 (pom.xml) — supported, end of support 2027-10-31
    test files:           1 test / 2 source files — ratio 0.50
    test command:         mvn -B test  [Maven lifecycle (exists whether or not tests do)]
    coverage config:      jacoco
    CI:                   jenkins — references tests
    analysis tooling:     checkstyle

  inventory-api
    build manifests:      pom.xml
    lockfile:             n/a — this build system has no lockfile
    dependencies pinned:  1/4 (25%)
    container build:      none
    declared runtime:     java 17 (pom.xml) — supported, end of support 2027-10-31
    test files:           1 test / 1 source files — ratio 1.00
    test command:         mvn -B test  [Maven lifecycle (exists whether or not tests do)]
    coverage config:      none
    CI:                   none
    analysis tooling:     none
```

Same archetype, and the second one is where the work stops. That is why the
report also prints the worst level within each archetype rather than an average:
an archetype is onboarded against its weakest member.

### The one every reader should be suspicious of

```console
  legacy-batch
    test files:           0 test / 2 source files — ratio 0.00
    test command:         mvn -B test  [Maven lifecycle (exists whether or not tests do)]
```

**A test command was inferred and there are no tests.** `mvn -B test` is valid in
every Maven repository ever created, because Maven defines a test phase. So is
`go test ./...`, and `dotnet test`. A tool that reported "test command found" as
testability would rate this repository as having an oracle, which is exactly
backwards — so the basis that produced the command is printed next to it, and
testability scores 0.

The inverse holds too, and is reported separately. `invoicing-api` is Python: its
runner has to be declared somewhere, so `could not be inferred` is real evidence
that nobody has written down how to run the suite.

### The rubric applied

```console
$ brownfield-scan score fixtures
READINESS RUBRIC — brownfield-agentic-readiness v1 (as of 2026-08-02)

ESTATE-LEVEL DIMENSIONS
  Archetype concentration: L0 fragmented
    8 repositories across 7 archetypes; reuse factor 0.12
  Data and IP governance constraint: —
    requires human assessment — no signal for this exists in a repository
  Adoption readiness: —
    requires human assessment — no signal for this exists in a repository

PER-REPOSITORY DIMENSIONS
  Repository       buildability                 testability           guardrail coverage
  invoicing-api      L1 manifest-only             L0 no-tests-detected  L0 no-automation
  customer-portal  L3 reproducible-environment  L3 tests-gated        L3 analysis-in-pipeline
  inventory-api    L1 manifest-only             L2 tests-runnable     L0 no-automation
  legacy-batch     L2 pinned                    L0 no-tests-detected  L0 no-automation
  notify-worker    L3 reproducible-environment  L2 tests-runnable     L0 no-automation
  orders-api       L3 reproducible-environment  L3 tests-gated        L3 analysis-in-pipeline
  reporting-tool   L2 pinned                    L0 no-tests-detected  L0 no-automation
  web-frontend     L2 pinned                    L3 tests-gated        L3 analysis-in-pipeline

WORST LEVEL WITHIN EACH ARCHETYPE
  The binding repository, not the average one. An archetype is onboarded
  against its weakest member, because that is the one that stops.
  Archetype                        buildability                 testability           guardrail coverage
  java/maven/spring-boot           L1 manifest-only             L2 tests-runnable     L0 no-automation
  dotnet/msbuild/none              L2 pinned                    L0 no-tests-detected  L0 no-automation
  go/go-modules/none               L3 reproducible-environment  L2 tests-runnable     L0 no-automation
  java/maven/none                  L2 pinned                    L0 no-tests-detected  L0 no-automation
  javascript/npm/react             L2 pinned                    L3 tests-gated        L3 analysis-in-pipeline
  python/pip-requirements/fastapi  L1 manifest-only             L0 no-tests-detected  L0 no-automation
  python/pyproject/fastapi         L3 reproducible-environment  L3 tests-gated        L3 analysis-in-pipeline
```

## The rubric

Six dimensions, versioned in [`rubric/readiness-v1.yaml`](rubric/readiness-v1.yaml).
Each carries four levels with a definition and the evidence that moves one, plus
two separate lists: `machine_evidence` and `human_evidence`.

| Dimension | Scope | Assessment | What the level means |
|---|---|---|---|
| **Buildability** | repository | mixed | 0 no build definition · 1 manifest only · 2 dependencies fixed by a lockfile or ≥80% pinning · 3 plus a declared build environment |
| **Testability** | repository | mixed | 0 no tests detected · 1 tests, no inferable runner · 2 tests and a runner · 3 plus coverage instrumentation and a CI reference |
| **Archetype concentration** | estate | machine | Reuse-factor bands: 0 below 0.25 · 1 to 0.50 · 2 to 0.75 · 3 above |
| **Guardrail coverage** | repository | mixed | 0 no CI · 1 CI present · 2 CI references tests · 3 plus analysis or security tooling configured |
| **Data and IP governance constraint** | estate | **human** | 0 unestablished · 1 identified · 2 written policy naming destinations · 3 a technical control enforcing it |
| **Adoption readiness** | estate | **human** | 0 unsponsored · 1 individual experimentation · 2 named owner with time · 3 plus a success criterion and a measured baseline |

Two properties of the scoring are deliberate and are asserted by tests.

**There is no composite score.** The dimensions are not commensurable. An estate
at level 3 on buildability, concentration and guardrails and level 0 on data
governance is not three-quarters ready; it is blocked. A total would rank it
above an estate that is mediocre everywhere and blocked nowhere, which inverts
the correct decision.

**An unassessed dimension is unscored, never level 0.** Text renders it as `—`
and JSON as `null`. Treating an unasked question as a bad answer would let an
assessment improve by declining to ask.

## What the scanner cannot tell you

This is the part that matters. Every signal below is file presence; the scanner
runs nothing and fetches nothing.

**Whether the build works.** It reports a manifest, a lockfile, a pinning ratio
and a container definition. It has never run `mvn package`. A repository at
buildability level 3 can fail on a clean machine for a missing credential, an
unreachable internal registry, or a toolchain nobody has installed since 2021.
The next thing a human does is build a representative sample per archetype.

**Whether the tests pass, or mean anything.** Test *presence* is measured — file
counts and a test-to-source file ratio, which is a much weaker instrument than
coverage and far weaker than an assessment of what is asserted. A suite that
executes code and asserts nothing scores identically to a real one. That case is
worse than having no tests, because it is trusted.

**Whether a gate is enforced.** Branch protection is a server-side setting and is
not in the checkout. A repository can contain an immaculate pipeline that nothing
requires to pass, and it looks the same either way. Nor can the scanner tell
whether a failing gate blocks a merge or is routinely overridden.

**Anything about data restrictions.** No file says where this source code is
permitted to go, whether it may be sent to a third-party endpoint, whether it may
be retained or trained on. This is a legal and contractual question and it gates
the entire design. The rubric keeps it as a dimension precisely so that it cannot
be dropped for being inconvenient to automate.

**Regulatory requirements.** Which framework applies, what must be demonstrable
to an auditor, how many human approval points are mandated. None of it is
inferable from a repository.

**Adoption appetite.** Whether a named team owns this and has time allocated,
what happened the last time assisted tooling was introduced, whether the review
workflow can change and who has to agree. Tooling that is technically correct and
unused has failed, and it fails in a way that looks like success right up to the
point where usage is measured.

**Code quality, architecture, and technical debt.** The scanner counts files. It
has no opinion about what is in them.

### Three ways the scanner is confidently wrong

Named specifically, because a limitation you can reproduce is more useful than
one stated in general terms.

**Maven with parent-managed versions.** `inventory-api` reports `1/4 (25%)`
dependencies pinned. The three unpinned ones get their versions from a Spring
Boot parent POM, which is normal practice and reproducible in a way the scanner
cannot see — resolving parent POMs means being a build tool. The statement is
true about the file and misleading about the build.

**Archetype detection is manifest-shaped.** A repository with an unusual layout,
a polyglot repository, or one whose framework is loaded dynamically rather than
declared will be misfiled. Every manifest found is listed, including those
belonging to ecosystems that were not selected, so the mistake is visible.

**"CI references tests" is a keyword match.** The word "test" anywhere in a
pipeline definition, or the whole inferred command. A job merely *named* "tests"
passes. Matching the first token of the inferred command was tried and rejected:
for Go and Maven that token is the toolchain binary, so `go build ./...` read as
running tests.

## Runtime age, and why it is judged against a date rather than a clock

The scanner has no network access, so it cannot ask a registry how old a
dependency is. What it does instead is read the runtime version a repository
declares for itself and compare it against
[`data/runtime-support-2026-08.yaml`](data/runtime-support-2026-08.yaml) — a
committed table of published end-of-support dates, each carrying a source URL, a
test asserting that URL is present, and its own CI job.

The comparison is made against the **table's** `as_of` date, not today's. A scan
is therefore reproducible: the same tree scanned next year gives the same answer,
and the answer changes when somebody updates the table, which is a reviewable
commit rather than a silent drift. Pass `--support-table` to use your own.

A runtime with no entry is reported as `unknown`, never as supported. Go is
deliberately absent from the table — its policy is "the two most recent releases"
with no published calendar date per version, so there is nothing to transcribe,
and inventing one would be worse than reporting `unknown`.

Java is the awkward case and the table says so per entry: there is no single
end-of-support date for a Java version, so the shipped dates are Eclipse
Temurin's community support, which is the default for an organisation with no
commercial JDK agreement.

## Adopting tooling into an existing repository

[ADR-0005](docs/adr/0005-reverse-bootstrap.md) sets out the retrofit path in
three stages: analyse the repository and write an adoption plan naming what can
be added without breaking anything **plus the explicit residual debt**; then one
bootstrap change that adds configuration and gates and **touches no application
code**; then optional, separate, incremental conformance changes.

The boundary at stage two is the whole design. A reviewer can verify "this
touches no application code" from the file list, which is a much cheaper check
than "this refactoring is behaviour-preserving" — and it is what makes the change
mergeable by a team that has no reason yet to trust the tooling.

Expect weeks, not minutes. Tooling that presents adoption as a button produces
stage two and calls the job done, leaving the residual debt undocumented.

## Repository layout

```
src/brownfield_readiness/
  ecosystems.py  The tables: manifests, lockfiles, test conventions, framework markers.
  detect.py      Archetype detection and dependency pinning, per ecosystem.
  facts.py       Presence signals: tests, CI, coverage, containers. Runs nothing.
  runtimes.py    Declared runtime versions against the dated support table.
  scan.py        Directory walking and archetype grouping. Stable ordering.
  rubric.py      Rubric loading, validation, and the threshold scorers.
  render.py      Text output. Pure functions, no calculation.
  serialize.py   JSON projection of the same value objects.
  cli.py         Three commands.
rubric/          The versioned rubric. The specification; rubric.py is one implementation.
data/            Dated runtime support table with a source URL per entry.
docs/adr/        Five decision records.
fixtures/        The estate every number in this README comes from.
tests/           240 tests, 95% coverage floor, golden CLI output.
```

## Development

```bash
pytest                    # 240 tests, 95% coverage floor
ruff check .              # pinned 0.6.9
ruff format --check .
```

CI runs lint, the test matrix on 3.11–3.13, the support-table provenance suite as
its own visible job, and the scanner against the committed fixtures — including a
diff of the golden files against live CLI output, so the README cannot drift away
from the tool. No `continue-on-error`, no `|| true`.

One deliberate exception: `fixtures/` is excluded from linting. Several of those
repositories are shabby on purpose — unpinned dependencies, an end-of-support
runtime, no tests — because that is what they exist to demonstrate.

## Roadmap

Not implemented, and named rather than implied:

- **Executing a build and a test suite** for a representative repository per
  archetype, in a container, with the result reported alongside the presence
  signals. This is the single largest gap between what the scanner reports and
  what an assessment needs.
- Monorepo support: today the unit of input is a directory of checkouts, and
  inferring project boundaries inside one repository is a separate problem.
- Reading git history for change frequency and last-release age, which would turn
  "maintenance state" from a questionnaire item into a measured one.
- Resolving Maven parent POMs and Gradle version catalogues, so the pinning
  signal stops being misleading for the most common enterprise Java setup.
- A machine-readable adoption plan skeleton generated from a scan — facts and
  headings only, with the residual-debt section left empty for a human, per
  ADR-0005.

## Licence

MIT. See [LICENSE](LICENSE).
