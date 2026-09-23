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

`analysis.mode`: `mock` — явно выбранный шаблон; `live` — проверенный ответ LLM или его кэш; `fallback` — живой провайдер недоступен/ответ не прошёл проверку. Всегда отображать `notice`. Режим не влияет на Score.

Новые обратно совместимые поля: `analysis.source` = `provider` / `cache` / `template` (default `template`); `analysis.reason` = код причины fallback или `null`. Коды: `missing_api_key`, `invalid_configuration`, `timeout`, `connection_error`, `authentication_error`, `permission_error`, `rate_limit`, `provider_error`, `invalid_output`. Внутренние ошибки/ключи в ответ не попадают. Fallback — HTTP 200 с корректным рассчитанным `result`; невалидный сценарий по-прежнему 422 и не вызывает AI.

`/api/health.ai_mode` показывает готовность конфигурации: `live`, если выбран live, настройки валидны и ключ заполнен. Health не вызывает провайдера и не доказывает доступность модели или наличие квоты. Фактический режим конкретного запроса смотреть в `analysis.mode`.

AI получает результат расчёта, выбранные меры, правила, конфликты и каталог фактов/советов. Провайдерная схема `AISelection` содержит только `strength_ids`, `risk_ids`, `recommendation_ids`. Каждый ID должен существовать в соответствующей категории и не повторяться. Произвольный текст модели не показывается: списки analysis и числовую сводку отрисовывает сервер. `AINarrative` теперь внутренний контейнер отрисованного текста. Направления и лаги считаются отдельно. Инструкции и настройка: `ai/README.md`.

`AnalysisResponse.alternatives` — новый необязательный массив (по умолчанию `[]`) из максимум трёх независимых замен одного решения. Поля: `id`, `removed`, `added` (Decision), `scenario` (полный ScenarioRequest), `score`, `score_gain` к текущему сценарию, `total_cost`, `remaining_budget`, `critical_count`, `tradeoffs` (все ухудшения показателей относительно текущего набора). Каждый вариант проходит обычную валидацию и расчёт; `score_gain>0`. Порядок: убывание прироста, возрастание стоимости, затем ID. В текстовом совете показаны первые три ухудшения и их полное количество, если их больше.

Чтобы применить вариант, пользователь выбирает его, клиент подставляет `scenario.decisions` и отправляет обычный POST. Ничего автоматически не сохраняется и не выполняется. Несколько альтернатив не комбинировать без нового расчёта. Пустой массив означает, что среди всех замен одного решения роста Score не найдено, а не доказательство глобального оптимума. Результат совета из `examples/analysis.json` можно воспроизвести через `/evaluate`. Кэш учитывает весь набор фактов и альтернатив и новую версию промпта.

Изменения контракта согласовывает LEAD. Добавлять совместимые необязательные поля; одновременно обновлять схемы, API-документ, примеры и тесты. FRONTEND и OPS не редактируют контракт самостоятельно.
