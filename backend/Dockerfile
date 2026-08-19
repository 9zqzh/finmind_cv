FROM python:3.11.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app

COPY packages/gduf-academic-api /app/packages/gduf-academic-api
COPY backend /app/backend
COPY resources /app/resources

RUN python -m pip install --no-cache-dir \
      /app/packages/gduf-academic-api \
      /app/backend \
    && chown -R app:app /app

USER app
WORKDIR /app/backend

EXPOSE 8000

CMD ["python", "-m", "app.start", "--host", "0.0.0.0", "--port", "8000"]
