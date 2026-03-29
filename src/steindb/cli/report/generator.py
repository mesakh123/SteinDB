"""Report generator — dispatches to the appropriate renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from steindb.cli.report.html_renderer import HTMLReportRenderer
from steindb.cli.report.json_renderer import JSONReportRenderer

if TYPE_CHECKING:
    from steindb.contracts import ScanResult


class ReportGenerator:
    """Dispatch report generation to the correct renderer based on format."""

    def generate(
        self,
        scan_result: ScanResult,
        complexity_scores: dict[str, float],
        dependencies: dict[str, list[str]],
        format: str = "html",  # noqa: A002
    ) -> str:
        """Generate a report in the given format.

        Args:
            scan_result: The scan result to report on.
            complexity_scores: Mapping of object name to complexity score.
            dependencies: Mapping of object name to list of dependency names.
            format: Output format — ``"html"`` or ``"json"``.

        Returns:
            The rendered report as a string.

        Raises:
            ValueError: If the format is not supported.
        """
        if format == "html":
            return HTMLReportRenderer().render(scan_result, complexity_scores, dependencies)
        elif format == "json":
            return JSONReportRenderer().render(scan_result, complexity_scores, dependencies)
        else:
            raise ValueError(f"Unknown format: {format}")
