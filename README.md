# Аким на 5 часов

AI-симулятор городских решений для HackAlem AI, трек Management. Пять решений, бюджет 100, пять синтетических районов, горизонт 8 кварталов.

**Статус:** каталог, валидация, расчёт Score, HTTP API и React-интерфейс работают локально. OPS проверил Docker-образ, 32 основных теста, 79 OPS-тестов в процессе и 79 против контейнера, 31 проверку fallback, сборку frontend и браузерное демо. Объяснение явно обозначено как mock. Живой LLM, публичный деплой и сохранение сценариев пока не реализованы.

**Публичный URL:** пока отсутствует. Фактические результаты и препятствия — [статус деплоя](docs/deployment-status.md), [запросы команде](docs/blockers.md).

## Контейнер: запуск за 3 команды

Требуется установленный и запущенный Docker с Linux Engine, Git и доступ к репозиторию. Выполнить из родительской папки, где ещё нет клона, после публикации OPS-изменений и интеграции в main:

```powershell
git clone https://github.com/BAITC-Hacks/hack-8385c555-kunnurs.git
docker build -f hack-8385c555-kunnurs/deploy/Dockerfile -t akim-city:demo hack-8385c555-kunnurs
docker run --rm --name akim-city -p 8000:8000 -e AI_MODE=mock akim-city:demo
```

Открыть `http://localhost:8000`. Последняя команда работает в отдельном терминале человека, остановка Ctrl+C. Образ собирает frontend и отдаёт его вместе с API; ключ для mock не нужен. Сборка и работа контейнера проверены 23.09.2026. [Деплой, env и диагностика](deploy/README.md).

## Быстрый запуск

Требуются Python 3.12+ и Node.js 22.12+; каркас проверен на Python 3.14.0 и Node.js 24.14.0 в Windows. Выполнять из корня клона командного репозитория.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env.local
npm.cmd --prefix frontend ci
.\.venv\Scripts\python.exe scripts/check.py --require-frontend
```

Если окружение или `.env` уже существуют, пропустить их создание/копирование, чтобы сохранить настройки. Для mock ключ не нужен. `AI_MODE=live` сейчас выдаёт явно обозначенный fallback; наличие API-ключа само по себе не включает LLM.

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

Альтернативы: `powershell -File scripts/check.ps1 --require-frontend` или `bash scripts/check.sh --require-frontend`. Проверка запускает pytest, проверяет импорт приложения и собирает frontend; серверы не запускаются. Без `--require-frontend` сборка пропускается, если зависимости frontend не установлены, и это явно выводится.

OPS-проверки без слушающего сервера: `powershell -File deploy/check.ps1 -Python .venv/Scripts/python.exe`. Linux/macOS с активированным окружением: `bash deploy/check.sh`. Против уже запущенного API: задать `API_URL` и выполнить `python -m pytest tests/e2e -q -rs -p no:cacheprovider`. Недоступный API даёт SKIP, что не считается успешной проверкой релиза. После деплоя: `python deploy/smoke.py <HTTPS-URL> --require-https --expected-ai-mode mock`. [Подробности тестов](tests/e2e/README.md), [security-отчёт](docs/security-report.md).

Ручное демо: начальный набор уже заполнен примером PDF. Нажать «Рассчитать сценарий»: стоимость 95, остаток 5, Score 56.54 (база 52.56), прирост +3.99. Перенести M7 из Нуры в Есиль и повторить — результат изменится. Попробовать дублирование меры или конфликт M4/M7 в одном районе — сервер вернёт объяснение ошибки. Набор дороже 100 блокируется и клиентом, и сервером.

## Устройство проекта

```text
contracts/    схемы API, JSON-примеры, тесты контракта
backend/      FastAPI, загрузка данных, чистый движок расчёта, тесты
ai/           граница AI-адаптера, сейчас mock
frontend/     React + Vite, стартовый интерфейс
data/         исходные синтетические районы и меры
scripts/      проверки и обновление примеров
.githooks/    проверка зон ответственности перед коммитом
tests/e2e/    зона OPS для сквозных тестов
deploy/       зона OPS для развёртывания
docs/         архитектура и будущая эксплуатационная документация
```

Подробности: [SPEC.md](SPEC.md), [архитектура](docs/architecture.md), [API](contracts/api.md), [задачи команды](TASKS.md), [правила агентов](AGENTS.md), [использование AI](AI_USAGE.md).

Score считает Python по формуле датасета; LLM не определяет стоимость и численные результаты. Каталог неизменен для всех запросов. Сейчас всё работает без базы; SQLite для сохранения и сравнения сценариев — отдельное расширение.

## Раскрытие ранее созданного кода, шаблонов, библиотек и датасетов

Данные вручную перенесены из предоставленных пользователем PDF «Датасет районов» и «HackAlem AI: Аким на 5 часов — AI-симулятор управления городом». Синтетические, без персональных данных; [подробности](data/README.md). Оригиналы PDF не включены. Предыдущие README и учебный Task-7 не используются.

Каркас создан с помощью Codex; внешние шаблоны приложения и заимствованный код не использовались. Использованы библиотеки FastAPI, Pydantic, Uvicorn, python-dotenv, React, Vite; тесты — pytest и HTTPX. Версии Python-зависимостей закреплены в `requirements.txt`, frontend — в `package-lock.json`. Для разового чтения PDF использовался pypdf 6.19.0; приложению он не нужен. OpenAI SDK и SQLAlchemy будут добавлены при реализации соответствующих этапов.

Официальные руководства: [FastAPI / тесты](https://fastapi.tiangolo.com/tutorial/testing/), [Pydantic / модели](https://docs.pydantic.dev/latest/concepts/models/), [Vite](https://vite.dev/guide/).

OPS развивает существующий командный каркас: использованы исходный каталог, схемы и примеры LEAD; чужие шаблоны приложения не добавлялись. Новые Python-зависимости не добавлены; генератор и smoke используют стандартную библиотеку. Контейнер использует официальные образы Node/Python. [Сверка с PDF](docs/data-review.md), [генератор сценариев](data/README.md).

## Как мы использовали AI/Codex

Codex помог подготовить каркас, расчёт, проверки, конфигурацию развёртывания и документацию. Фактические записи: [журнал LEAD](AI_USAGE.md) и [журнал OPS](docs/AI_USAGE.md). Проверки человеком фиксируются только после подтверждения. Использование Codex при разработке отдельно от AI внутри продукта: текущий runtime-адаптер выдаёт mock/fallback, а настоящий LLM-анализ ещё нужен для финального критерия.

Питч на три минуты — [docs/pitch.md](docs/pitch.md), ручная приёмка — [чек-лист](docs/judges-checklist.md), доступность 24–28.09 и восстановление — [runbook](docs/runbook.md).

## Работа команды

LEAD работает в `main`, FRONTEND в `feat/frontend`, OPS в `feat/ops`. Каждый настраивает собственные `user.name`, `user.email`, `team.role` и `core.hooksPath=.githooks`. Роль LEAD — `lead`, остальные — `frontend` и `ops`. Хук проверяет зоны; качество проверяет `scripts/check.py` перед коммитом. Авторство участников не подменяется.

Требование хакатона: рабочая промежуточная версия в GitHub не реже раза в час. План интеграции — каждые 45 минут; code freeze через 4:15 после фактического старта разработки. Публичный URL должен быть доступен во время проверки 24–28.09; его подготовка закреплена за OPS и пока не выполнена.
