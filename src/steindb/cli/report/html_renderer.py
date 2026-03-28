# ruff: noqa: E501
"""HTML report renderer — generates a standalone, self-contained HTML report."""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from steindb.contracts import ScannedObject, ScanResult

# ---------------------------------------------------------------------------
# Complexity thresholds (shared with ComplexityScorer)
# ---------------------------------------------------------------------------
_LOW_THRESHOLD = 3.0
_MED_THRESHOLD = 7.0


def _classify(score: float) -> str:
    if score <= _LOW_THRESHOLD:
        return "low"
    elif score <= _MED_THRESHOLD:
        return "medium"
    return "high"


def _status_color(cls: str) -> str:
    return {"low": "#22c55e", "medium": "#eab308", "high": "#ef4444"}.get(cls, "#94a3b8")


def _escape(text: str) -> str:
    return html.escape(str(text))


class HTMLReportRenderer:
    """Generate a standalone HTML report string with dark theme and inline SVG charts."""

    def render(
        self,
        scan_result: ScanResult,
        complexity_scores: dict[str, float],
        dependency_graph: dict[str, list[str]],
    ) -> str:
        """Generate a standalone HTML report string."""
        generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        objects = scan_result.objects

        # --- summary stats ---
        total = scan_result.total_objects
        by_type: dict[str, int] = {}
        for obj in objects:
            by_type[obj.object_type.value] = by_type.get(obj.object_type.value, 0) + 1

        scores = list(complexity_scores.values())
        avg_complexity = sum(scores) / len(scores) if scores else 0.0

        low_count = sum(1 for s in scores if _classify(s) == "low")
        med_count = sum(1 for s in scores if _classify(s) == "medium")
        high_count = sum(1 for s in scores if _classify(s) == "high")

        # Rule-convertible vs LLM-required (threshold: high = LLM)
        rule_convertible = low_count + med_count
        llm_required = high_count

        # Estimated effort placeholder (hours)
        est_effort_hours = round(low_count * 0.5 + med_count * 2.0 + high_count * 8.0, 1)

        # --- complexity factors ---
        complexity_factors = self._collect_complexity_factors(objects)

        # --- build HTML ---
        parts: list[str] = []
        parts.append(self._head(generated_at, scan_result.job_id))
        parts.append(
            self._executive_summary(
                total,
                by_type,
                avg_complexity,
                rule_convertible,
                llm_required,
                est_effort_hours,
            )
        )
        parts.append(self._object_inventory(objects, complexity_scores))
        parts.append(self._complexity_chart(low_count, med_count, high_count))
        parts.append(self._dependency_section(dependency_graph))
        parts.append(self._complexity_factors_section(complexity_factors))
        parts.append(self._savings_estimate(total, est_effort_hours))
        parts.append(self._footer())
        return "".join(parts)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _head(self, generated_at: str, job_id: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SteinDB Migration Report</title>
<style>
:root {{
    --bg: #0f172a;
    --surface: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #3b82f6;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; line-height: 1.6; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem; }}
h1 {{ font-size: 1.8rem; margin-bottom: 0.25rem; }}
h2 {{ font-size: 1.3rem; margin: 2rem 0 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
h3 {{ font-size: 1.1rem; margin: 1rem 0 0.5rem; }}
.meta {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 2rem; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin: 1rem 0; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; text-align: center; }}
.card .value {{ font-size: 1.8rem; font-weight: 700; color: var(--accent); }}
.card .label {{ font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }}
th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border); }}
th {{ background: var(--surface); color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }}
tr:hover {{ background: rgba(59,130,246,0.05); }}
.badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
.badge-low {{ background: rgba(34,197,94,0.15); color: var(--green); }}
.badge-medium {{ background: rgba(234,179,8,0.15); color: var(--yellow); }}
.badge-high {{ background: rgba(239,68,68,0.15); color: var(--red); }}
.dep-list {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 0.85rem; white-space: pre-wrap; max-height: 400px; overflow-y: auto; }}
.factors {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 0.75rem; }}
.factor {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 0.75rem; }}
.factor .name {{ font-weight: 600; margin-bottom: 0.25rem; }}
.factor .count {{ color: var(--accent); font-weight: 700; }}
.savings {{ background: linear-gradient(135deg, #1e3a5f 0%, #1e293b 100%); border: 1px solid var(--accent); border-radius: 8px; padding: 1.5rem; margin: 2rem 0; text-align: center; }}
.savings .big {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
.footer {{ text-align: center; margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.85rem; }}
.cta {{ display: inline-block; margin-top: 0.75rem; padding: 0.6rem 1.5rem; background: var(--accent); color: #fff; text-decoration: none; border-radius: 6px; font-weight: 600; }}
.cta:hover {{ background: #2563eb; }}
.chart-container {{ display: flex; justify-content: center; align-items: center; gap: 2rem; margin: 1rem 0; flex-wrap: wrap; }}
.chart-legend {{ display: flex; flex-direction: column; gap: 0.5rem; }}
.legend-item {{ display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
</style>
</head>
<body>
<div class="container">
<h1>SteinDB Migration Report</h1>
<p class="meta">Generated {_escape(generated_at)} &middot; Job {_escape(job_id)}</p>
"""

    def _executive_summary(
        self,
        total: int,
        by_type: dict[str, int],
        avg_complexity: float,
        rule_convertible: int,
        llm_required: int,
        est_effort_hours: float,
    ) -> str:
        type_summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items()))
        return f"""<h2>Executive Summary</h2>
<div class="cards">
  <div class="card"><div class="value">{total}</div><div class="label">Total Objects</div></div>
  <div class="card"><div class="value">{avg_complexity:.1f}</div><div class="label">Avg Complexity</div></div>
  <div class="card"><div class="value">{rule_convertible}</div><div class="label">Rule Convertible</div></div>
  <div class="card"><div class="value">{llm_required}</div><div class="label">LLM Required</div></div>
  <div class="card"><div class="value">{est_effort_hours}h</div><div class="label">Est. Effort</div></div>
</div>
<p style="color:var(--muted);font-size:0.85rem;">Object types: {_escape(type_summary)}</p>
"""

    def _object_inventory(
        self,
        objects: list[ScannedObject],
        complexity_scores: dict[str, float],
    ) -> str:
        rows: list[str] = []
        for obj in objects:
            score = complexity_scores.get(obj.name, 0.0)
            cls = _classify(score)
            badge_class = f"badge-{cls}"
            rows.append(
                f"<tr>"
                f"<td>{_escape(obj.name)}</td>"
                f"<td>{_escape(obj.object_type.value)}</td>"
                f"<td>{_escape(obj.schema)}</td>"
                f"<td>{score:.1f}</td>"
                f'<td><span class="badge {badge_class}">{cls}</span></td>'
                f"</tr>"
            )
        rows_html = "\n".join(rows)
        return f"""<h2>Object Inventory</h2>
<table>
<thead><tr><th>Name</th><th>Type</th><th>Schema</th><th>Complexity</th><th>Status</th></tr></thead>
<tbody>
{rows_html}
</tbody>
</table>
"""

    def _complexity_chart(self, low: int, med: int, high: int) -> str:
        total = low + med + high
        if total == 0:
            return "<h2>Complexity Breakdown</h2><p>No objects to chart.</p>"

        # SVG bar chart
        bar_width = 400
        bar_height = 28
        gap = 8

        bars: list[str] = []
        data = [("Low", low, "#22c55e"), ("Medium", med, "#eab308"), ("High", high, "#ef4444")]
        max_val = max(low, med, high, 1)

        for i, (label, count, color) in enumerate(data):
            y = i * (bar_height + gap)
            w = int((count / max_val) * (bar_width - 80))
            bars.append(
                f'<g transform="translate(0,{y})">'
                f'<text x="0" y="{bar_height // 2 + 4}" fill="#94a3b8" font-size="13">{label}</text>'
                f'<rect x="70" y="0" width="{w}" height="{bar_height}" rx="4" fill="{color}" opacity="0.8"/>'
                f'<text x="{70 + w + 8}" y="{bar_height // 2 + 4}" fill="#e2e8f0" font-size="13">{count}</text>'
                f"</g>"
            )

        svg_height = len(data) * (bar_height + gap)
        bars_svg = "\n".join(bars)

        return f"""<h2>Complexity Breakdown</h2>
<div class="chart-container">
<svg width="{bar_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">
{bars_svg}
</svg>
</div>
"""

    def _dependency_section(self, dependency_graph: dict[str, list[str]]) -> str:
        if not dependency_graph:
            lines = "No dependencies detected."
        else:
            parts: list[str] = []
            for source, targets in sorted(dependency_graph.items()):
                for target in sorted(targets):
                    parts.append(f"{_escape(source)} -> {_escape(target)}")
            lines = "\n".join(parts)

        return f"""<h2>Dependency Graph</h2>
<div class="dep-list">{lines}</div>
"""

    def _collect_complexity_factors(self, objects: list[ScannedObject]) -> dict[str, int]:
        """Detect Oracle-specific constructs across all objects."""
        import re

        patterns: dict[str, re.Pattern[str]] = {
            "DBMS_LOB": re.compile(r"\bDBMS_LOB\b", re.IGNORECASE),
            "DBMS_SQL": re.compile(r"\bDBMS_SQL\b", re.IGNORECASE),
            "UTL_FILE": re.compile(r"\bUTL_FILE\b", re.IGNORECASE),
            "DBMS_SCHEDULER": re.compile(r"\bDBMS_SCHEDULER\b", re.IGNORECASE),
            "DBMS_OUTPUT": re.compile(r"\bDBMS_OUTPUT\b", re.IGNORECASE),
            "AUTONOMOUS_TRANSACTION": re.compile(r"\bAUTONOMOUS_TRANSACTION\b", re.IGNORECASE),
            "BULK COLLECT": re.compile(r"\bBULK\s+COLLECT\b", re.IGNORECASE),
            "CONNECT BY": re.compile(r"\bCONNECT\s+BY\b", re.IGNORECASE),
            "DECODE": re.compile(r"\bDECODE\s*\(", re.IGNORECASE),
            "NVL": re.compile(r"\bNVL\s*\(", re.IGNORECASE),
            "SYSDATE": re.compile(r"\bSYSDATE\b", re.IGNORECASE),
            "ROWNUM": re.compile(r"\bROWNUM\b", re.IGNORECASE),
            "ROWID": re.compile(r"\bROWID\b", re.IGNORECASE),
            "VARCHAR2": re.compile(r"\bVARCHAR2\b", re.IGNORECASE),
            "NUMBER": re.compile(r"\bNUMBER\b", re.IGNORECASE),
        }

        counts: dict[str, int] = {}
        for obj in objects:
            for name, pat in patterns.items():
                if pat.search(obj.source_sql):
                    counts[name] = counts.get(name, 0) + 1
        return counts

    def _complexity_factors_section(self, factors: dict[str, int]) -> str:
        if not factors:
            return """<h2>Oracle-Specific Constructs Detected</h2>
<p style="color:var(--muted);">No Oracle-specific constructs detected.</p>
"""
        items: list[str] = []
        for name, count in sorted(factors.items(), key=lambda x: -x[1]):
            items.append(
                f'<div class="factor"><span class="name">{_escape(name)}</span> '
                f'&mdash; <span class="count">{count} occurrence{"s" if count != 1 else ""}</span></div>'
            )
        items_html = "\n".join(items)
        return f"""<h2>Oracle-Specific Constructs Detected</h2>
<div class="factors">
{items_html}
</div>
"""

    def _savings_estimate(self, total: int, est_effort_hours: float) -> str:
        manual_hours = total * 8.0  # rough manual estimate per object
        savings_pct = (
            max(0, round((1 - est_effort_hours / manual_hours) * 100, 0)) if manual_hours > 0 else 0
        )
        return f"""<h2>Estimated Savings</h2>
<div class="savings">
<div class="big">~{int(savings_pct)}%</div>
<p>Estimated time savings vs. manual migration</p>
<p style="color:var(--muted);font-size:0.85rem;margin-top:0.5rem;">
Manual estimate: ~{int(manual_hours)}h &middot; With SteinDB: ~{est_effort_hours}h
</p>
</div>
"""

    def _footer(self) -> str:
        return """<div class="footer">
<p>Generated by <strong>SteinDB</strong> &mdash; AI-Powered Oracle-to-PostgreSQL Migration</p>
<a class="cta" href="https://app.steindb.com">Upgrade to SteinDB Cloud</a>
<p style="margin-top:0.75rem;">&copy; 2026 SteinDB Inc.</p>
</div>
</div>
</body>
</html>"""
