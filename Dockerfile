# Multi-stage: build React UI, then run FastAPI + serve static dist.
FROM node:20-alpine AS frontend-build
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webapp.py trade_logic.py cba_rules.py picks.py season_utils.py ./
COPY ml ./ml
COPY artifacts ./artifacts
COPY data ./data
COPY templates ./templates
COPY static ./static
COPY --from=frontend-build /fe/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "webapp:app", "--host", "0.0.0.0", "--port", "8000"]
