# Сборка и публикация

Один Docker-образ: Node собирает React/Vite, Python запускает FastAPI API и статику через `deploy.app:create_app`. Ветка OPS включает live AI из main. Публичный URL пока не получен. Ревизии и результаты проверок — [deployment-status.md](../docs/deployment-status.md).

## Локальный контейнер

Docker Desktop должен работать в режиме Linux containers. Основной способ из корня репозитория:

```powershell
docker compose -f deploy/compose.yaml up -d --build --wait --wait-timeout 90
```

Открыть `http://localhost:8000`, Swagger — `/docs`, health — `/api/health`. Эта конфигурация явно включает mock и не передаёт `.env` в контейнер. Повтор команды обновляет изменённый образ. Состояние: `docker compose -f deploy/compose.yaml ps`; остановка: `docker compose -f deploy/compose.yaml down`.

Если порт занят, в PowerShell задать `$env:AKIM_PORT = '8002'`, повторить команду и открыть `http://localhost:8002`. Linux/macOS: `AKIM_PORT=8002 docker compose -f deploy/compose.yaml up -d --build --wait`. Compose создаёт отдельный проект `akim-city`; он не управляет старым контейнером `akim-demo`.

Compose ограничивает прослушивание localhost, запускает процесс от UID 10001 с read-only файловой системой и временной `/tmp`, без Linux capabilities и повышения привилегий. Логи ограничены двумя файлами по 5 MB. Постоянный диск MVP не нужен. Формат: [Docker Compose services](https://docs.docker.com/reference/compose-file/services/).

### Живой AI локально

Создать корневой `.env` из `.env.example`, если его ещё нет; заполнить `OPENAI_API_KEY`, оставить `AI_MODE=live` и `OPENAI_MODEL=gpt-4.1-mini` либо модель, согласованную с LEAD. Не перезаписывать существующий файл. Затем:

```powershell
docker compose -f deploy/compose.yaml -f deploy/compose.live.yaml up -d --build --force-recreate --wait --wait-timeout 90
python deploy/smoke.py http://127.0.0.1:8000 --expected-ai-mode live --require-provider
```

Вторую команду выполнить до первого анализа в браузере: повторный сценарий может вернуться из кэша. `--require-provider` требует свежий ответ модели; обычная проверка live принимает и `source=cache`. Health проверяет конфигурацию, но не доступ модели/квоту. После изменения ключа повторить команду с `--force-recreate`: обычный restart окружение не перечитывает. Без ключа будет `fallback / missing_api_key`. Compose live читает `.env` только при запуске; файл не включается в образ.

В этой локальной конфигурации внутренний `PORT=8000` и пустой `CORS_ORIGINS` заданы явно; внешний порт выбирается `AKIM_PORT`. Не выводить результат `docker compose ... config` с live-секретами; для проверки формата используйте `config --quiet`.

### Сборка без Compose

```powershell
docker build -f deploy/Dockerfile -t akim-city:ops .
docker run --rm --name akim-city -p 127.0.0.1:8000:8000 -e AI_MODE=mock akim-city:ops
```

Последняя команда остаётся в терминале до Ctrl+C. Для live передать `--env-file .env -e AI_MODE=live`. После изменения `.env` остановить старый контейнер и создать новый. Не запускать одновременно два контейнера на одном порту.

В другом терминале, если Python и зависимости доступны:

```powershell
python deploy/smoke.py http://127.0.0.1:8000 --expected-ai-mode mock
$env:API_URL = 'http://127.0.0.1:8000'
python -m pytest tests/e2e --require-api --expected-ai-mode mock -q -p no:cacheprovider
```

`smoke.py` использует стандартную библиотеку. Проверяет HTML, JS/CSS, пять API, базу 52.55768, пример 56.54307, школу в Есиле 55.29777, пересчитывает альтернативы, проверяет 422 и закрытые `.env`/`.git`. Недоступность означает ненулевой exit code. JSON содержит безопасные `stage`/`code` и режим/источник/причину AI, без сырого текста ошибки провайдера. `--wait-seconds 30` ждёт запуска health; анализ не повторяется автоматически. `--output <file.json>` сохраняет отчёт. Редиректы запрещены, HTTP-прокси из окружения не используются.

Конечная проверка всего образа:

```powershell
python deploy/container_check.py --build --browser
python deploy/container_check.py --mode fallback --browser
```

Создаёт уникальный временный контейнер на свободном localhost-порту, проверяет smoke, UID/упаковку, запускает pytest и при `--browser` — headless Chromium. Контейнер удаляется в `finally`; обычные контейнеры проекта не затрагиваются. Образ остаётся `akim-city:ops-check`. Ключи не передаются. Нужны Python-зависимости; для браузера — Node и Edge/Chromium. Подробности: [tests/e2e](../tests/e2e/README.md).

## Состав образа

`deploy/Dockerfile.dockerignore` разрешает нужные файлы и исключает `.env*`, Git, IDE, локальные зависимости, ключи и Python-кэш. Поддержку файла рядом с Dockerfile описывает [Docker build context](https://docs.docker.com/build/concepts/context/). Обязательно указывать `-f deploy/Dockerfile`.

Контейнер работает под UID 10001. Uvicorn access-log отключён; логи внешнего прокси регулируются хостингом. Python-пакеты берутся из существующего `requirements.txt`, JS — из `package-lock.json`. Базовые образы закреплены по ветке версии, не по digest: побайтовая идентичность сборок не гарантируется.

## Переменные окружения

| Имя | Этап | Назначение |
|---|---|---|
| `AI_MODE` | Запуск | В образе по умолчанию `mock`; для провайдера явно задать `live` |
| `PORT` | Запуск | Порт платформы, иначе 8000; слушает `0.0.0.0` |
| `CORS_ORIGINS` | Запуск | Пустое значение для единого origin; при отдельном frontend — точный HTTPS origin без `*` |
| `VITE_API_URL` | Сборка | В Dockerfile `/`, запросы на текущий origin. Пустое значение в текущем frontend включает localhost |
| `FRONTEND_DIST` | Запуск | Необязательный путь статики, по умолчанию `/app/frontend/dist` |
| `OPENAI_API_KEY` | Запуск | Секрет платформы или локальный `--env-file .env`; никогда build arg или `VITE_*` |
| `OPENAI_MODEL` | Запуск | По умолчанию `gpt-4.1-mini`; модель и доступ согласует LEAD |
| `AI_TIMEOUT_SECONDS` | Запуск | Общий deadline, по умолчанию и максимум 12 секунд |
| `AI_REQUEST_TIMEOUT_SECONDS` | Запуск | Deadline попытки, по умолчанию и максимум 12 секунд |
| `AI_CACHE_ENABLED` | Запуск | По умолчанию `true`; успешные ответы кэшируются в памяти |

`DATABASE_URL` текущему приложению не нужен. Ключ сам по себе не включает LLM.

## Render

1. Войти своим аккаунтом и дать Render доступ к командному GitHub-репозиторию. Выбрать ветку с OPS-коммитом, для финального релиза — интегрированный `main`.
2. Создать Blueprint с путём `deploy/render.yaml`. Альтернатива: Web Service, Docker runtime, build context `.`, Dockerfile `deploy/Dockerfile`, план Free.
3. Установить health path `/api/health`, оставить команду запуска Dockerfile и пустой `CORS_ORIGINS`. Blueprint стартует в mock. Для финального live задать `AI_MODE=live`, секрет `OPENAI_API_KEY` и `OPENAI_MODEL` в настройках сервиса.
4. Выполнить deploy, дождаться сборки и health-check. Скопировать фактически выданный HTTPS URL.
5. Выполнить приёмку ниже; записать URL и commit в `docs/deployment-status.md` и README. Автодеплой в Blueprint выключен, следующие релизы запускать после проверок.

Поля конфигурации: [Render Blueprint reference](https://render.com/docs/blueprint-spec). Free-сервис засыпает после 15 минут без входящих запросов; холодный старт задерживает открытие. Бесплатный план не подтверждает непрерывную доступность без задержек 24–28.09. Ограничение согласовать с командой; платный план автоматически не включать. Источник: [Render Free](https://render.com/docs/free).

## Railway

1. Подключить свой аккаунт и репозиторий, выбрать нужную ветку. Root directory — корень репозитория.
2. В настройках сервиса задать `RAILWAY_DOCKERFILE_PATH=deploy/Dockerfile`, health path `/api/health`, health timeout 120 секунд и restart on failure. Команду запуска оставить из образа.
3. Задать `AI_MODE=mock`, пустой `CORS_ORIGINS`; порт берётся из предоставленного `PORT`.
4. Выполнить deploy, сгенерировать публичный домен в Networking и пройти приёмку.

Для нового сервиса не полагаться на `railway.json`: актуальная документация помечает Config as Code устаревшим и недоступным новым сервисам. Здесь описана настройка через Dashboard. Источники: [Dockerfiles](https://docs.railway.com/guides/dockerfiles), [Config as code](https://docs.railway.com/config-as-code), [тарифы](https://docs.railway.com/pricing/plans). Достаточность бесплатных ресурсов/кредитов на 24–28.09 проверить в аккаунте; платный тариф требует решения владельца.

## Приёмка публичного релиза

Подставить фактически выданный URL:

```powershell
python deploy/smoke.py https://YOUR-SERVICE.onrender.com --require-https --expected-ai-mode mock
$env:API_URL = 'https://YOUR-SERVICE.onrender.com'
python -m pytest tests/e2e --require-api --expected-ai-mode mock -q -p no:cacheprovider
```

Для финального live заменить `mock` на `live` в обеих командах: fallback тогда даст FAIL. Первый smoke после перезапуска выполнить с `--require-provider`, до браузерных запросов. Успех mock подтверждает доступность и расчёт, не обязательный критерий AI. Удалённые live-тесты могут расходовать квоту.

В браузере из другой сети: пример 95 / 56.54 / +3.99, затем M7 в Есиле и другой Score. В DevTools `/api/*` должен идти на публичный origin без localhost, CORS и mixed-content ошибок. Полный [чек-лист](../docs/judges-checklist.md).

## Диагностика

| Симптом | Действие |
|---|---|
| Нет `dockerDesktopLinuxEngine` | Запустить Docker Desktop, дождаться Linux Engine |
| Ошибка `pip install` / `npm ci` | Сохранить пакет и ошибку без секретов; DEPENDENCY_REQUEST LEAD; версии не менять самостоятельно |
| `Build the frontend before starting...` | Проверить frontend-build и копирование `dist` |
| Запросы к localhost | Пересобрать образ с `VITE_API_URL=/`; runtime env не изменяет готовый JS |
| 502 / failed health | Проверить `0.0.0.0:$PORT`, start command, каталог данных |
| 422 | Прочитать `error.issues`, сверить IDs/бюджет/конфликты |
| Live даёт fallback | Проверить `analysis.reason`: missing_api_key — передать ключ; authentication_error — заменить ключ; permission_error — доступ модели; rate_limit — квота/лимиты; timeout/connection_error — сеть; invalid_configuration — настройки |
| Free-сервис долго открывается | Дождаться холодного старта, повторить smoke, проверить лимиты |

Восстановление и график: [runbook.md](../docs/runbook.md).
