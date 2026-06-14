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

void check(bool condition, String message) {
  if (!condition) {
    throw StateError(message);
  }
}

Future<void> main() async {
  final noModelRuntime = FakeLocalSttRuntime(available: true);
  final noModelService = LocalSttService(
    FakeModelManager(ready: false),
    runtime: noModelRuntime,
  );
  try {
    await noModelService.transcribe('/tmp/audio.wav');
    throw StateError('expected missing model failure');
  } on StateError catch (error) {
    check(error.message.contains('모델이 준비되지 않았습니다'), 'missing model error');
  }
  check(noModelRuntime.transcribeCalls == 0, 'runtime called without model');

  final unavailableRuntime = FakeLocalSttRuntime(
    available: false,
    info: 'whisper.cpp test runtime missing',
  );
  final unavailableService = LocalSttService(
    FakeModelManager(ready: true),
    runtime: unavailableRuntime,
  );
  check(
      await unavailableService.isAvailable() == false, 'runtime availability');
  check(
    (await unavailableService.modelInfo).contains('런타임 미연결'),
    'runtime info surfaced',
  );
  try {
    await unavailableService.transcribe('/tmp/audio.wav');
    throw StateError('expected unavailable runtime failure');
  } on StateError catch (error) {
    check(
      error.message.contains('오프라인 STT 런타임이 준비되지 않았습니다'),
      'unavailable runtime error',
    );
  }
  check(unavailableRuntime.transcribeCalls == 0,
      'runtime called while unavailable');

  final runtime = FakeLocalSttRuntime(available: true);
  final service = LocalSttService(
    FakeModelManager(ready: true),
    runtime: runtime,
  );
  final result = await service.transcribe('/tmp/audio.wav');
  check(runtime.transcribeCalls == 1, 'runtime call count');
  check(runtime.capturedAudioPath == '/tmp/audio.wav', 'audio path');
  check(runtime.capturedModelPath == '/tmp/whisper-base.bin', 'model path');
  check(runtime.capturedLanguage == 'ko', 'language');
  check(result.text == '회의록 초안 작성', 'result text');
  check(result.language == 'ko', 'result language');
  check(result.durationSeconds == 12, 'result duration');
  check(result.segments.length == 1, 'segment count');
  check(result.segments.single.confidence == 0.87, 'segment confidence');

  // ignore: avoid_print
  print('local_stt_smoke: PASS');
}
