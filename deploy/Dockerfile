# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src
# api.js falls back to localhost for an empty value. A slash is truthy,
# then its trailing slash is removed, producing same-origin /api requests.
ENV VITE_API_URL=/
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_MODE=mock \
    CORS_ORIGINS="" \
    PORT=8000
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app
COPY backend ./backend
COPY ai ./ai
COPY contracts ./contracts
COPY data/city.json ./data/city.json
COPY deploy/app.py deploy/healthcheck.py ./deploy/
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "deploy/healthcheck.py"]
CMD ["sh", "-c", "exec python -m uvicorn deploy.app:create_app --factory --host 0.0.0.0 --port \"${PORT:-8000}\" --no-access-log"]
