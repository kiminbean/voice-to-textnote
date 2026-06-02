// Firebase 초기화 설정
// @MX:ANCHOR: Firebase 앱 초기화의 진입점
// @MX:REASON: main.dart에서 앱 시작 전 반드시 호출해야 함

import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';

/// Firebase 초기화 결과
class FirebaseInitResult {
  final bool success;
  final String? error;

  const FirebaseInitResult({required this.success, this.error});
}

/// Firebase 설정 유틸
class FirebaseConfig {
  /// Firebase 초기화 (우회 지원)
  static Future<FirebaseInitResult> initializeFirebase() async {
    try {
      // 이미 초기화된 경우 무시
      if (Firebase.apps.isNotEmpty) {
        return const FirebaseInitResult(success: true);
      }

      // Firebase 기본 옵션으로 초기화
      await Firebase.initializeApp(
        options: const FirebaseOptions(
          apiKey: '', // 프로덕션에서는 환경변수 주입 필요
          appId: '',
          messagingSenderId: '',
          projectId: '',
        ),
      );

      debugPrint('Firebase 초기화 성공');
      return const FirebaseInitResult(success: true);
    } catch (e) {
      // Firebase 미구성 시 우회 (개발 환경 지원)
      debugPrint('Firebase 초기화 실패 (우회 모드): $e');
      return FirebaseInitResult(
        success: false,
        error: 'Firebase가 구성되지 않았습니다. 일부 기능이 제한됩니다.',
      );
    }
  }

  /// Firebase 구성 여부 확인
  static bool isConfigured() {
    return Firebase.apps.isNotEmpty;
  }
}
