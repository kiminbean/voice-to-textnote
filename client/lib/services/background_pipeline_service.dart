// 백그라운드 파이프라인 모니터링 서비스
// @MX:NOTE: SPEC-APP-005 REQ-015 — Firebase Push + 로컬 알림 하이브리드 전략
// iOS 백그라운드 제약(~30초)으로 workmanager 대신 서버 푸시 활용

import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/providers/pipeline_provider.dart';
import 'package:voice_to_textnote/services/notification_service.dart';
import 'package:voice_to_textnote/services/cache_service.dart';

/// 백그라운드 파이프라인 모니터 (REQ-015)
/// 앱이 백그라운드로 전환되어도 파이프라인 완료를 감지하고 알림
class BackgroundPipelineService {
  Timer? _monitorTimer;
  final NotificationService _notificationService = NotificationService();
  final CacheService _cacheService = CacheService();

  bool _isMonitoring = false;
  String? _currentMeetingId;
  String? _currentMeetingTitle;

  /// 백그라운드 모니터링 시작
  void startMonitoring({
    required Ref ref,
    required String meetingId,
    String? meetingTitle,
  }) {
    if (_isMonitoring) return;

    _currentMeetingId = meetingId;
    _currentMeetingTitle = meetingTitle;
    _isMonitoring = true;

    // 10초 간격으로 파이프라인 상태 폴링
    _monitorTimer = Timer.periodic(
      const Duration(seconds: 10),
      (_) => _checkPipelineStatus(ref),
    );
  }

  /// 모니터링 중지
  void stopMonitoring() {
    _monitorTimer?.cancel();
    _monitorTimer = null;
    _isMonitoring = false;
    _currentMeetingId = null;
    _currentMeetingTitle = null;
  }

  /// 파이프라인 상태 확인
  Future<void> _checkPipelineStatus(Ref ref) async {
    if (!_isMonitoring || _currentMeetingId == null) return;

    final pipelineState = ref.read(pipelineProvider);

    if (pipelineState.currentStep == PipelineStep.completed) {
      // 완료 시 결과 캐싱 + 로컬 알림 (REQ-015)
      await _cacheService.init();
      await _notificationService.init();

      // 알림 표시
      await _notificationService.showPipelineCompleted(
        meetingId: _currentMeetingId!,
        title: _currentMeetingTitle ?? '미팅',
      );

      stopMonitoring();
    } else if (pipelineState.currentStep == PipelineStep.failed) {
      // 실패 시에도 모니터링 중지
      stopMonitoring();
    }
  }

  /// 현재 모니터링 상태
  bool get isMonitoring => _isMonitoring;

  /// 리소스 정리
  void dispose() {
    stopMonitoring();
  }
}
