# src/steindb/transpiler/transpiler.py
"""LLM Transpiler pipeline.

Orchestrates: input sanitization -> prompt assembly -> LLM call ->
output parsing -> injection check -> TranspileResult.
"""

from __future__ import annotations

import structlog

from steindb.contracts.models import ForwardedObject, TranspileResult
from steindb.transpiler.defense import (
    check_canary_leakage,
    generate_canary_token,
    sanitize_oracle_input,
    validate_output_safety,
)
from steindb.transpiler.parser import parse_llm_output
from steindb.transpiler.prompts import (
    SYSTEM_PROMPT,
    build_few_shot_examples,
    build_user_prompt,
)
from steindb.transpiler.router import BYOKConfig, BYOKRouter

logger = structlog.get_logger(__name__)


class Transpiler:
    """The LLM Transpiler agent.

    Takes ForwardedObjects from the Rule Engine and converts them
    to PostgreSQL using an LLM via the BYOK router.
    """

    def __init__(self, config: BYOKConfig) -> None:
        self._config = config
        self._router = BYOKRouter(config)

    async def transpile(
        self,
        obj: ForwardedObject,
        max_retries: int = 3,
    ) -> TranspileResult:
        """Convert a single Oracle object to PostgreSQL via LLM."""
        # Step 1: Sanitize input
        clean_sql = sanitize_oracle_input(obj.source_sql)

        # Step 2: Build prompts
        canary = generate_canary_token()
        few_shot = build_few_shot_examples(clean_sql)
        user_prompt = build_user_prompt(
            oracle_sql=clean_sql,
            object_name=obj.name,
            object_type=obj.object_type,
            few_shot_examples=few_shot,
            context={"schema": obj.schema, "forward_reason": obj.forward_reason},
        )

        # Step 3: Call LLM with retries
        last_error: Exception | None = None
        raw_response: str = ""
        for attempt in range(max_retries):
            try:
                raw_response = await self._router.call(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )
                break
            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM call failed, retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                )
        else:
            raise RuntimeError(f"LLM call failed after {max_retries} retries") from last_error

        # Step 4: Parse output
        result = parse_llm_output(raw_response)

        # Step 5: Safety checks
        if check_canary_leakage(canary, raw_response):
            result = TranspileResult(
                postgresql=result.postgresql,
                confidence=max(0.3, result.confidence - 0.3),
                changes=result.changes,
                warnings=[*result.warnings, "SECURITY: Canary token leaked in output"],
                test_hints=result.test_hints,
            )

        safety = validate_output_safety(result.postgresql)
        if not safety.is_safe:
            result = TranspileResult(
                postgresql=result.postgresql,
                confidence=max(0.3, result.confidence - 0.2),
                changes=result.changes,
                warnings=[
                    *result.warnings,
                    f"SECURITY: Output flagged as potentially unsafe -- {safety.reason}",
                ],
                test_hints=result.test_hints,
            )

        return result
