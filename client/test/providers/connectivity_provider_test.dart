// ConnectivityProvider 테스트
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/providers/connectivity_provider.dart';
import 'package:voice_to_textnote/services/connectivity_service.dart';

class MockConnectivityService extends Mock implements ConnectivityService {}

void main() {
  setUpAll(() {
    registerFallbackValue(const Duration(seconds: 30));
  });

  late MockConnectivityService mockService;
  late StreamController<bool> streamController;

  setUp(() {
    mockService = MockConnectivityService();
    streamController = StreamController<bool>.broadcast();

    // Mock 기본 동작 설정
    when(() => mockService.isOnline).thenReturn(true);
    when(() => mockService.onStatusChange)
        .thenAnswer((_) => streamController.stream);
    when(() => mockService.startMonitoring(
          interval: any(named: 'interval'),
        )).thenReturn(null);
    when(() => mockService.dispose()).thenReturn(null);
  });

  tearDown(() {
    streamController.close();
  });

  group('ConnectivityProvider', () {
    // 초기 상태 테스트
    test('초기 상태는 isOnline 값을 반영해야 함', () {
      when(() => mockService.isOnline).thenReturn(true);

      final container = ProviderContainer(
        overrides: [
          connectivityServiceProvider.overrideWithValue(mockService),
        ],
      );
      addTearDown(container.dispose);

      final isOnline = container.read(connectivityProvider);
      expect(isOnline, isTrue);
    });

    // 오프라인 초기 상태 테스트
    test('서비스가 오프라인이면 false를 반환해야 함', () {
      when(() => mockService.isOnline).thenReturn(false);

      final container = ProviderContainer(
        overrides: [
          connectivityServiceProvider.overrideWithValue(mockService),
        ],
      );
      addTearDown(container.dispose);

      final isOnline = container.read(connectivityProvider);
      expect(isOnline, isFalse);
    });

    // 스트림으로 상태 변화 반영 테스트
    test('onStatusChange 스트림으로 상태가 업데이트되어야 함', () async {
      when(() => mockService.isOnline).thenReturn(true);

      final container = ProviderContainer(
        overrides: [
          connectivityServiceProvider.overrideWithValue(mockService),
        ],
      );
      addTearDown(container.dispose);

      // 초기 상태 확인
      expect(container.read(connectivityProvider), isTrue);

      // 오프라인 이벤트 발행
      streamController.add(false);
      await Future.microtask(() {}); // 스트림 처리 대기

      // 상태 변화 반영 확인
      expect(container.read(connectivityProvider), isFalse);
    });
  });
}
