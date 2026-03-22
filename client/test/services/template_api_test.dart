// TemplateApi 서비스 테스트 - SPEC-TMPL-001 REQ-TMPL-005
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/template_api.dart';

// Dio Mock 클래스
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late TemplateApi templateApi;
  late Directory tempDir;

  setUpAll(() {
    registerFallbackValue(FormData());
    registerFallbackValue(Options());
  });

  setUp(() async {
    mockDio = MockDio();
    templateApi = TemplateApi(mockDio);
    // 임시 디렉토리 생성 (실제 파일 업로드 테스트용)
    tempDir = await Directory.systemTemp.createTemp('template_test_');
  });

  tearDown(() async {
    // 임시 파일 정리
    if (await tempDir.exists()) {
      await tempDir.delete(recursive: true);
    }
  });

  group('TemplateApi', () {
    // uploadTemplate: 파일 업로드 성공 테스트
    test('uploadTemplate이 파일을 업로드하고 Template 객체를 반환해야 함', () async {
      // Arrange - 실제 임시 파일 생성
      final testFile = File('${tempDir.path}/표준_회의록.pdf');
      await testFile.writeAsString('PDF content');

      when(
        () => mockDio.post(
          any(),
          data: any(named: 'data'),
          options: any(named: 'options'),
        ),
      ).thenAnswer(
        (_) async => Response(
          data: {
            'template_id': 'tmpl-001',
            'name': '표준_회의록.pdf',
            'format': 'pdf',
            'structure': {'sections': ['개요', '결정사항']},
            'created_at': '2026-03-22T10:00:00.000Z',
          },
          statusCode: 201,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await templateApi.uploadTemplate(testFile);

      // Assert
      expect(result.templateId, 'tmpl-001');
      expect(result.name, '표준_회의록.pdf');
      expect(result.format, 'pdf');
      expect(result.structure, isNotNull);
      expect(result.createdAt, isA<DateTime>());
    });

    // uploadTemplate: 업로드 실패 시 예외 전파 테스트
    test('uploadTemplate이 서버 오류 시 DioException을 전파해야 함', () async {
      // Arrange - 실제 임시 파일 생성
      final testFile = File('${tempDir.path}/test.pdf');
      await testFile.writeAsString('PDF content');

      when(
        () => mockDio.post(
          any(),
          data: any(named: 'data'),
          options: any(named: 'options'),
        ),
      ).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          message: '서버 오류',
        ),
      );

      // Act & Assert
      expect(
        () => templateApi.uploadTemplate(testFile),
        throwsA(isA<DioException>()),
      );
    });

    // getTemplates: 템플릿 목록 조회 성공 테스트
    test('getTemplates가 Template 객체 목록을 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: [
            {
              'template_id': 'tmpl-001',
              'name': '표준 회의록.pdf',
              'format': 'pdf',
              'created_at': '2026-03-22T10:00:00.000Z',
            },
            {
              'template_id': 'tmpl-002',
              'name': '팀 미팅 양식.docx',
              'format': 'docx',
              'created_at': '2026-03-21T09:00:00.000Z',
            },
          ],
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await templateApi.getTemplates();

      // Assert
      expect(result, hasLength(2));
      expect(result[0].templateId, 'tmpl-001');
      expect(result[0].format, 'pdf');
      expect(result[1].templateId, 'tmpl-002');
      expect(result[1].format, 'docx');
      verify(() => mockDio.get('/templates')).called(1);
    });

    // getTemplates: 빈 목록 반환 테스트
    test('getTemplates가 템플릿이 없을 때 빈 목록을 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: [],
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await templateApi.getTemplates();

      // Assert
      expect(result, isEmpty);
    });

    // getTemplate: 단일 템플릿 조회 성공 테스트
    test('getTemplate이 templateId로 단일 Template 객체를 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'template_id': 'tmpl-001',
            'name': '표준 회의록.pdf',
            'format': 'pdf',
            'structure': {'sections': ['개요', '결정사항', '다음 단계']},
            'created_at': '2026-03-22T10:00:00.000Z',
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await templateApi.getTemplate('tmpl-001');

      // Assert
      expect(result.templateId, 'tmpl-001');
      expect(result.name, '표준 회의록.pdf');
      expect(result.structure, isNotNull);
      verify(() => mockDio.get('/templates/tmpl-001')).called(1);
    });

    // deleteTemplate: 템플릿 삭제 성공 테스트
    test('deleteTemplate이 템플릿을 삭제하고 완료해야 함', () async {
      // Arrange
      when(() => mockDio.delete(any())).thenAnswer(
        (_) async => Response(
          data: null,
          statusCode: 204,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      await templateApi.deleteTemplate('tmpl-001');

      // Assert: 예외 없이 완료
      verify(() => mockDio.delete('/templates/tmpl-001')).called(1);
    });

    // deleteTemplate: 존재하지 않는 템플릿 삭제 시 예외 테스트
    test('deleteTemplate이 404 오류 시 DioException을 전파해야 함', () async {
      // Arrange
      when(() => mockDio.delete(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          response: Response(
            statusCode: 404,
            requestOptions: RequestOptions(path: ''),
          ),
          type: DioExceptionType.badResponse,
        ),
      );

      // Act & Assert
      expect(
        () => templateApi.deleteTemplate('unknown-id'),
        throwsA(isA<DioException>()),
      );
    });
  });
}
