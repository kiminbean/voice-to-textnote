#!/bin/bash
# ============================================================
# Voice to TextNote - Ubuntu 24.04 서버 배포 스크립트
# 사용법: bash setup-ubuntu.sh
# ============================================================

set -e

echo "=========================================="
echo " Voice to TextNote 서버 설치 시작"
echo " 대상: Ubuntu 24.04"
echo "=========================================="

# ─── 1. 시스템 패키지 설치 ───────────────────────────────────
echo ""
echo "[1/6] 시스템 패키지 설치..."
sudo apt update
sudo apt install -y \
    python3.11 python3.11-venv python3.11-dev \
    redis-server \
    ffmpeg \
    git \
    build-essential

# Redis 시작 및 자동 시작 설정
sudo systemctl enable redis-server
sudo systemctl start redis-server
echo "✓ Redis 서버 시작됨"

# ─── 2. 프로젝트 클론 ───────────────────────────────────────
echo ""
echo "[2/6] 프로젝트 설정..."

PROJECT_DIR="$HOME/voice-textnote"

if [ -d "$PROJECT_DIR" ]; then
    echo "기존 프로젝트 디렉토리 발견: $PROJECT_DIR"
    cd "$PROJECT_DIR"
    git pull origin main
else
    git clone https://github.com/kiminbean/my-project.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# ─── 3. Python 가상환경 및 의존성 ───────────────────────────
echo ""
echo "[3/6] Python 가상환경 설정..."

python3.11 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r deploy/requirements-ubuntu.txt

echo "✓ Python 의존성 설치 완료"

# ─── 4. 환경 변수 설정 ──────────────────────────────────────
echo ""
echo "[4/6] 환경 변수 설정..."

ENV_FILE="$PROJECT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    cp .env.example "$ENV_FILE"

    # 우분투용 기본값 수정
    sed -i 's|WHISPER_MODEL=.*|WHISPER_MODEL=small|' "$ENV_FILE"
    sed -i 's|HOST=.*|HOST=0.0.0.0|' "$ENV_FILE"
    sed -i 's|PORT=.*|PORT=8000|' "$ENV_FILE"

    echo ""
    echo "⚠️  .env 파일이 생성되었습니다. 다음 값을 반드시 설정하세요:"
    echo "   - HUGGINGFACE_TOKEN: 화자 분리용 HuggingFace 토큰"
    echo "   - ZAI_API_KEY: Z.AI Coding Plan API 키 (glm-5.2)"
    echo "   - API_KEYS: API 인증 키 (쉼표 구분)"
    echo ""
    echo "   편집: nano $ENV_FILE"
else
    echo "✓ 기존 .env 파일 사용"
fi

# ─── 5. 저장소 디렉토리 생성 ─────────────────────────────────
echo ""
echo "[5/6] 저장소 디렉토리 생성..."
mkdir -p storage/temp storage/results
echo "✓ storage 디렉토리 생성 완료"

# ─── 6. systemd 서비스 등록 ──────────────────────────────────
echo ""
echo "[6/6] systemd 서비스 등록..."

# FastAPI 서버 서비스
sudo tee /etc/systemd/system/voicenote-api.service > /dev/null << SERVICEEOF
[Unit]
Description=Voice TextNote API Server
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin
ExecStart=$PROJECT_DIR/venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Celery 워커 서비스
sudo tee /etc/systemd/system/voicenote-worker.service > /dev/null << SERVICEEOF
[Unit]
Description=Voice TextNote Celery Worker
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin
ExecStart=$PROJECT_DIR/venv/bin/celery -A backend.workers.celery_app:celery_app worker --loglevel=info --concurrency=3
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable voicenote-api voicenote-worker

echo ""
echo "=========================================="
echo " 설치 완료!"
echo "=========================================="
echo ""
echo " 다음 단계:"
echo ""
echo " 1. .env 파일 편집:"
echo "    nano $ENV_FILE"
echo ""
echo " 2. 서비스 시작:"
echo "    sudo systemctl start voicenote-api"
echo "    sudo systemctl start voicenote-worker"
echo ""
echo " 3. 상태 확인:"
echo "    sudo systemctl status voicenote-api"
echo "    sudo systemctl status voicenote-worker"
echo ""
echo " 4. 로그 확인:"
echo "    journalctl -u voicenote-api -f"
echo "    journalctl -u voicenote-worker -f"
echo ""
echo " 5. API 테스트:"
echo "    curl http://localhost:8000/api/v1/health"
echo ""
echo " Tailscale IP: 아이폰에서 http://100.69.69.119:8000 으로 접속"
echo "=========================================="
