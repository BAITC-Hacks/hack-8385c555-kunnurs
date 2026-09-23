"""Offline explanation stub with a stable interface for the later live adapter."""

from collections.abc import Callable, Mapping

from contracts.schemas import Analysis, Catalog, SimulationResult


def explain_scenario(
    result: SimulationResult,
    catalog: Catalog,
    *,
    mode: str = "mock",
    tools: Mapping[str, Callable] | None = None,
) -> Analysis:
    # Live Responses API integration is a separate TASKS.md item.
    # Tools are reserved for a read-only allowlist; the stub executes none.
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
        mode="mock" if mode == "mock" else "fallback",
        summary=f"Score {result.score:.2f} ({result.score_delta:+.2f} к базе). Использовано {result.total_cost} из {result.budget} единиц бюджета.",
        strengths=[f"Наибольший прирост районного балла: {strongest_gain.name} ({strongest_gain.score_delta:+.2f}).", f"Сработало синергий: {len(result.applied_synergies)}."],
        risks=risks,
        recommendations=[f"Сравните альтернативы для района {weakest.name}: он определяет 30% итогового Score.", "Проверяйте каждый альтернативный набор расчётом; остаток бюджета бонуса не даёт."],
        notice="Шаблонное объяснение. LLM ещё не подключена." if mode == "mock" else "Запрошен live-режим, но провайдер ещё не реализован. Использовано шаблонное объяснение.",
    )
