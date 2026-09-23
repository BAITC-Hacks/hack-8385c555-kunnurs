"""OpenAI explanation adapter. Scores and numeric summaries stay server-owned."""

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable, Mapping
from typing import Literal

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAIError
from pydantic import Field, ValidationError, create_model

from ai import cache
from ai.evidence import build_evidence, composition
from ai.privacy import redact
from ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from ai.settings import AISettings
from contracts.schemas import AINarrative, AISelection, Analysis, AnalysisEvidence, Catalog, MeasureContribution, ScenarioAlternative, SimulationResult

logger = logging.getLogger(__name__)

FALLBACK_NOTICES = {
    "missing_api_key": "API-ключ не настроен. Показано шаблонное объяснение; расчёт Score выполнен.",
    "invalid_configuration": "Настройки AI некорректны. Показано шаблонное объяснение.",
    "timeout": "AI не ответил вовремя. Показано шаблонное объяснение; расчёт Score выполнен.",
    "connection_error": "Нет связи с AI-провайдером. Показано шаблонное объяснение.",
    "authentication_error": "AI-провайдер отклонил ключ. Показано шаблонное объяснение.",
    "permission_error": "Нет доступа к выбранной модели. Показано шаблонное объяснение.",
    "rate_limit": "Достигнут лимит AI-провайдера. Показано шаблонное объяснение.",
    "provider_error": "AI-провайдер вернул ошибку. Показано шаблонное объяснение.",
    "invalid_output": "Ответ AI не прошёл проверку. Показано шаблонное объяснение.",
}


def configured_mode(mode: str) -> str:
    """Configuration readiness only; this does not make a billable probe."""
    if mode == "mock":
        return "mock"
    try:
        settings = AISettings.from_env()
        return "live" if settings.api_key.get_secret_value() else "fallback"
    except ValidationError:
        return "fallback"


def _summary(result: SimulationResult, catalog: Catalog) -> str:
    return f"Score {result.score:.2f} ({result.score_delta:+.2f} к базе). Использовано {result.total_cost} из {result.budget} единиц бюджета. " + composition(result, catalog)


