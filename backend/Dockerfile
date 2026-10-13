# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ffmpeg helps faster-whisper decode mp4/mov/webm (and STT builds need it).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Core API only. For full STT (faster-whisper/torch/pyannote) build with:
#   docker compose build --build-arg INSTALL_STT=1 backend
# Pip cache mount keeps torch/pyannote downloads across rebuilds (BuildKit).
COPY requirements.txt requirements-stt.txt ./
ARG INSTALL_STT=0
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$INSTALL_STT" = "1" ]; then pip install -r requirements-stt.txt; fi

# App code last — changing Python files does NOT reinstall torch.
COPY app ./app
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
