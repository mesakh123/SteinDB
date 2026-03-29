# src/steindb/verifier/confidence.py
"""Stage 4: Weighted confidence scoring and status classification."""

from __future__ import annotations

from steindb.contracts.models import VerifyStatus

# Weights (must sum to 1.0)
WEIGHT_PARSE = 0.30
WEIGHT_EXPLAIN = 0.25
WEIGHT_LLM_CONFIDENCE = 0.25
WEIGHT_COMPLEXITY = 0.20

# Penalties
ISSUE_PENALTY = 0.05

# Thresholds
GREEN_THRESHOLD = 0.95
YELLOW_THRESHOLD = 0.70


def compute_confidence(
    parse_valid: bool,
    explain_valid: bool,
    llm_confidence: float,
    complexity: float,
    issue_count: int,
) -> float:
    """Compute weighted confidence score.

    Weights:
    - Parse validation: 30%
    - EXPLAIN validation: 25%
    - LLM self-reported confidence: 25%
    - Complexity inverse: 20%

    Issue penalty: -5% per issue.
    """
    if not parse_valid:
        return 0.0

    score = 0.0

    # Parse (30%)
    score += WEIGHT_PARSE * (1.0 if parse_valid else 0.0)

    # EXPLAIN (25%)
    score += WEIGHT_EXPLAIN * (1.0 if explain_valid else 0.3)

    # LLM confidence (25%)
    score += WEIGHT_LLM_CONFIDENCE * min(1.0, max(0.0, llm_confidence))

    # Complexity inverse (20%) -- higher complexity = lower score
    complexity_factor = max(0.0, 1.0 - (complexity / 15.0))
    score += WEIGHT_COMPLEXITY * complexity_factor

    # Issue penalties
    score -= ISSUE_PENALTY * issue_count

    return max(0.0, min(1.0, score))


def classify_status(
    confidence: float,
    issue_count: int,
) -> VerifyStatus:
    """Classify verification status based on confidence and issues.

    - GREEN: >= 0.95 AND no issues (auto-approve)
    - YELLOW: >= 0.70 (human review)
    - RED: < 0.70 (reject)
    """
    if confidence >= GREEN_THRESHOLD and issue_count == 0:
        return VerifyStatus.GREEN
    elif confidence >= YELLOW_THRESHOLD:
        return VerifyStatus.YELLOW
    else:
        return VerifyStatus.RED