def _payload(result: SimulationResult, catalog: Catalog, evidence: AnalysisEvidence) -> str:
    selected = {effect.measure_id for effect in result.measure_effects}
    data = {
        "result": result.model_dump(mode="json"),
        "rules": catalog.rules.model_dump(),
        "selected_measures": [m.model_dump(mode="json") for m in catalog.measures if m.id in selected],
        "conflicts": [c.model_dump(mode="json") for c in catalog.conflicts],
        "composition": composition(result, catalog),
        "evidence": evidence.model_dump(),
    }
    return json.dumps(redact(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_selection(selection: AISelection, evidence: AnalysisEvidence) -> AISelection:
    for identifiers, allowed in (
        (selection.strength_ids, evidence.strengths),
        (selection.risk_ids, evidence.risks),
        (selection.recommendation_ids, evidence.recommendations),
    ):
        if len(identifiers) != len(set(identifiers)) or any(identifier not in allowed for identifier in identifiers):
            raise ValueError("invalid_output")
    return selection


def _render(selection: AISelection, evidence: AnalysisEvidence) -> AINarrative:
    _validate_selection(selection, evidence)
    risk_ids = list(dict.fromkeys([*evidence.mandatory_risk_ids, *selection.risk_ids]))
    return AINarrative(
        strengths=[redact(evidence.strengths[key]) for key in selection.strength_ids],
        risks=[redact(evidence.risks[key]) for key in risk_ids],
        recommendations=[redact(text) for text in evidence.recommendations.values()],
    )


async def _request_selection(settings: AISettings, payload: str, evidence: AnalysisEvidence) -> AISelection:
    # Constrain generation itself, not just post-validation: M7 is NOT the fact
    # ID contribution_M7. Static string schemas allowed that common model error.
    selection_schema = create_model(
        "ScenarioSelection", __base__=AISelection,
        strength_ids=(list[Literal[tuple(evidence.strengths)]], Field(min_length=1, max_length=3)),
        risk_ids=(list[Literal[tuple(evidence.risks)]], Field(min_length=1, max_length=3)),
        recommendation_ids=(list[Literal[tuple(evidence.recommendations)]], Field(min_length=1, max_length=2)),
    )
    # Explicit endpoint prevents an inherited OPENAI_BASE_URL from redirecting secrets.
    # The outer deadline also bounds SDK retry-after/backoff and slow streaming bodies.
    async with asyncio.timeout(settings.timeout):
        async with AsyncOpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url="https://api.openai.com/v1",
            timeout=settings.request_timeout,
            max_retries=1,
        ) as client:
            response = await client.responses.parse(
                model=settings.model,
                input=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": payload}],
                text_format=selection_schema,
                max_output_tokens=400,
                store=False,
            )
            if response.status != "completed" or response.output_parsed is None:
                raise ValueError("invalid_output")
            return _validate_selection(response.output_parsed, evidence)


def _live(result: SimulationResult, catalog: Catalog, evidence: AnalysisEvidence) -> Analysis:
    try:
        settings = AISettings.from_env()
    except ValidationError:
        return _template(result, catalog, evidence, reason="invalid_configuration")
    payload = _payload(result, catalog, evidence)
    key = hashlib.sha256(f"{PROMPT_VERSION}\n{settings.model}\n{payload}".encode()).hexdigest()
    selection = cache.get(key) if settings.cache_enabled else None
    if selection is not None:
        try:
            _validate_selection(selection, evidence)
        except ValueError:
            selection = None
    source = "cache" if selection is not None else "provider"
    if selection is None:
        if not settings.api_key.get_secret_value():
            return _template(result, catalog, evidence, reason="missing_api_key")
        try:
            selection = asyncio.run(_request_selection(settings, payload, evidence))
        except (TimeoutError, APITimeoutError):
            return _template(result, catalog, evidence, reason="timeout")
        except APIConnectionError:
            return _template(result, catalog, evidence, reason="connection_error")
        except APIStatusError as exc:
            reason = {401: "authentication_error", 403: "permission_error", 404: "permission_error", 429: "rate_limit"}.get(exc.status_code, "provider_error")
            return _template(result, catalog, evidence, reason=reason)
        except OpenAIError:
            return _template(result, catalog, evidence, reason="provider_error")
        except (ValidationError, ValueError):
            return _template(result, catalog, evidence, reason="invalid_output")
        if settings.cache_enabled:
            cache.put(key, selection)
    narrative = _render(selection, evidence)
    return Analysis(
        mode="live", source=source, summary=_summary(result, catalog), **narrative.model_dump(),
        notice=("AI-разбор" if source == "provider" else "Сохранённый AI-разбор") + ": модель выделила сильные стороны и дополнительные риски. Обязательные риски и все проверенные замены показаны сервером независимо от выбора AI.",
    )


def explain_scenario(
    result: SimulationResult,
    catalog: Catalog,
    *,
    mode: str = "mock",
    tools: Mapping[str, Callable] | None = None,
    alternatives: list[ScenarioAlternative] | None = None,
    contributions: list[MeasureContribution] | None = None,
) -> Analysis:
    # No tool declarations are sent to the model. Arbitrary callbacks are never run.
    evidence = build_evidence(result, catalog, alternatives, contributions)
    if mode == "live":
        return _live(result, catalog, evidence)
    return _template(result, catalog, evidence)


def _template(result: SimulationResult, catalog: Catalog, evidence: AnalysisEvidence, reason: str | None = None) -> Analysis:
    if reason:
        # Only a fixed reason code is logged, never exception bodies, prompts or keys.
        logger.warning("ai_fallback reason=%s", reason)
    narrative = _render(AISelection(
        strength_ids=list(evidence.strengths)[:2],
        risk_ids=[key for key in evidence.risks if key not in evidence.mandatory_risk_ids][:2],
        recommendation_ids=list(evidence.recommendations)[:2],
    ), evidence)
    return Analysis(
        mode="fallback" if reason else "mock", source="template", reason=reason,
        summary=_summary(result, catalog),
        **narrative.model_dump(),
        notice=FALLBACK_NOTICES[reason] if reason else "Шаблонное объяснение: включён режим mock.",
    )
