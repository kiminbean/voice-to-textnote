// 녹음 품질 설정 모델
// @MX:NOTE: SPEC-APP-005 REQ-003 — 녹음 품질 프리셋 (표준/고품질/절약)

import 'package:record/record.dart';

/// 녹음 품질 설정
class RecordingConfig {
  final AudioEncoder encoder;
  final int sampleRate;
  final int bitRate;
  final String label;

  const RecordingConfig({
    required this.encoder,
    required this.sampleRate,
    required this.bitRate,
    required this.label,
  });

  /// 표준 (기본값): AAC-LC, 44.1kHz, 128kbps
  static const standard = RecordingConfig(
    encoder: AudioEncoder.aacLc,
    sampleRate: 44100,
    bitRate: 128000,
    label: '표준',
  );

  /// 고품질: AAC-LC, 48kHz, 256kbps
  static const highQuality = RecordingConfig(
    encoder: AudioEncoder.aacLc,
    sampleRate: 48000,
    bitRate: 256000,
    label: '고품질',
  );

  /// 절약: AAC-LC, 22.05kHz, 64kbps
  static const economy = RecordingConfig(
    encoder: AudioEncoder.aacLc,
    sampleRate: 22050,
    bitRate: 64000,
    label: '절약',
  );

  /// 모든 프리셋 목록
  static List<RecordingConfig> get presets => [
        standard,
        highQuality,
        economy,
      ];

  /// RecordConfig로 변환 (record 패키지용)
  RecordConfig toRecordConfig() => RecordConfig(
        encoder: encoder,
        sampleRate: sampleRate,
        bitRate: bitRate,
      );

  /// SharedPreferences 저장용 키
  String get storageKey => 'recording_quality_${sampleRate}_$bitRate';

  /// 인덱스에서 프리셋 가져오기
  static RecordingConfig fromIndex(int index) {
    if (index < 0 || index >= presets.length) return standard;
    return presets[index];
  }

  /// 현재 프리셋의 인덱스
  int get presetIndex => presets.indexWhere(
        (p) => p.sampleRate == sampleRate && p.bitRate == bitRate,
      );

  /// 설정 요약 문자열
  String get summary {
    final khz = (sampleRate / 1000).toStringAsFixed(1);
    final kbps = (bitRate / 1000).toInt();
    return '$label · ${khz}kHz · ${kbps}kbps';
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is RecordingConfig &&
          encoder == other.encoder &&
          sampleRate == other.sampleRate &&
          bitRate == other.bitRate;

  @override
  int get hashCode => Object.hash(encoder, sampleRate, bitRate);

  @override
  String toString() => 'RecordingConfig($summary)';
}
