# Аким на 5 часов

AI-симулятор городских решений для HackAlem AI, трек Management. Пять решений, бюджет 100, пять синтетических районов, горизонт 8 кварталов.

**Статус:** интегрированы `main` (`a78d56e`) и последние графики FRONTEND (`ffbc4c5`). Работают каталог, валидация, Score, API, dashboard, применение рекомендаций и сохранение одного сценария для локального сравнения. Живой AI в рабочем Docker подтверждён 23.09.2026: `live/provider`, без причины fallback. Для повторения нужен действующий ключ в окружении backend. Публичный деплой и общее хранилище команд пока не выполнены. Фактические проверки — в [статусе деплоя](docs/deployment-status.md).

**Публичный URL:** пока отсутствует. Фактические результаты и препятствия — [статус деплоя](docs/deployment-status.md), [запросы команде](docs/blockers.md).

## Контейнер: запуск за 3 команды

Требуются работающий Docker Desktop с Linux Engine и Compose, Git и доступ к репозиторию. До интеграции последнего OPS-коммита используйте `feat/ops`. Из папки, где ещё нет клона:

```powershell
git clone --branch feat/ops https://github.com/BAITC-Hacks/hack-8385c555-kunnurs.git
cd hack-8385c555-kunnurs
docker compose -f deploy/compose.yaml up -d --build --wait --wait-timeout 90
```

Открыть **http://localhost:8000**. Команда завершается после готовности контейнера, приложение остаётся в Docker. Режим **mock** работает без ключа. Остановка: `docker compose -f deploy/compose.yaml down`. Если порт уже занят прежним `akim-demo`, остановить этот свой контейнер либо выбрать другой `AKIM_PORT` по [инструкции](deploy/README.md). Для **живого AI** используйте конфигурацию live и локальный `.env` из той же инструкции.

## Быстрый запуск

Требуются Python 3.12+ и Node.js 22.12+; OPS-проверки выполнены на Python 3.13.14 и Node.js 24.19.0 в Windows, контейнер — Python 3.12 / Node 22. Выполнять из корня клона.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path frontend/.env.local)) { Copy-Item frontend/.env.example frontend/.env.local }
npm.cmd --prefix frontend ci
.\.venv\Scripts\python.exe scripts/check.py --require-frontend
```

Если окружение или `.env` уже существуют, пропустить их создание/копирование, чтобы сохранить настройки. Для mock ключ не нужен. Для live в корневом `.env` задать `AI_MODE=live`, `OPENAI_API_KEY` и `OPENAI_MODEL=gpt-4.1-mini`. Без ключа или при ошибке провайдера сервер возвращает явный fallback. Настройка: [ai/README.md](ai/README.md). Docker требует передачи `.env` через `--env-file`; файл не входит в образ.

Два отдельных терминала:

```powershell
# Терминал 1, из корня
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Терминал 2, из корня
npm.cmd --prefix frontend run dev
```

Открыть `http://localhost:5173`, API-документация: `http://localhost:8000/docs`. Клиент читает `VITE_API_URL` из `frontend/.env.local`; сервер — `CORS_ORIGINS` из корневого `.env`.

Linux/macOS: создать окружение через `python3 -m venv .venv`, активировать `source .venv/bin/activate`, далее `python -m pip install -r requirements.txt`, `cp .env.example .env`, `cp frontend/.env.example frontend/.env.local`, `npm --prefix frontend ci`. Команды приложения: `python -m uvicorn backend.app.main:app` и `npm --prefix frontend run dev`.

## Проверка

```powershell
.\.venv\Scripts\python.exe scripts/check.py --require-frontend
```

Общая команда запускает основные тесты, OPS mock/fallback, импорт приложения и сборку frontend; серверы не запускаются и личный ключ в тестах не используется. Обёртки: `powershell -File deploy/check.ps1 -Python .venv/Scripts/python.exe` или `bash deploy/check.sh` с активным окружением. Если Windows запрещает `.ps1`, используйте прямую команду Python выше. Без `--require-frontend` сборка пропускается, если frontend-зависимости не установлены.

Полная проверка образа с автоматическим удалением временного контейнера: `python deploy/container_check.py --build --browser` (нужны зависимости Python, Node и Chromium/Edge). Против уже запущенного API: задать `API_URL`, выполнить `python -m pytest tests/e2e --require-api --expected-ai-mode mock -q -p no:cacheprovider`. Без `--require-api` недоступный API даёт SKIP. После публикации: `python deploy/smoke.py <HTTPS-URL> --require-https --expected-ai-mode live`; для первого свежего ответа добавить `--require-provider`. [Подробности](tests/e2e/README.md), [security-отчёт](docs/security-report.md).

