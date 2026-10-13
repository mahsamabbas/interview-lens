FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Core API only. For full STT (faster-whisper/torch/pyannote) build with:
#   docker compose build --build-arg INSTALL_STT=1 backend
COPY requirements.txt requirements-stt.txt ./
ARG INSTALL_STT=0
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$INSTALL_STT" = "1" ]; then pip install -r requirements-stt.txt; fi

COPY app ./app
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
