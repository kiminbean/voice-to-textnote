// 권한 관리 서비스
// @MX:ANCHOR: 마이크/알림 권한 요청의 중앙 관리 서비스
// @MX:REASON: recording_provider에서 직접 의존하며, iOS/Android 플랫폼 분기 로직 포함
// SPEC-MOBILE-005 REQ-006: 권한 검사 경로 통일 (G12)

import 'package:permission_handler/permission_handler.dart' as ph;

/// 권한 상태
enum PermissionStatus {
  granted, // 허용됨
  denied, // 거부됨
  permanentlyDenied, // 영구 거부
  notDetermined, // 미결정
}

/// 권한 서비스
class PermissionService {
  /// 마이크 권한 요청
  Future<PermissionStatus> requestMicrophonePermission() async {
    final status = await ph.Permission.microphone.request();
    return _mapStatus(status);
  }

  /// 알림 권한 요청
  Future<PermissionStatus> requestNotificationPermission() async {
    final status = await ph.Permission.notification.request();
    return _mapStatus(status);
  }

  /// 저장공간 권한 요청 (T-013)
  /// Android 12 이하: Permission.storage
  /// Android 13+: Permission.videos / photos / audio (MANAGE_EXTERNAL_STORAGE 권한)
  /// iOS: 미사용 (앱 샌드박스 내 저장)
  Future<PermissionStatus> requestStoragePermission() async {
    final status = await ph.Permission.storage.request();
    return _mapStatus(status);
  }

  /// 저장공간 권한 확인 (T-013)
  Future<PermissionStatus> checkStoragePermission() async {
    final status = await ph.Permission.storage.status;
    return _mapStatus(status);
  }

  /// 마이크 권한 확인
  Future<PermissionStatus> checkMicrophonePermission() async {
    final status = await ph.Permission.microphone.status;
    return _mapStatus(status);
  }

  /// SPEC-MOBILE-005 REQ-006: 통합 권한 보장 (G12)
  /// 녹음 시작 전 단일 진입점 — record 패키지의 hasPermission()과
  /// permission_handler의 상태를 교차 검증하여 일관성 보장
  ///
  /// @returns true: 마이크 권한 보장됨, false: 권한 없음
  Future<bool> ensureMicrophonePermission() async {
    // 1차: permission_handler로 상태 확인
    final status = await checkMicrophonePermission();

    if (status == PermissionStatus.granted) {
      return true;
    }

    if (status == PermissionStatus.permanentlyDenied) {
      return false;
    }

    // 2차: denied/notDetermined인 경우 요청 시도
    final requestResult = await requestMicrophonePermission();
    return requestResult == PermissionStatus.granted;
  }

  /// 권한 설명 필요 여부 (iOS)
  Future<bool> shouldShowRationale(ph.Permission permission) async {
    return await permission.shouldShowRequestRationale;
  }

  /// 설정 열기 (권한 거부 시 안내)
  Future<bool> openAppSettings() async {
    return await ph.openAppSettings();
  }

  /// ph.Permission.Status -> 내부 PermissionStatus 변환
  PermissionStatus _mapStatus(ph.PermissionStatus status) {
    switch (status) {
      case ph.PermissionStatus.granted:
        return PermissionStatus.granted;
      case ph.PermissionStatus.denied:
        return PermissionStatus.denied;
      case ph.PermissionStatus.permanentlyDenied:
        return PermissionStatus.permanentlyDenied;
      default:
        return PermissionStatus.notDetermined;
    }
  }
}
