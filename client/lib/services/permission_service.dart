// 권한 관리 서비스
// @MX:ANCHOR: 마이크/알림 권한 요청의 중앙 관리 서비스
// @MX:REASON: recording_provider에서 직접 의존하며, iOS/Android 플랫폼 분기 로직 포함

import 'package:permission_handler/permission_handler.dart';

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
    final status = await Permission.microphone.request();
    return _mapStatus(status);
  }

  /// 알림 권한 요청
  Future<PermissionStatus> requestNotificationPermission() async {
    final status = await Permission.notification.request();
    return _mapStatus(status);
  }

  /// 마이크 권한 확인
  Future<PermissionStatus> checkMicrophonePermission() async {
    final status = await Permission.microphone.status;
    return _mapStatus(status);
  }

  /// 권한 설명 필요 여부 (iOS)
  Future<bool> shouldShowRationale(Permission permission) async {
    return await permission.shouldShowRequestRationale;
  }

  /// 설정 열기 (권한 거부 시 안내)
  Future<bool> openAppSettings() async {
    return await openAppSettings();
  }

  /// Permission.Status -> 내부 PermissionStatus 변환
  PermissionStatus _mapStatus(androidStatus) {
    switch (androidStatus) {
      case PermissionStatus.granted:
        return PermissionStatus.granted;
      case PermissionStatus.denied:
        return PermissionStatus.denied;
      case PermissionStatus.permanentlyDenied:
        return PermissionStatus.permanentlyDenied;
      default:
        return PermissionStatus.notDetermined;
    }
  }
}
