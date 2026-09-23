"""Turn known catalog facts and evaluated outcomes into displayable evidence."""

from collections import Counter

from backend.app.services.advice import METRIC_NAMES
from backend.app.services.simulation import leave_one_out
from contracts.schemas import AnalysisEvidence, Catalog, MeasureContribution, ScenarioAlternative, SimulationResult

DIRECTIONS = {
    "transport": "транспорт", "ecology": "экология", "social": "соцсфера",
    "safety": "безопасность", "services": "сервисы",
}


def composition(result: SimulationResult, catalog: Catalog) -> str:
    measures = {m.id: m for m in catalog.measures}
    counts = Counter(measures[effect.measure_id].direction for effect in result.measure_effects)
    return "Выбрано мер по направлениям: " + "; ".join(f"{label} — {counts[key]}" for key, label in DIRECTIONS.items()) + "."


def build_evidence(
    result: SimulationResult,
    catalog: Catalog,
    alternatives: list[ScenarioAlternative] | None = None,
    contributions: list[MeasureContribution] | None = None,
) -> AnalysisEvidence:
    measures = {m.id: m for m in catalog.measures}
    districts = {d.id: d.name for d in catalog.districts}
    def describe(decision):
        measure = measures[decision.measure_id]
        target = districts[decision.district_id] if decision.district_id else "весь город"
        return f"{measure.id} «{measure.name}» ({target})"

    strengths = {}
    contributions = leave_one_out(result, catalog) if contributions is None else contributions
    negative = {}
    for item in contributions:
        text = (
            f"{describe(item.decision)}, {item.cost} ед.: вклад в Score {item.score_contribution:+.2f} "
            f"(leave-one-out: без этой меры {item.score_without:.2f}, с ней {result.score:.2f}). "
            "При исключении меры пересчитаны её синергии, критические штрафы и слабейший район; вклады не суммируются."
        )
        if item.score_contribution > 0:
            strengths[f"contribution_{item.decision.measure_id}"] = text
        elif item.score_contribution < 0:
            negative[f"negative_{item.decision.measure_id}"] = text
    if not strengths:
        strengths["no_positive_contribution"] = "Положительный вклад отдельных мер в Score методом leave-one-out не найден."

    weakest = min(result.districts, key=lambda d: (d.score, d.district_id))
    risks = {}
    for item in result.critical_indicators:
        risks[f"critical_{item.district_id}_{item.metric}"] = f"{districts[item.district_id]}, {item.metric} ({METRIC_NAMES[item.metric]}): {item.value:g} < 40. Этот показатель даёт штраф 1 балл к Score."
    if result.remaining_budget > 10:
        risks["unused_budget"] = (
            f"Неиспользованный бюджет: {result.remaining_budget} из {result.budget} (больше 10). "
            "Это риск недоиспользования ресурсов: остаток не даёт бонуса к Score. "
            "Не нужно тратить его ради расхода — сравните проверенные замены."
        )
    healthy = {d.id for d in catalog.districts if all(v >= catalog.rules.critical_threshold for v in d.indicators.values())}
    critical_districts = {item.district_id for item in result.critical_indicators}
    for item in contributions:
        target = item.decision.district_id
        elsewhere = critical_districts - {target}
        if target in healthy and elsewhere:
            names = ", ".join(districts[d] for d in sorted(elsewhere))
            risks[f"allocation_{item.decision.measure_id}"] = (
                f"Слабое место распределения: {item.cost} ед. на {describe(item.decision)} "
                f"в районе без исходных показателей <40, пока в других районах ({names}) "
                "остаются критические значения. Это компромисс приоритетов, а не отсутствие пользы от меры."
            )
    risks.update(negative)
    mandatory_risk_ids = list(risks)
    risks["weakest_district"] = f"{weakest.name} — один из районов с минимальным баллом {weakest.score:.2f}. В формуле Score минимальный районный балл имеет вес 30%; средневзвешенный по населению — 70%."
    groups = {}
    for effect in result.measure_effects:
        measure = measures[effect.measure_id]
        if measure.lag_quarters:
            groups.setdefault(measure.lag_quarters, []).append(f"{measure.id} «{measure.name}» ({DIRECTIONS[measure.direction]})")
    for lag, names in sorted(groups.items(), reverse=True):
        fraction = (catalog.rules.horizon_quarters - lag) / catalog.rules.horizon_quarters * 100
        risks[f"lag_{lag}"] = f"Лаг {lag} кв. у {len(names)} мер: {'; '.join(sorted(names))}. За горизонт модели реализуется {fraction:g}% полного эффекта каждой из них."
    risks["synthetic_model"] = "Данные и эффекты синтетические: результат нельзя считать прогнозом для реального города."

    recommendations = {}
    for alternative in alternatives or []:
        text = (
            f"Вместо {describe(alternative.removed)} выбрать {describe(alternative.added)}. "
            f"Проверено сервером: Score {result.score:.2f} → {alternative.score:.2f} "
            f"({alternative.score_gain:+.2f} к текущему), стоимость {result.total_cost} → {alternative.total_cost}/100, "
            f"критических показателей {result.critical_count} → {alternative.critical_count}. "
        )
        if alternative.tradeoffs:
            text += "Ухудшения: " + "; ".join(alternative.tradeoffs[:3]) + ". "
            if len(alternative.tradeoffs) > 3:
                text += f"Всего ухудшенных показателей: {len(alternative.tradeoffs)}. "
        else:
            text += "Снижения отдельных показателей относительно текущего сценария нет. "
        recommendations[alternative.id] = text + "Это отдельная альтернатива: не объединяйте её с другими советами без нового расчёта."
    if not recommendations:
        recommendations["search_scope"] = (
            "Перебор всех допустимых замен одного решения не нашёл роста Score. Это не доказывает глобальный оптимум: можно проверить согласованную замену нескольких решений."
            if alternatives is not None else "Альтернативные наборы в этом вызове не рассчитывались. Для конкретного совета нужен повторный анализ через сервер."
        )
    return AnalysisEvidence(strengths=strengths, risks=risks, recommendations=recommendations, mandatory_risk_ids=mandatory_risk_ids)
