import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/local_stt_service.dart';

class FakeModelManager implements LocalSttModelSource {
  FakeModelManager({required this.ready, this.path = '/tmp/whisper-base.bin'});

  final bool ready;
  final String? path;

  @override
  Future<bool> isModelReady() async => ready;

  @override
  Future<String?> getModelPath() async => path;
}

class FakeLocalSttRuntime implements LocalSttRuntime {
  FakeLocalSttRuntime({
    required this.available,
    this.info = 'fake-whisper-runtime',
    this.result = const LocalSttResult(
      text: '회의록 초안 작성',
      language: 'ko',
      durationSeconds: 12,
      segments: [
        LocalSttSegment(
          id: 1,
          start: 0,
          end: 12.5,
          text: '회의록 초안 작성',
          confidence: 0.87,
        ),
      ],
    ),
  });

  final bool available;
  final String info;
  final LocalSttResult result;
  int transcribeCalls = 0;
  String? capturedAudioPath;
  String? capturedModelPath;
  String? capturedLanguage;

  @override
  Future<bool> isAvailable() async => available;

  @override
  Future<String> runtimeInfo() async => info;

  @override
  Future<LocalSttResult> transcribe({
    required String audioFilePath,
    required String modelPath,
    required String language,
  }) async {
    transcribeCalls++;
    capturedAudioPath = audioFilePath;
    capturedModelPath = modelPath;
    capturedLanguage = language;
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('LocalSttService', () {
    test('모델이 준비되지 않았으면 네이티브 STT를 호출하지 않아야 함', () async {
      final service = LocalSttService(
        FakeModelManager(ready: false),
        runtime: FakeLocalSttRuntime(available: true),
      );

      expect(
        () => service.transcribe('/tmp/audio.wav'),
        throwsA(isA<StateError>()),
      );
    });

    test('모델이 준비되어도 네이티브 런타임이 없으면 사용 불가여야 함', () async {
      final runtime = FakeLocalSttRuntime(
        available: false,
        info: 'whisper.cpp test runtime missing',
      );
      final service = LocalSttService(
        FakeModelManager(ready: true),
        runtime: runtime,
      );

      expect(await service.isAvailable(), isFalse);
      expect(await service.modelInfo, contains('런타임 미연결'));
      expect(
        () => service.transcribe('/tmp/audio.wav'),
        throwsA(
          isA<StateError>().having(
            (e) => e.message,
            'message',
            contains('오프라인 STT 런타임이 준비되지 않았습니다'),
          ),
        ),
      );
      expect(runtime.transcribeCalls, equals(0));
    });

    test('네이티브 STT 런타임 응답을 LocalSttResult로 반환해야 함', () async {
      final runtime = FakeLocalSttRuntime(available: true);
      final service = LocalSttService(
        FakeModelManager(ready: true),
        runtime: runtime,
      );

      final result = await service.transcribe('/tmp/audio.wav');

      expect(runtime.transcribeCalls, equals(1));
      expect(runtime.capturedAudioPath, equals('/tmp/audio.wav'));
      expect(runtime.capturedModelPath, equals('/tmp/whisper-base.bin'));
      expect(runtime.capturedLanguage, equals('ko'));
      expect(result.text, equals('회의록 초안 작성'));
      expect(result.language, equals('ko'));
      expect(result.durationSeconds, equals(12));
      expect(result.segments, hasLength(1));
      expect(result.segments.single.text, equals('회의록 초안 작성'));
      expect(result.segments.single.confidence, equals(0.87));
    });
  });
}
