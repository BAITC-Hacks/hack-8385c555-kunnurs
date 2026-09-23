"""OpenAI explanation adapter. Scores and numeric summaries stay server-owned."""

import asyncio
import hashlib
import json
import logging
import re
from collections.abc import Callable, Mapping

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from ai import cache
from ai.privacy import redact
from ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from ai.settings import AISettings
from contracts.schemas import AINarrative, Analysis, Catalog, SimulationResult

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


def _summary(result: SimulationResult) -> str:
    return f"Score {result.score:.2f} ({result.score_delta:+.2f} к базе). Использовано {result.total_cost} из {result.budget} единиц бюджета."


def _payload(result: SimulationResult, catalog: Catalog) -> str:
    selected = {effect.measure_id for effect in result.measure_effects}
    data = {
        "result": result.model_dump(mode="json"),
        "rules": catalog.rules.model_dump(),
        "selected_measures": [m.model_dump(mode="json") for m in catalog.measures if m.id in selected],
        "conflicts": [c.model_dump(mode="json") for c in catalog.conflicts],
    }
    return json.dumps(redact(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_narrative(narrative: AINarrative) -> AINarrative:
    # Fail closed on generated numeric claims; the UI already shows trusted numbers.
    for sentence in [*narrative.strengths, *narrative.risks, *narrative.recommendations]:
        if not sentence.strip() or re.search(r"\d", sentence):
            raise ValueError("invalid_output")
    return AINarrative.model_validate(redact(narrative.model_dump()))


async def _request_narrative(settings: AISettings, payload: str) -> AINarrative:
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
                text_format=AINarrative,
                max_output_tokens=750,
                store=False,
            )
            if response.status != "completed" or response.output_parsed is None:
                raise ValueError("invalid_output")
            return _validate_narrative(response.output_parsed)


def _live(result: SimulationResult, catalog: Catalog) -> Analysis:
    try:
        settings = AISettings.from_env()
    except ValidationError:
        return _template(result, reason="invalid_configuration")
    if not settings.api_key.get_secret_value():
        return _template(result, reason="missing_api_key")
    payload = _payload(result, catalog)
    key = hashlib.sha256(f"{PROMPT_VERSION}\n{settings.model}\n{payload}".encode()).hexdigest()
    narrative = cache.get(key) if settings.cache_enabled else None
    source = "cache" if narrative is not None else "provider"
    if narrative is None:
        try:
            narrative = asyncio.run(_request_narrative(settings, payload))
        except (TimeoutError, APITimeoutError):
            return _template(result, reason="timeout")
        except APIConnectionError:
            return _template(result, reason="connection_error")
        except APIStatusError as exc:
            reason = {401: "authentication_error", 403: "permission_error", 404: "permission_error", 429: "rate_limit"}.get(exc.status_code, "provider_error")
            return _template(result, reason=reason)
        except OpenAIError:
            return _template(result, reason="provider_error")
        except (ValidationError, ValueError):
            return _template(result, reason="invalid_output")
        if settings.cache_enabled:
            cache.put(key, narrative)
    return Analysis(
        mode="live", source=source, summary=_summary(result), **narrative.model_dump(),
        notice="AI-разбор по рассчитанным показателям. Рекомендации требуют проверки симулятором." if source == "provider" else "Сохранённый AI-разбор этого сценария. Рекомендации требуют проверки симулятором.",
    )


def explain_scenario(
    result: SimulationResult,
    catalog: Catalog,
    *,
    mode: str = "mock",
    tools: Mapping[str, Callable] | None = None,
) -> Analysis:
    # No tool declarations are sent to the model. Arbitrary callbacks are never run.
    if mode == "live":
        return _live(result, catalog)
    return _template(result)


def _template(result: SimulationResult, reason: str | None = None) -> Analysis:
    if reason:
        # Only a fixed reason code is logged, never exception bodies, prompts or keys.
        logger.warning("ai_fallback reason=%s", reason)
    weakest = min(result.districts, key=lambda d: d.score)
    strongest_gain = max(result.districts, key=lambda d: d.score_delta)
    risks = ["Модель синтетическая: результат не является прогнозом для реального города."]
    if result.critical_count:
        risks.append(f"Осталось критических показателей: {result.critical_count}; каждый уменьшает Score на 1.")
    else:
        risks.append("Критических значений ниже 40 нет, но это не означает отсутствия городских проблем.")
    if any(effect.realized_fraction < 1 for effect in result.measure_effects):
        risks.append("За 8 кварталов реализуется только часть полного эффекта мер из-за лага.")
    return Analysis(
        mode="fallback" if reason else "mock", source="template", reason=reason,
        summary=_summary(result),
        strengths=[f"Наибольший прирост районного балла: {strongest_gain.name} ({strongest_gain.score_delta:+.2f}).", f"Сработало синергий: {len(result.applied_synergies)}."],
        risks=risks,
        recommendations=[f"Сравните альтернативы для района {weakest.name}: он определяет 30% итогового Score.", "Проверяйте каждый альтернативный набор расчётом; остаток бюджета бонуса не даёт."],
        notice=FALLBACK_NOTICES[reason] if reason else "Шаблонное объяснение: включён режим mock.",
    )
