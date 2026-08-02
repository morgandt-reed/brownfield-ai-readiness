"""Locating the two data files this package ships alongside its code.

The rubric and the runtime support table are deliberately *outside* the package
directory: they are the artefacts a reader is meant to open, edit and disagree
with, so they live at the top of the repository rather than buried in `src/`.
The cost is that finding them means walking up from the module, which works for
a source checkout and an editable install and not for a wheel -- so both errors
say to pass the path explicitly rather than failing obscurely.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def find_upward(subdirectory: str, pattern: str, flag: str, start: Path | None = None) -> Path:
    """Newest file matching `<ancestor>/<subdirectory>/<pattern>`, searching upward."""
    origin = start if start is not None else Path(__file__).resolve()
    for parent in [origin, *origin.parents]:
        candidates = sorted((parent / subdirectory).glob(pattern))
        if candidates:
            return candidates[-1]
    raise FileNotFoundError(
        f"could not locate a {subdirectory}/{pattern} file by searching upward from "
        f"{origin}. Pass one explicitly with {flag}."
    )


def locate(subdirectory: str, pattern: str, flag: str, error: Callable[[str], Exception]) -> Path:
    try:
        return find_upward(subdirectory, pattern, flag)
    except FileNotFoundError as exc:
        raise error(str(exc)) from exc
