// 권한 요청 다이얼로그 위젯
// @MX:ANCHOR: 마이크/알림 권한 요청의 중앙 UI 컴포넌트
// @MX:REASON: recording_screen에서 사용하며, 영구 거부 시 설정 안내 포함

import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart' as ph;

/// 권한 타입
enum PermissionType {
  microphone, // 마이크 권한
  notification, // 알림 권한
}

/// 권한 요청 다이얼로그
class PermissionDialog extends StatelessWidget {
  final PermissionType permissionType;
  final VoidCallback onRequest;
  final VoidCallback onOpenSettings;

  const PermissionDialog({
    super.key,
    required this.permissionType,
    required this.onRequest,
    required this.onOpenSettings,
  });

  @override
  Widget build(BuildContext context) {
    final title = _getTitle();
    final description = _getDescription();
    final buttonText = _getButtonText();

    return AlertDialog(
      title: Text(title),
      content: Text(description),
      actions: [
        // 취소 버튼
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('취소'),
        ),
        // 권한 요청 또는 설정 열기 버튼
        ElevatedButton(
          onPressed: () {
            Navigator.of(context).pop();
            if (permissionType == PermissionType.notification) {
              // 알림 권한은 설정에서만 허용 가능 (iOS)
              onOpenSettings();
            } else {
              onRequest();
            }
          },
          child: Text(buttonText),
        ),
      ],
    );
  }

  /// 권한 타입별 제목
  String _getTitle() {
    switch (permissionType) {
      case PermissionType.microphone:
        return '마이크 권한 필요';
      case PermissionType.notification:
        return '알림 권한 필요';
    }
  }

  /// 권한 타입별 설명
  String _getDescription() {
    switch (permissionType) {
      case PermissionType.microphone:
        return '회의 녹음을 위해 마이크 접근 권한이 필요합니다.';
      case PermissionType.notification:
        return '녹음 완료 및 처리 완료 알림을 위해 알림 권한이 필요합니다.';
    }
  }

  /// 권한 타입별 버튼 텍스트
  String _getButtonText() {
    switch (permissionType) {
      case PermissionType.microphone:
        return '권한 허용';
      case PermissionType.notification:
        return '설정 열기';
    }
  }
}

/// 영구 거부 안내 다이얼로그
class PermanentlyDeniedDialog extends StatelessWidget {
  final PermissionType permissionType;
  final VoidCallback onOpenSettings;

  const PermanentlyDeniedDialog({
    super.key,
    required this.permissionType,
    required this.onOpenSettings,
  });

  @override
  Widget build(BuildContext context) {
    final title = _getTitle();
    final description = _getDescription();

    return AlertDialog(
      title: Text(title),
      content: Text(description),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('취소'),
        ),
        ElevatedButton(
          onPressed: () {
            Navigator.of(context).pop();
            onOpenSettings();
          },
          child: const Text('설정 열기'),
        ),
      ],
    );
  }

  String _getTitle() {
    switch (permissionType) {
      case PermissionType.microphone:
        return '마이크 권한이 거부됨';
      case PermissionType.notification:
        return '알림 권한이 거부됨';
    }
  }

  String _getDescription() {
    switch (permissionType) {
      case PermissionType.microphone:
        return '마이크 권한이 영구적으로 거부되었습니다. 설정에서 권한을 허용해주세요.';
      case PermissionType.notification:
        return '알림 권한이 영구적으로 거부되었습니다. 설정에서 권한을 허용해주세요.';
    }
  }
}

/// 설정 열기 헬퍼 함수
/// permission_handler 패키지의 openAppSettings를 래핑한다.
Future<bool> openAppSettings() async {
  try {
    return await ph.openAppSettings();
  } catch (e) {
    debugPrint('설정 열기 실패: $e');
    return false;
  }
}
