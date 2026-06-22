#!/bin/bash
# 스테이징 환경 실행 스크립트 (Tailscale IP)
# API URL: http://100.69.69.119:8000/api/v1
# API_KEY: .env 파일에서 읽거나 직접 지정
API_KEY="${API_KEY:-}"
flutter run --dart-define=ENV=staging --dart-define=API_KEY="$API_KEY"
