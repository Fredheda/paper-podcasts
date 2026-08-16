# Build context: repo root  ->  docker build -t podcasts-agent -f backend/Dockerfile .
FROM python:3.13-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir "poetry>=2.0,<3.0" \
    && poetry config virtualenvs.in-project true
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main,backend --no-interaction --no-ansi
COPY . .

FROM python:3.13-slim
WORKDIR /app

# mssql-python bundles its own driver (DDBC) -- these three packages are the
# only runtime system dependencies it needs (Kerberos + dynamic loading),
# per Microsoft's container guidance. Same as Portfolio/backend/Dockerfile.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libltdl7 \
    libkrb5-3 \
    libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
