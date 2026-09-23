"""Turn known catalog facts and evaluated outcomes into displayable evidence."""

from collections import Counter

from contracts.schemas import AnalysisEvidence, Catalog, ScenarioAlternative, SimulationResult

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
) -> AnalysisEvidence:
    measures = {m.id: m for m in catalog.measures}
    districts = {d.id: d.name for d in catalog.districts}
    strengths = {}
    for district in sorted(result.districts, key=lambda d: (-d.score_delta, d.district_id)):
        if district.score_delta > 0:
            strengths[f"gain_{district.district_id}"] = f"{district.name}: районный балл вырос на {district.score_delta:.2f} и достиг {district.score:.2f}. Это результат всего набора мер."
    if result.critical_count == 0:
        strengths["no_critical"] = "После выбранных мер ни один показатель районов не находится ниже критического порога 40."
    for synergy in result.applied_synergies:
        pair = " + ".join(synergy.measures)
        effects = ", ".join(f"{metric} {value:+g}" for metric, value in synergy.effects.items())
        strengths[f"synergy_{'_'.join(synergy.measures)}"] = f"Синергия {pair} в районе {districts[synergy.district_id]}: фиксированный бонус {effects} до ограничения показателей диапазоном 0–100; лаг его не уменьшает."
    if not strengths:
        strengths["valid_budget"] = f"Сценарий допустим и укладывается в бюджет: {result.total_cost} из {result.budget}."

    weakest = min(result.districts, key=lambda d: (d.score, d.district_id))
    risks = {"weakest_district": f"{weakest.name} — один из районов с минимальным баллом {weakest.score:.2f}. В формуле Score минимальный районный балл имеет вес 30%; средневзвешенный по населению — 70%."}
    for item in result.critical_indicators:
        risks[f"critical_{item.district_id}_{item.metric}"] = f"{districts[item.district_id]}, {item.metric}: {item.value:g} < 40. Этот показатель даёт штраф 1 балл к Score."
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
        def describe(decision):
            measure = measures[decision.measure_id]
            target = districts[decision.district_id] if decision.district_id else "весь город"
            return f"{measure.id} «{measure.name}» ({target})"

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
    return AnalysisEvidence(strengths=strengths, risks=risks, recommendations=recommendations)
