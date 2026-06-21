import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/shared_import_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('com.voicetextnote.app/shared_import');

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  group('SharedImportPayload', () {
    test('shared YouTube URL is extracted and title is inferred', () {
      final payload = SharedImportPayload.fromPlatformMap({
        'text': 'https://youtu.be/example123',
        'mimeType': 'text/plain',
      });

      expect(payload.sourceUrl, equals('https://youtu.be/example123'));
      expect(payload.title, equals('YouTube transcript'));
      expect(payload.text, isNull);
      expect(payload.mimeType, equals('text/plain'));
    });

    test('shared URL plus transcript keeps transcript as editable content', () {
      final payload = SharedImportPayload.fromPlatformMap({
        'text': 'https://example.com/talk 오늘 강의에서는 검색 인덱싱과 요약 워크플로를 설명했습니다.',
      });

      expect(payload.sourceUrl, equals('https://example.com/talk'));
      expect(payload.title, equals('example.com transcript'));
      expect(payload.text, contains('검색 인덱싱'));
    });

    test('query parameters round trip into payload fields', () {
      const payload = SharedImportPayload(
        sourceUrl: 'https://example.com/article',
        text: '공유된 원문 transcript',
        title: 'Example transcript',
        mimeType: 'text/plain',
      );

      final restored =
          SharedImportPayload.fromQueryParameters(payload.toQueryParameters());

      expect(restored.sourceUrl, payload.sourceUrl);
      expect(restored.text, payload.text);
      expect(restored.title, payload.title);
      expect(restored.mimeType, payload.mimeType);
    });
  });

  group('SharedImportService', () {
    test('consumeInitialSharedImport returns parsed native payload', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
        expect(call.method, equals('consumeInitialSharedImport'));
        return {
          'text': 'https://owll.ai/ai-transcription transcript body for import',
          'mimeType': 'text/plain',
        };
      });

      final payload = await SharedImportService(channel: channel)
          .consumeInitialSharedImport();

      expect(payload, isNotNull);
      expect(payload!.sourceUrl, equals('https://owll.ai/ai-transcription'));
      expect(payload.text, equals('transcript body for import'));
    });

    test('consumeLatestSharedImport returns null when native payload is empty',
        () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async => null);

      final payload = await SharedImportService(channel: channel)
          .consumeLatestSharedImport();

      expect(payload, isNull);
    });
  });
}
