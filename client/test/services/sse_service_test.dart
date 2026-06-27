// SSE 서비스 테스트
import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/sse_service.dart';

// Mock http.Client
class MockHttpClient extends Mock implements http.Client {}

// Mock http.StreamedResponse
class MockStreamedResponse extends Mock implements http.StreamedResponse {}

void main() {
  setUpAll(() {
    // Uri fallback 등록
    registerFallbackValue(Uri.parse('http://localhost:8000'));
    registerFallbackValue(
        http.Request('GET', Uri.parse('http://localhost:8000')));
  });

  late MockHttpClient mockClient;
  late SseService sseService;

  setUp(() {
    mockClient = MockHttpClient();
    sseService = SseService(
      baseUrl: 'http://localhost:8000',
      clientFactory: () => mockClient,
    );
  });

  tearDown(() {
    sseService.disconnect();
  });

  group('SseService', () {
    // SSE 이벤트 스트림 수신 테스트
    test('SSE 이벤트를 파싱하여 스트림으로 emit 해야 함', () async {
      // Arrange: SSE 데이터 시뮬레이션
      final sseData = [
        'data: {"status": "processing", "progress": 0.5}\n\n',
        'data: {"status": "completed", "progress": 1.0}\n\n',
      ];
      final streamController = StreamController<List<int>>();

      // http 패키지의 ByteStream 사용
      final byteStream = http.ByteStream(streamController.stream);
      final mockResponse = MockStreamedResponse();
      when(() => mockResponse.statusCode).thenReturn(200);
      when(() => mockResponse.stream).thenAnswer((_) => byteStream);

      when(() => mockClient.send(any())).thenAnswer((_) async {
        // 비동기로 데이터 전송
        Future.microtask(() {
          for (final chunk in sseData) {
            streamController.add(utf8.encode(chunk));
          }
          streamController.close();
        });
        return mockResponse;
      });

      // Act
      final events = <Map<String, dynamic>>[];
      await for (final event in sseService.connect('task-123')) {
        events.add(event);
      }

      // Assert
      expect(events, hasLength(2));
      expect(events[0]['status'], 'processing');
      expect(events[0]['progress'], 0.5);
      expect(events[1]['status'], 'completed');
      expect(events[1]['progress'], 1.0);
    });

    // 연결 실패 시 예외 전파 테스트
    test('SSE 연결 실패 시 예외를 던져야 함', () async {
      // Arrange
      when(() => mockClient.send(any())).thenThrow(Exception('연결 실패'));

      // Act & Assert
      expect(
        () => sseService.connect('task-123').toList(),
        throwsException,
      );
    });

    // disconnect 호출 시 클라이언트 종료 테스트
    test('disconnect 호출 시 오류 없이 완료되어야 함', () {
      // Act & Assert: 두 번 호출해도 안전해야 함
      expect(() => sseService.disconnect(), returnsNormally);
      expect(() => sseService.disconnect(), returnsNormally);
    });

    // 잘못된 JSON 데이터 무시 테스트
    test('잘못된 JSON 데이터는 무시해야 함', () async {
      // Arrange: 일부 잘못된 JSON 포함
      final sseData = [
        'data: invalid-json\n\n',
        'data: {"status": "processing"}\n\n',
      ];
      final streamController = StreamController<List<int>>();

      final byteStream = http.ByteStream(streamController.stream);
      final mockResponse = MockStreamedResponse();
      when(() => mockResponse.statusCode).thenReturn(200);
      when(() => mockResponse.stream).thenAnswer((_) => byteStream);

      when(() => mockClient.send(any())).thenAnswer((_) async {
        Future.microtask(() {
          for (final chunk in sseData) {
            streamController.add(utf8.encode(chunk));
          }
          streamController.close();
        });
        return mockResponse;
      });

      // Act
      final events = <Map<String, dynamic>>[];
      await for (final event in sseService.connect('task-123')) {
        events.add(event);
      }

      // Assert: 유효한 이벤트만 수신
      expect(events, hasLength(1));
      expect(events[0]['status'], 'processing');
    });

    test('headersProvider가 반환한 인증 헤더를 요청에 포함해야 함', () async {
      sseService = SseService(
        baseUrl: 'http://localhost:8000',
        clientFactory: () => mockClient,
        headersProvider: () async => {'Authorization': 'Bearer token-001'},
      );
      when(() => mockClient.send(any())).thenAnswer(
        (_) async => http.StreamedResponse(const Stream.empty(), 200),
      );

      await sseService.connect('task-123').toList();

      final request = verify(() => mockClient.send(captureAny()))
          .captured
          .single as http.Request;
      expect(request.headers['Authorization'], 'Bearer token-001');
    });

    test('성공 상태 코드가 아니면 예외를 던져 폴링 폴백을 가능하게 해야 함', () async {
      when(() => mockClient.send(any())).thenAnswer(
        (_) async => http.StreamedResponse(const Stream.empty(), 401),
      );

      expect(
        () => sseService.connect('task-123').toList(),
        throwsA(isA<http.ClientException>()),
      );
    });
  });
}
