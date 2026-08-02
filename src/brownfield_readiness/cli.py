"""`brownfield-scan` — the command line surface.

Three commands, one job each: describe the estate, score it against the rubric,
print the rubric. Errors from this package are printed as one line without a
traceback; anything else is a bug and is allowed to crash loudly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import __version__
from .errors import BrownfieldError
from .render import render_scan
from .rubric import apply, load_rubric
from .runtimes import load_support_table
from .scan import scan_estate
from .serialize import report_to_dict, scan_to_dict

_ROOT = click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
_FORMAT = click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
_SUPPORT_TABLE = click.option(
    "--support-table",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Runtime end-of-support table. Defaults to the newest data/runtime-support-*.yaml.",
)
_RUBRIC = click.option(
    "--rubric",
    "rubric_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Rubric file. Defaults to the newest rubric/readiness-v*.yaml.",
)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="brownfield-scan")
def main() -> None:
    """Assess whether an estate of repositories is ready for agentic tooling.

    Every signal this tool produces is file evidence. It does not build, test or
    resolve anything, and the dimensions that decide most programmes -- data
    governance and adoption -- have no machine signal at all and are reported as
    requiring human assessment.
    """


@main.command()
@_ROOT
@_FORMAT
@_SUPPORT_TABLE
def scan(root: Path, output_format: str, support_table: Path | None) -> None:
    """Detect archetypes and emit a fact sheet per repository under ROOT.

    ROOT is a directory whose immediate children are repository checkouts.
    """
    result = scan_estate(root, load_support_table(support_table))
    if output_format == "json":
        click.echo(json.dumps(scan_to_dict(result), indent=2))
    else:
        click.echo(render_scan(result), nl=False)


@main.command()
@_ROOT
@_FORMAT
@_SUPPORT_TABLE
@_RUBRIC
def score(
    root: Path,
    output_format: str,
    support_table: Path | None,
    rubric_path: Path | None,
) -> None:
    """Scan ROOT and apply the readiness rubric to what was found."""
    result = scan_estate(root, load_support_table(support_table))
    report = apply(load_rubric(rubric_path), result)
    if output_format == "json":
        payload = scan_to_dict(result) | {"readiness": report_to_dict(report)}
        click.echo(json.dumps(payload, indent=2))
    else:
        click.echo(render_scan(result, report), nl=False)


@main.command()
@_FORMAT
@_RUBRIC
def rubric(output_format: str, rubric_path: Path | None) -> None:
    """Print the rubric: dimensions, levels, and what is left to a human."""
    loaded = load_rubric(rubric_path)
    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "id": loaded.id,
                    "version": loaded.version,
                    "as_of": loaded.as_of.isoformat(),
                    "dimensions": [
                        {
                            "id": dimension.id,
                            "title": dimension.title,
                            "scope": dimension.scope,
                            "assessment": dimension.assessment,
                            "question": dimension.question,
                            "machine_evidence": list(dimension.machine_evidence),
                            "human_evidence": list(dimension.human_evidence),
                            "levels": [
                                {
                                    "level": level.level,
                                    "name": level.name,
                                    "definition": level.definition,
                                }
                                for level in dimension.levels
                            ],
                        }
                        for dimension in loaded.dimensions
                    ],
                },
                indent=2,
            )
        )
        return

    lines = [f"{loaded.id} v{loaded.version} (as of {loaded.as_of.isoformat()})", ""]
    for dimension in loaded.dimensions:
        lines.append(f"{dimension.title}  [{dimension.scope}, {dimension.assessment}]")
        lines.append(f"  {dimension.question}")
        for level in dimension.levels:
            lines.append(f"    L{level.level} {level.name}: {level.definition}")
        if dimension.assessment == "human":
            lines.append("    NO MACHINE SIGNAL — this dimension is assessed by asking.")
        if dimension.human_evidence:
            lines.append("    Requires human assessment:")
            lines.extend(f"      - {item}" for item in dimension.human_evidence)
        lines.append("")
    click.echo("\n".join(lines), nl=False)


def run() -> None:
    try:
        main.main(standalone_mode=False)
    except BrownfieldError as exc:
        click.echo(f"brownfield-scan: {exc}", err=True)
        sys.exit(2)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except click.exceptions.Abort:
        sys.exit(130)
