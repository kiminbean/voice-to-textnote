// Firebase 초기화 설정
// @MX:ANCHOR: Firebase 앱 초기화의 진입점
// @MX:REASON: main.dart에서 앱 시작 전 반드시 호출해야 함

import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:voice_to_textnote/firebase_options.dart';

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

      // flutterfire configure로 생성된 플랫폼별 옵션으로 초기화
      // (lib/firebase_options.dart, voice-to-textnote 프로젝트)
      await Firebase.initializeApp(
        options: DefaultFirebaseOptions.currentPlatform,
      );

      debugPrint('Firebase 초기화 성공');
      return const FirebaseInitResult(success: true);
    } catch (e) {
      // Firebase 미구성 시 우회 (개발 환경 지원)
      debugPrint('Firebase 초기화 실패 (우회 모드): $e');
      return const FirebaseInitResult(
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
