# CosmosPeaceForum public social platform image
# Builds the React frontend and serves the API, uploads, and SPA from FastAPI.

FROM node:24-alpine AS frontend-builder

WORKDIR /app/social_platform/frontend

ENV HUSKY=0

RUN corepack enable && corepack prepare pnpm@11.0.9 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build


FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt ./social_platform/requirements.txt
RUN pip install --no-cache-dir -r ./social_platform/requirements.txt

COPY app/ ./social_platform/app/
COPY __init__.py __main__.py ./social_platform/
COPY alembic/ ./social_platform/alembic/
COPY alembic.ini ./social_platform/alembic.ini
COPY entrypoint.sh ./social_platform/entrypoint.sh
COPY --from=frontend-builder /app/social_platform/frontend/dist ./social_platform/frontend/dist

RUN mkdir -p /app/social_platform/app/data /app/social_platform/app/uploads && \
    chmod +x /app/social_platform/entrypoint.sh

EXPOSE 8000

CMD ["/app/social_platform/entrypoint.sh"]
