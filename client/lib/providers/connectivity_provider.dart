// 연결 상태 프로바이더
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/api_client.dart';
import 'package:voice_to_textnote/services/connectivity_service.dart';

// ConnectivityService 싱글톤 프로바이더
final connectivityServiceProvider = Provider<ConnectivityService>((ref) {
  final dio = ref.watch(dioProvider);
  final service = ConnectivityService(dio: dio);

  // Provider 해제 시 서비스도 정리
  ref.onDispose(service.dispose);

  return service;
});

// 온라인 여부 상태 프로바이더 (StreamProvider로 실시간 업데이트)
final connectivityProvider =
    StateNotifierProvider<_ConnectivityNotifier, bool>((ref) {
  final service = ref.watch(connectivityServiceProvider);
  return _ConnectivityNotifier(service);
});

class _ConnectivityNotifier extends StateNotifier<bool> {
  final ConnectivityService _service;

  // 스트림 구독 참조 저장 - dispose 시 취소를 위해 필요
  late final StreamSubscription<bool> _subscription;

  _ConnectivityNotifier(this._service) : super(_service.isOnline) {
    // 상태 변화 스트림 구독 - 반환값 저장
    _subscription = _service.onStatusChange.listen((isOnline) {
      if (mounted) state = isOnline;
    });
    // 30초 간격 모니터링 시작
    _service.startMonitoring();
  }

  @override
  void dispose() {
    // 스트림 구독 취소하여 메모리 누수 방지
    _subscription.cancel();
    super.dispose();
  }
}
