FROM python:3.11-slim

# ffmpeg 설치 (REQ-STT-015: 오디오 변환에 필수)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY backend/ backend/
COPY storage/ storage/ 2>/dev/null || mkdir -p storage/temp storage/results

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
