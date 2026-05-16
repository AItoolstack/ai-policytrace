# syntax=docker/dockerfile:1

FROM node:20-slim AS ui-build

WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build


FROM python:3.11-slim AS app

ENV PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_sm

COPY config/ ./config/
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY sample_data/ ./sample_data/
COPY --from=ui-build /app/ui/dist ./ui/dist

RUN mkdir -p output/sessions output/debug

EXPOSE 7860

CMD ["sh", "-c", "uvicorn api:app --app-dir src --host 0.0.0.0 --port ${PORT:-7860}"]
