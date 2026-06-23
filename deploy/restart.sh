#!/bin/bash
# REQ-PERF-006: 서버 안전 재시작 스크립트
# 사용법: bash deploy/restart.sh

set -e

PROJECT_DIR="${HOME}/voice-to-textnote"
VENV_BIN="${PROJECT_DIR}/venv/bin"
LOG_DIR="${HOME}"

echo "=== Voice to TextNote 서버 재시작 ==="

# 1. 기존 프로세스 정리
echo "[1/4] 기존 프로세스 정리..."
pkill -f uvicorn 2>/dev/null || true
pkill -f celery 2>/dev/null || true
sleep 2

# 2. 코드 업데이트 (선택)
if [ "$1" = "--pull" ]; then
    echo "[2/4] 코드 업데이트 (git pull)..."
    cd "${PROJECT_DIR}" && git pull origin main
else
    echo "[2/4] 코드 업데이트 건너뜀 (--pull 옵션으로 활성화)"
fi

# 3. uvicorn 시작
echo "[3/4] uvicorn 시작..."
cd "${PROJECT_DIR}"
nohup "${VENV_BIN}/uvicorn" backend.app.main:app --host 0.0.0.0 --port 8000 >> "${LOG_DIR}/voicenote.log" 2>&1 &
sleep 3

# 4. Celery 워커 시작
echo "[4/4] Celery 워커 시작..."
nohup "${VENV_BIN}/celery" -A backend.workers.celery_app:celery_app worker --loglevel=info --concurrency=3 >> "${LOG_DIR}/celery.log" 2>&1 &
sleep 2

# 헬스체크
echo ""
echo "=== 헬스체크 ==="
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health | grep -q "200"; then
    echo "uvicorn: OK (port 8000)"
else
    echo "uvicorn: FAILED - 로그 확인: tail -20 ${LOG_DIR}/voicenote.log"
fi

echo ""
echo "=== 재시작 완료 ==="
echo "로그 확인: tail -f ${LOG_DIR}/voicenote.log"
