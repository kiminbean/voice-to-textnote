import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/model_manager.dart';

void main() {
  group('SttModelInfo', () {
    test('Whisper Base metadata must match the current whisper.cpp ggml file',
        () {
      const model = SttModelInfo.whisperBase;

      expect(model.id, 'whisper-base');
      expect(model.displayName, 'Whisper Base (오프라인)');
      expect(
        model.downloadUrl,
        'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin',
      );
      expect(model.sizeBytes, 147951465);
      expect(
        model.sha256Checksum,
        '60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe',
      );
    });
  });
}