Ручное демо: начальный набор уже заполнен примером PDF. Нажать «Рассчитать и получить AI-анализ»: стоимость 95, остаток 5, Score 56.54 (база 52.56), прирост +3.99. Перенести M7 из Нуры в Есиль и повторить — результат изменится. Попробовать дублирование меры или конфликт M4/M7 в одном районе — сервер вернёт объяснение ошибки. Набор дороже 100 блокируется и клиентом, и сервером. В карточках рекомендаций «Применить» заменяет одну меру и пересчитывает полный набор. Победители разных критериев могут совпасть: для примера PDF показаны две уникальные альтернативы.

## Устройство проекта

```text
contracts/    схемы API, JSON-примеры, тесты контракта
backend/      FastAPI, загрузка данных, чистый движок расчёта, тесты
ai/           OpenAI, проверенные факты, кэш, mock/fallback
frontend/     React + Vite, dashboard, графики и сравнение сценариев
data/         исходные синтетические районы и меры
scripts/      проверки и обновление примеров
.githooks/    проверка зон ответственности перед коммитом
tests/e2e/    зона OPS для сквозных тестов
deploy/       зона OPS для развёртывания
docs/         архитектура, результаты проверок, эксплуатация и питч
```

Подробности: [SPEC.md](SPEC.md), [архитектура](docs/architecture.md), [API](contracts/api.md), [задачи команды](TASKS.md), [правила агентов](AGENTS.md), [использование AI](AI_USAGE.md).

Score считает Python по формуле датасета; LLM не определяет стоимость и численные результаты. Каталог неизменен для всех запросов. Сейчас всё работает без базы; SQLite для сохранения и сравнения сценариев — отдельное расширение.

## Раскрытие ранее созданного кода, шаблонов, библиотек и датасетов

Данные вручную перенесены из предоставленных пользователем PDF «Датасет районов» и «HackAlem AI: Аким на 5 часов — AI-симулятор управления городом». Синтетические, без персональных данных; [подробности](data/README.md). Оригиналы PDF не включены. Предыдущие README и учебный Task-7 не используются.

Каркас создан с помощью Codex; внешние шаблоны приложения и заимствованный код не использовались. Использованы FastAPI, Pydantic, Uvicorn, python-dotenv, OpenAI SDK, React, Vite; тесты — pytest и HTTPX. Версии Python-зависимостей закреплены в `requirements.txt`, frontend — в `package-lock.json`. Для разового чтения PDF LEAD использовал pypdf 6.19.0, OPS — встроенный Windows PDF API; приложению они не нужны. SQLAlchemy не используется.

Официальные руководства: [FastAPI / тесты](https://fastapi.tiangolo.com/tutorial/testing/), [Pydantic / модели](https://docs.pydantic.dev/latest/concepts/models/), [Vite](https://vite.dev/guide/).

OPS развивает существующий командный каркас: использованы исходный каталог, схемы и примеры LEAD; чужие шаблоны приложения не добавлялись. Новые Python-зависимости не добавлены; генератор и smoke используют стандартную библиотеку. Контейнер использует официальные образы Node/Python. [Сверка с PDF](docs/data-review.md), [генератор сценариев](data/README.md).

## Как мы использовали AI/Codex

Codex помог подготовить каркас, расчёт, проверки, конфигурацию развёртывания и документацию. Фактические записи: [журнал LEAD](AI_USAGE.md) и [журнал OPS](docs/AI_USAGE.md). Проверки человеком фиксируются только после подтверждения. AI внутри продукта вызывает OpenAI при `AI_MODE=live` и доступном ключе. Конкретный ответ подтверждают `analysis.mode=live` и `analysis.source=provider`; `source=cache` означает сохранённый ответ, mock/fallback — шаблон.

Питч на три минуты — [docs/pitch.md](docs/pitch.md), ручная приёмка — [чек-лист](docs/judges-checklist.md), доступность 24–28.09 и восстановление — [runbook](docs/runbook.md).

## Работа команды

LEAD работает в `main`, FRONTEND в `feat/frontend`, OPS в `feat/ops`. Каждый настраивает собственные `user.name`, `user.email`, `team.role` и `core.hooksPath=.githooks`. Роль LEAD — `lead`, остальные — `frontend` и `ops`. Хук проверяет зоны; качество проверяет `scripts/check.py` перед коммитом. Авторство участников не подменяется.

Требование хакатона: рабочая промежуточная версия в GitHub не реже раза в час. План интеграции — каждые 45 минут; code freeze через 4:15 после фактического старта разработки. Публичный URL должен быть доступен во время проверки 24–28.09; его подготовка закреплена за OPS и пока не выполнена.
