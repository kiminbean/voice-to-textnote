// 서버 연결 상태 모니터링 서비스
import 'dart:async';

import 'package:dio/dio.dart';

// @MX:ANCHOR: 연결 상태 관리 - 앱 전역에서 참조됨
// @MX:REASON: HomeScreen, ProcessingScreen, RecordingScreen 모두 이 서비스 사용
class ConnectivityService {
  final Dio _dio;
  final String _healthPath;

  Timer? _timer;
  final _controller = StreamController<bool>.broadcast();

  // 현재 온라인 여부
  bool _isOnline = true;
  bool get isOnline => _isOnline;

  // 연결 상태 변화 스트림
  Stream<bool> get onStatusChange => _controller.stream;

  ConnectivityService({
    required Dio dio,
    String healthPath = '/api/v1/health',
  })  : _dio = dio,
        _healthPath = healthPath;

  // 주기적 헬스체크 시작 (기본 30초 간격)
  void startMonitoring({
    Duration interval = const Duration(seconds: 30),
  }) {
    // 즉시 1회 체크
    checkHealth();
    _timer = Timer.periodic(interval, (_) => checkHealth());
  }

  // 단일 헬스체크 수행
  Future<void> checkHealth() async {
    try {
      await _dio.get(_healthPath);
      // 오프라인 → 온라인 복구 시에만 이벤트 발행
      if (!_isOnline) {
        _isOnline = true;
        if (!_controller.isClosed) {
          _controller.add(true);
        }
      }
    } catch (_) {
      // 온라인 → 오프라인 전환 시에만 이벤트 발행
      if (_isOnline) {
        _isOnline = false;
        if (!_controller.isClosed) {
          _controller.add(false);
        }
      }
    }
  }

  // 리소스 정리
  void dispose() {
    _timer?.cancel();
    _timer = null;
    _controller.close();
  }
}
