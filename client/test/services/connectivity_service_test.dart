// ConnectivityService 테스트
import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/connectivity_service.dart';

class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late ConnectivityService service;

  setUpAll(() {
    registerFallbackValue(Options());
  });

  setUp(() {
    mockDio = MockDio();
    service = ConnectivityService(
      dio: mockDio,
      healthPath: '/api/v1/health',
    );
  });

  tearDown(() {
    service.dispose();
  });

  group('ConnectivityService', () {
    // 초기 상태는 온라인
    test('초기 상태는 온라인이어야 함', () {
      expect(service.isOnline, isTrue);
    });

    // 헬스체크 성공 시 온라인 유지
    test('헬스체크 성공 시 isOnline이 true여야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer((_) async => Response(
            data: {'status': 'ok'},
            statusCode: 200,
            requestOptions: RequestOptions(path: ''),
          ));

      // Act
      await service.checkHealth();

      // Assert
      expect(service.isOnline, isTrue);
    });

    // 헬스체크 실패 시 오프라인 전환
    test('헬스체크 실패 시 isOnline이 false여야 함', () async {
      // Arrange: 오류 발생
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          message: '서버 연결 불가',
          type: DioExceptionType.connectionError,
        ),
      );

      // Act
      await service.checkHealth();

      // Assert
      expect(service.isOnline, isFalse);
    });

    // 온라인 → 오프라인 전환 시 스트림 이벤트 발행
    test('오프라인 전환 시 onStatusChange 스트림에 false를 emit 해야 함', () async {
      // Arrange: 초기 온라인 상태에서 실패로 전환
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.connectionError,
        ),
      );

      final events = <bool>[];
      final subscription = service.onStatusChange.listen(events.add);

      // Act: 온라인 → 오프라인
      await service.checkHealth();
      subscription.cancel();

      // Assert: false 이벤트 발행 확인
      expect(events, contains(false));
    });

    // 오프라인 → 온라인 복구 시 스트림 이벤트 발행
    test('온라인 복구 시 onStatusChange 스트림에 true를 emit 해야 함', () async {
      // Step 1: 먼저 오프라인 상태로 전환
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.connectionError,
        ),
      );
      await service.checkHealth();
      expect(service.isOnline, isFalse);

      // Step 2: 온라인 복구 준비 및 구독 등록
      when(() => mockDio.get(any())).thenAnswer((_) async => Response(
            data: {'status': 'ok'},
            statusCode: 200,
            requestOptions: RequestOptions(path: ''),
          ));

      final events = <bool>[];
      final completer = Completer<void>();
      final subscription = service.onStatusChange.listen((event) {
        events.add(event);
        if (!completer.isCompleted) completer.complete();
      });

      // Step 3: 복구 체크
      await service.checkHealth();

      // 이벤트 처리 대기 (최대 1초)
      await Future.any([
        completer.future,
        Future.delayed(const Duration(milliseconds: 100)),
      ]);
      await subscription.cancel();

      // Assert: true 이벤트 발행 확인
      expect(events, contains(true));
    });

    // 중복 상태 변화 시 이벤트 미발행
    test('동일 상태에서는 스트림 이벤트를 발행하지 않아야 함', () async {
      // Arrange: 온라인 유지
      when(() => mockDio.get(any())).thenAnswer((_) async => Response(
            data: {'status': 'ok'},
            statusCode: 200,
            requestOptions: RequestOptions(path: ''),
          ));

      final events = <bool>[];
      final subscription = service.onStatusChange.listen(events.add);

      // Act: 두 번 연속 성공
      await service.checkHealth();
      await service.checkHealth();
      subscription.cancel();

      // Assert: 이벤트 미발행 (이미 온라인 → 온라인)
      expect(events, isEmpty);
    });

    // dispose 후 안전 종료
    test('dispose 후 오류 없이 종료되어야 함', () {
      expect(() => service.dispose(), returnsNormally);
    });
  });
}
