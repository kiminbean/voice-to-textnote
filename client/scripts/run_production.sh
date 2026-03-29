#!/bin/bash
# 프로덕션 환경 실행 스크립트 (릴리즈 빌드)
# API URL: https://api.voicetextnote.com/api/v1
# API_KEY: 반드시 환경 변수로 지정 필요
API_KEY="${API_KEY:?API_KEY 환경 변수를 설정하세요}"
flutter run --release --dart-define=ENV=production --dart-define=API_KEY="$API_KEY"
