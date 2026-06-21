FROM python:3.11-slim

# ffmpeg: 오디오 변환 (REQ-STT-015)
# curl: docker-compose healthcheck용
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY backend/ backend/

RUN pip install --no-cache-dir . && \
    mkdir -p storage/temp storage/results

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
