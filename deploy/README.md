# Сборка и публикация

Один Docker-образ: Node собирает React/Vite, Python запускает FastAPI API и статику через `deploy.app:create_app`. Образ собран и проверен локально 23.09.2026: health, smoke, 79 pytest-проверок и браузерное демо успешны. Публичный URL пока не получен. Фактический статус — [deployment-status.md](../docs/deployment-status.md).

## Локальный контейнер

Docker Desktop должен работать в режиме Linux containers. Команды выполняет человек из корня репозитория:

```powershell
docker build -f deploy/Dockerfile -t akim-city:ops .
docker run --rm --name akim-city -p 8000:8000 -e AI_MODE=mock akim-city:ops
```

Вторую команду держать в отдельном терминале. Открыть `http://localhost:8000`, Swagger — `/docs`, health — `/api/health`. Остановка: Ctrl+C. Локальная `.env` в образ не включается. Постоянный диск приложению не нужен.

В другом терминале, если Python и зависимости доступны:

```powershell
python deploy/smoke.py http://127.0.0.1:8000 --expected-ai-mode mock
$env:API_URL = 'http://127.0.0.1:8000'
python -m pytest tests/e2e -q -rs -p no:cacheprovider
```

`smoke.py` использует стандартную библиотеку. Проверяет HTML, JS/CSS, пять API, контрольные числа и режим AI; недоступность означает ненулевой exit code. Это конечная проверка, не мониторинг и не браузерный тест.

## Состав образа

`deploy/Dockerfile.dockerignore` разрешает нужные файлы и исключает `.env*`, Git, IDE, локальные зависимости, ключи и Python-кэш. Поддержку файла рядом с Dockerfile описывает [Docker build context](https://docs.docker.com/build/concepts/context/). Обязательно указывать `-f deploy/Dockerfile`.

Контейнер работает под UID 10001. Uvicorn access-log отключён; логи внешнего прокси регулируются хостингом. Python-пакеты берутся из существующего `requirements.txt`, JS — из `package-lock.json`. Базовые образы закреплены по ветке версии, не по digest: побайтовая идентичность сборок не гарантируется.

## Переменные окружения

| Имя | Этап | Назначение |
|---|---|---|
| `AI_MODE` | Запуск | `mock` по умолчанию; сейчас `live` возвращает явный `fallback` |
| `PORT` | Запуск | Порт платформы, иначе 8000; слушает `0.0.0.0` |
| `CORS_ORIGINS` | Запуск | Пустое значение для единого origin; при отдельном frontend — точный HTTPS origin без `*` |
| `VITE_API_URL` | Сборка | В Dockerfile `/`, запросы на текущий origin. Пустое значение в текущем frontend включает localhost |
| `FRONTEND_DIST` | Запуск | Необязательный путь статики, по умолчанию `/app/frontend/dist` |
| `OPENAI_API_KEY` | Запуск | Только секрет платформы после live-интеграции LEAD; никогда build arg или `VITE_*` |
| `OPENAI_MODEL` | Запуск | Будет использован после реализации провайдера; модель согласует LEAD |

`DATABASE_URL` текущему приложению не нужен. Ключ сам по себе не включает LLM.

## Render

1. Войти своим аккаунтом и дать Render доступ к командному GitHub-репозиторию. Выбрать ветку с OPS-коммитом, для финального релиза — интегрированный `main`.
2. Создать Blueprint с путём `deploy/render.yaml`. Альтернатива: Web Service, Docker runtime, build context `.`, Dockerfile `deploy/Dockerfile`, план Free.
3. Установить health path `/api/health`, оставить команду запуска Dockerfile, `AI_MODE=mock` и пустой `CORS_ORIGINS`.
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
python -m pytest tests/e2e -q -rs -p no:cacheprovider
```

После подключения живой LLM ожидать `live`: fallback тогда даст FAIL. Успех mock подтверждает доступность и расчёт, не обязательный критерий AI.

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
| Live даёт fallback | Провайдер пока не реализован; BLOCKER LEAD |
| Free-сервис долго открывается | Дождаться холодного старта, повторить smoke, проверить лимиты |

Восстановление и график: [runbook.md](../docs/runbook.md).
