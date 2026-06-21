// MinutesApi 서비스 테스트 - SPEC-APP-004 REQ-APP-044
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';

// Dio Mock 클래스
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late MinutesApi minutesApi;

  setUp(() {
    mockDio = MockDio();
    minutesApi = MinutesApi(mockDio);
  });

  group('MinutesApi', () {
    // getResult: 회의록 결과 조회 성공 테스트 (markdown 포함)
    test('getResult가 markdown 필드를 포함한 회의록 결과를 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'markdown': '# 회의록\n\n## 참석자\n- 김철수\n- 이영희',
            'segments': [],
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await minutesApi.getResult('min-001');

      // Assert
      expect(result['markdown'], contains('# 회의록'));
      verify(() => mockDio.get('/minutes/min-001')).called(1);
    });

    // getResult: segments 형식으로 반환하는 경우 테스트
    test('getResult가 segments 배열을 포함한 결과를 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'segments': [
              {'speaker_name': '김철수', 'text': '안녕하세요.'},
              {'speaker_name': '이영희', 'text': '반갑습니다.'},
            ],
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await minutesApi.getResult('min-002');

      // Assert
      expect(result['segments'], hasLength(2));
      verify(() => mockDio.get('/minutes/min-002')).called(1);
    });

    // getResult: 네트워크 오류 시 예외 전파 테스트
    test('getResult가 네트워크 오류 시 DioException을 전파해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          message: '연결 오류',
        ),
      );

      // Act & Assert
      expect(
          () => minutesApi.getResult('min-001'), throwsA(isA<DioException>()));
    });

    test('importExternalText가 URL transcript를 import API로 전송해야 함', () async {
      // Arrange
      when(() => mockDio.post(any(), data: any(named: 'data'))).thenAnswer(
        (_) async => Response(
          data: {
            'task_id': 'ext-001',
            'status': 'completed',
            'result_url': '/api/v1/minutes/ext-001',
            'search_indexed': true,
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await minutesApi.importExternalText(
        sourceUrl: 'https://youtu.be/example123',
        title: '영상 transcript',
        content: '사용자가 보유한 영상 transcript 본문입니다.',
        sourceType: 'youtube',
        language: 'ko',
      );

      // Assert
      expect(result['task_id'], 'ext-001');
      expect(result['search_indexed'], true);
      verify(
        () => mockDio.post(
          '/imports/external-text',
          data: {
            'source_url': 'https://youtu.be/example123',
            'title': '영상 transcript',
            'content': '사용자가 보유한 영상 transcript 본문입니다.',
            'source_type': 'youtube',
            'language': 'ko',
          },
        ),
      ).called(1);
    });

    test('importDocument가 PDF/DOCX 문서를 document import API로 전송해야 함', () async {
      final tempDir = await Directory.systemTemp.createTemp('minutes-api-test');
      final file = File('${tempDir.path}/강의자료.pdf');
      await file
          .writeAsBytes([0x25, 0x50, 0x44, 0x46, 0x20, 0x74, 0x65, 0x78, 0x74]);
      addTearDown(() async {
        if (await tempDir.exists()) {
          await tempDir.delete(recursive: true);
        }
      });

      when(
        () => mockDio.post(
          any(),
          data: any(named: 'data'),
          options: any(named: 'options'),
        ),
      ).thenAnswer(
        (_) async => Response(
          data: {
            'task_id': 'doc-001',
            'status': 'completed',
            'title': '강의자료',
            'result_url': '/api/v1/minutes/doc-001',
            'search_indexed': true,
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await minutesApi.importDocument(
        file: file,
        title: '강의자료',
        language: 'ko',
      );

      expect(result['task_id'], 'doc-001');
      final captured = verify(
        () => mockDio.post(
          '/imports/document',
          data: captureAny(named: 'data'),
          options: captureAny(named: 'options'),
        ),
      ).captured;
      final formData = captured[0] as FormData;
      final options = captured[1] as Options;
      expect(formData.files.single.key, 'file');
      expect(formData.files.single.value.filename, '강의자료.pdf');
      expect(
        formData.fields,
        contains(predicate<MapEntry<String, String>>(
          (entry) => entry.key == 'title' && entry.value == '강의자료',
        )),
      );
      expect(
        formData.fields,
        contains(predicate<MapEntry<String, String>>(
          (entry) => entry.key == 'language' && entry.value == 'ko',
        )),
      );
      expect(options.contentType, 'multipart/form-data');
    });
  });
}
