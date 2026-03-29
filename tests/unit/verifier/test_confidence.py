# tests/unit/verifier/test_confidence.py
"""Tests for confidence scoring."""

from __future__ import annotations

from steindb.contracts.models import VerifyStatus
from steindb.verifier.confidence import classify_status, compute_confidence


class TestComputeConfidence:
    def test_perfect_score(self) -> None:
        score = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=1.0,
            complexity=1.0,
            issue_count=0,
        )
        assert score >= 0.95

    def test_parse_failure_zero(self) -> None:
        score = compute_confidence(
            parse_valid=False,
            explain_valid=False,
            llm_confidence=0.5,
            complexity=5.0,
            issue_count=1,
        )
        assert score == 0.0

    def test_explain_failure_reduces_score(self) -> None:
        good = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=0.9,
            complexity=3.0,
            issue_count=0,
        )
        bad = compute_confidence(
            parse_valid=True,
            explain_valid=False,
            llm_confidence=0.9,
            complexity=3.0,
            issue_count=0,
        )
        assert good > bad

    def test_issues_reduce_score(self) -> None:
        no_issues = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=0.9,
            complexity=3.0,
            issue_count=0,
        )
        with_issues = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=0.9,
            complexity=3.0,
            issue_count=3,
        )
        assert no_issues > with_issues

    def test_high_complexity_reduces_score(self) -> None:
        simple = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=0.9,
            complexity=1.0,
            issue_count=0,
        )
        complex_ = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=0.9,
            complexity=14.0,
            issue_count=0,
        )
        assert simple > complex_

    def test_score_clamped_0_to_1(self) -> None:
        score = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=1.0,
            complexity=0.0,
            issue_count=0,
        )
        assert 0.0 <= score <= 1.0

    def test_many_issues_floor_at_zero(self) -> None:
        score = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=0.5,
            complexity=10.0,
            issue_count=50,
        )
        assert score == 0.0

    def test_low_llm_confidence(self) -> None:
        high_llm = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=0.95,
            complexity=3.0,
            issue_count=0,
        )
        low_llm = compute_confidence(
            parse_valid=True,
            explain_valid=True,
            llm_confidence=0.3,
            complexity=3.0,
            issue_count=0,
        )
        assert high_llm > low_llm


class TestClassifyStatus:
    def test_green(self) -> None:
        assert classify_status(0.97, issue_count=0) == VerifyStatus.GREEN

    def test_yellow(self) -> None:
        assert classify_status(0.85, issue_count=0) == VerifyStatus.YELLOW

    def test_red(self) -> None:
        assert classify_status(0.60, issue_count=0) == VerifyStatus.RED

    def test_green_with_issues_becomes_yellow(self) -> None:
        assert classify_status(0.97, issue_count=1) == VerifyStatus.YELLOW

    def test_exactly_green_threshold(self) -> None:
        assert classify_status(0.95, issue_count=0) == VerifyStatus.GREEN

    def test_exactly_yellow_threshold(self) -> None:
        assert classify_status(0.70, issue_count=0) == VerifyStatus.YELLOW

    def test_just_below_yellow(self) -> None:
        assert classify_status(0.69, issue_count=0) == VerifyStatus.RED
