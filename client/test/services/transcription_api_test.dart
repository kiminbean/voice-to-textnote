// TranscriptionApi 서비스 테스트
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/transcription_api.dart';

// Dio Mock 클래스
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late TranscriptionApi transcriptionApi;
  late Directory tempDir;
  late File testFile;

  setUpAll(() async {
    // 테스트용 임시 파일 생성
    tempDir = await Directory.systemTemp.createTemp('test_audio_');
    testFile = File('${tempDir.path}/test.m4a');
    await testFile.writeAsBytes([0, 1, 2, 3]); // 더미 바이트
  });

  tearDownAll(() async {
    // 임시 파일 정리
    await tempDir.delete(recursive: true);
  });

  setUp(() {
    mockDio = MockDio();
    transcriptionApi = TranscriptionApi(mockDio);
  });

  group('TranscriptionApi', () {
    // 업로드 성공 테스트
    test('upload이 성공적으로 동작해야 함', () async {
      // Arrange: 성공 응답 모킹
      when(() => mockDio.post(
        any(),
        data: any(named: 'data'),
        options: any(named: 'options'),
      )).thenAnswer((_) async => Response(
        data: {'task_id': 'stt-task-001', 'status': 'pending'},
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ));

      // Act
      final result = await transcriptionApi.upload(testFile.path);

      // Assert
      expect(result['task_id'], 'stt-task-001');
      expect(result['status'], 'pending');
    });

    // 상태 조회 테스트
    test('getStatus가 올바르게 동작해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer((_) async => Response(
        data: {'task_id': 'stt-task-001', 'status': 'processing', 'progress': 50},
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ));

      // Act
      final result = await transcriptionApi.getStatus('stt-task-001');

      // Assert
      expect(result['task_id'], 'stt-task-001');
      expect(result['status'], 'processing');
    });

    // 결과 조회 테스트
    test('getResult가 올바르게 동작해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer((_) async => Response(
        data: {
          'task_id': 'stt-task-001',
          'status': 'completed',
          'text': '안녕하세요. 오늘 회의를 시작하겠습니다.',
        },
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ));

      // Act
      final result = await transcriptionApi.getResult('stt-task-001');

      // Assert
      expect(result['text'], '안녕하세요. 오늘 회의를 시작하겠습니다.');
    });

    // 삭제 테스트
    test('delete가 오류 없이 동작해야 함', () async {
      // Arrange
      when(() => mockDio.delete(any())).thenAnswer((_) async => Response(
        data: null,
        statusCode: 204,
        requestOptions: RequestOptions(path: ''),
      ));

      // Act & Assert: 예외 없이 완료되어야 함
      await expectLater(
        transcriptionApi.delete('stt-task-001'),
        completes,
      );
    });

    // 업로드 실패 테스트 (서버 오류)
    test('업로드 후 서버 오류 시 DioException을 던져야 함', () async {
      // Arrange: 업로드 자체는 성공하되 서버가 오류 반환
      when(() => mockDio.post(
        any(),
        data: any(named: 'data'),
        options: any(named: 'options'),
      )).thenThrow(DioException(
        requestOptions: RequestOptions(path: ''),
        message: '서버 오류',
        type: DioExceptionType.badResponse,
      ));

      // 파일은 실제 존재하고 멀티파트 생성까지는 성공 - dio.post에서 실패
      expect(
        () => transcriptionApi.upload(testFile.path),
        throwsA(isA<DioException>()),
      );
    });
  });
}
