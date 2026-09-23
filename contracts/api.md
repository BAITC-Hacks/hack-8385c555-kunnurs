# API v1

JSON UTF-8. Базовый URL локально `http://localhost:8000`. Типы определяет `schemas.py`, живой OpenAPI находится в `/openapi.json`, Swagger UI — `/docs`.

| Метод | Путь | Запрос | Ответ 200 | Ошибки |
|---|---|---|---|---|
| GET | `/api/health` | — | `HealthResponse`, `examples/health.json` | Недоступность API/данных |
| GET | `/api/catalog` | — | `Catalog`, `examples/catalog.json` | Недоступность данных |
| GET | `/api/baseline` | — | `SimulationResult`, `examples/baseline.json` | Недоступность данных |
| POST | `/api/simulations/evaluate` | `ScenarioRequest` | `SimulationResult`, `examples/evaluation.json` | 422 `ErrorResponse` |
| POST | `/api/simulations/analyze` | `ScenarioRequest` | `AnalysisResponse`, `examples/analysis.json` | 422 `ErrorResponse` |

`GET /baseline` описывает старт до решений; отправить пустой набор как сценарий нельзя. `/analyze` заново проверяет и рассчитывает набор на сервере, затем добавляет объяснение; клиент не может подменить Score.

Пример запроса (`examples/scenario.json`):

```json
{"decisions":[{"measure_id":"M7","district_id":"nura"},{"measure_id":"M8","district_id":"nura"},{"measure_id":"M10","district_id":"nura"},{"measure_id":"M12"},{"measure_id":"M5","district_id":"saryarka"}]}
```

Районы: `esil`, `almaty`, `saryarka`, `baikonur`, `nura`. Городские меры: M2, M6, M12, M14. `district_id` у них отсутствует или равен `null`. Направления: `transport`, `ecology`, `social`, `safety`, `services`.

В ответе расчёта: бюджет/стоимость/остаток, базовый и конечный Score, изменение, средний и минимальный районный балл, критические показатели, значения и дельты по районам, реализованные эффекты мер и отдельные синергии. Значения `measure_effects.effects` даны до clip, поэтому не всегда равны фактическому приращению у границ 0/100. Нелинейный Score не раскладывается в простую сумму вкладов.

Числа не округляются в промежуточных вычислениях; итоговые баллы API имеют до 6 знаков, UI показывает 2. Состояние исходного каталога не изменяется между запросами.

Бизнес-ошибка:

```json
{"error":{"code":"invalid_scenario","message":"Набор решений не прошёл проверку.","issues":[{"code":"decision_count","message":"Нужно выбрать ровно 5 мероприятий."}]}}
```

Коды причин: `decision_count`, `duplicate_measure`, `unknown_measure`, `invalid_district`, `city_has_district`, `budget_exceeded`, `direction_limit`, `incompatible_measures`. Нарушение JSON-схемы: `error.code=invalid_request`, причина `schema_validation`. У ошибки нет поля `score`.

`analysis.mode`: `mock` — шаблон; `live` зарезервирован для настоящего LLM; `fallback` — живой провайдер недоступен/ещё не реализован. Отображать `notice` пользователю. Сейчас `AI_MODE=live` явно возвращает fallback и не делает сетевых запросов. Режим никогда не влияет на Score.

Изменения контракта согласовывает LEAD. Добавлять совместимые необязательные поля; одновременно обновлять схемы, API-документ, примеры и тесты. FRONTEND и OPS не редактируют контракт самостоятельно.
