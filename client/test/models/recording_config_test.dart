// RecordingConfig 모델 테스트
// SPEC-APP-005 REQ-003
import 'package:flutter_test/flutter_test.dart';
import 'package:record/record.dart';
import 'package:voice_to_textnote/models/recording_config.dart';

void main() {
  group('RecordingConfig 모델', () {
    test('생성자가 모든 필드를 올바르게 설정해야 함', () {
      const config = RecordingConfig(
        encoder: AudioEncoder.aacLc,
        sampleRate: 44100,
        bitRate: 128000,
        label: '커스텀',
      );

      expect(config.encoder, AudioEncoder.aacLc);
      expect(config.sampleRate, 44100);
      expect(config.bitRate, 128000);
      expect(config.label, '커스텀');
    });

    test('standard 프리셋이 올바른 값을 가져야 함', () {
      const config = RecordingConfig.standard;

      expect(config.encoder, AudioEncoder.aacLc);
      expect(config.sampleRate, 44100);
      expect(config.bitRate, 128000);
      expect(config.label, '표준');
    });

    test('highQuality 프리셋이 올바른 값을 가져야 함', () {
      const config = RecordingConfig.highQuality;

      expect(config.encoder, AudioEncoder.aacLc);
      expect(config.sampleRate, 48000);
      expect(config.bitRate, 256000);
      expect(config.label, '고품질');
    });

    test('economy 프리셋이 올바른 값을 가져야 함', () {
      const config = RecordingConfig.economy;

      expect(config.encoder, AudioEncoder.aacLc);
      expect(config.sampleRate, 22050);
      expect(config.bitRate, 64000);
      expect(config.label, '절약');
    });

    test('presets getter가 3개 프리셋을 반환해야 함', () {
      final presets = RecordingConfig.presets;

      expect(presets.length, 3);
      expect(presets[0], RecordingConfig.standard);
      expect(presets[1], RecordingConfig.highQuality);
      expect(presets[2], RecordingConfig.economy);
    });

    test('fromIndex가 올바른 프리셋을 반환해야 함', () {
      expect(RecordingConfig.fromIndex(0), RecordingConfig.standard);
      expect(RecordingConfig.fromIndex(1), RecordingConfig.highQuality);
      expect(RecordingConfig.fromIndex(2), RecordingConfig.economy);
    });

    test('fromIndex가 범위를 벗어나면 standard를 반환해야 함', () {
      expect(RecordingConfig.fromIndex(-1), RecordingConfig.standard);
      expect(RecordingConfig.fromIndex(3), RecordingConfig.standard);
      expect(RecordingConfig.fromIndex(999), RecordingConfig.standard);
    });

    test('presetIndex가 올바른 인덱스를 반환해야 함', () {
      expect(RecordingConfig.standard.presetIndex, 0);
      expect(RecordingConfig.highQuality.presetIndex, 1);
      expect(RecordingConfig.economy.presetIndex, 2);
    });

    test('storageKey가 올바른 형식이어야 함', () {
      expect(RecordingConfig.standard.storageKey, 'recording_quality_44100_128000');
      expect(RecordingConfig.highQuality.storageKey, 'recording_quality_48000_256000');
      expect(RecordingConfig.economy.storageKey, 'recording_quality_22050_64000');
    });

    test('summary가 올바른 문자열을 반환해야 함', () {
      expect(RecordingConfig.standard.summary, '표준 · 44.1kHz · 128kbps');
      expect(RecordingConfig.highQuality.summary, '고품질 · 48.0kHz · 256kbps');
      expect(RecordingConfig.economy.summary, '절약 · 22.1kHz · 64kbps');
    });

    test('operator ==가 동등성을 올바르게 판별해야 함', () {
      const config1 = RecordingConfig.standard;
      const config2 = RecordingConfig.standard;
      const config3 = RecordingConfig.highQuality;

      expect(config1 == config2, isTrue);
      expect(config1 == config3, isFalse);
    });

    test('hashCode가 동등한 객체에 대해 같은 값을 가져야 함', () {
      const config1 = RecordingConfig.standard;
      const config2 = RecordingConfig.standard;

      expect(config1.hashCode, config2.hashCode);
    });

    test('toRecordConfig가 올바른 RecordConfig를 반환해야 함', () {
      const config = RecordingConfig.standard;
      final recordConfig = config.toRecordConfig();

      expect(recordConfig.encoder, AudioEncoder.aacLc);
      expect(recordConfig.sampleRate, 44100);
      expect(recordConfig.bitRate, 128000);
    });
  });
}
