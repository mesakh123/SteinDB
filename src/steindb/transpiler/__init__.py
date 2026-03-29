"""LLM Transpiler module for Oracle-to-PostgreSQL conversion.

Provides BYOK (Bring Your Own Key) routing to any OpenAI-compatible
API endpoint, prompt engineering, structured output parsing, and
prompt injection defense.
"""

from __future__ import annotations

from steindb.transpiler.defense import (
    SafetyCheckResult,
    check_canary_leakage,
    generate_canary_token,
    sanitize_oracle_input,
    validate_output_safety,
)
from steindb.transpiler.parser import extract_json, parse_llm_output
from steindb.transpiler.prompts import (
    SYSTEM_PROMPT,
    FewShotExample,
    build_few_shot_examples,
    build_user_prompt,
)
from steindb.transpiler.router import BYOKConfig, BYOKRouter, ModelProvider
from steindb.transpiler.transpiler import Transpiler

__all__ = [
    "BYOKConfig",
    "BYOKRouter",
    "FewShotExample",
    "ModelProvider",
    "SYSTEM_PROMPT",
    "SafetyCheckResult",
    "Transpiler",
    "build_few_shot_examples",
    "build_user_prompt",
    "check_canary_leakage",
    "extract_json",
    "generate_canary_token",
    "parse_llm_output",
    "sanitize_oracle_input",
    "validate_output_safety",
]
