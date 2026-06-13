import 'dart:developer' as developer;
import 'dart:io';

import 'package:audio_decoder/audio_decoder.dart';

typedef WavConverter = Future<String> Function(
  String inputPath,
  String outputPath, {
  int sampleRate,
  int channels,
  int bitDepth,
});

/// @MX:SPEC:REQ-MOBILE-008-01
///
/// M4A 오디오 파일을 16kHz mono WAV 형식으로 변환하는 전처리기
///
/// Native 플랫폼 API를 사용해 실제 오디오 디코딩과 WAV 변환을 수행합니다.
class AudioPreprocessor {
  final WavConverter _convertToWav;

  AudioPreprocessor({WavConverter? converter})
      : _convertToWav = converter ?? AudioDecoder.convertToWav;

  /// WAV 파일 샘플 레이트 (16kHz)
  static const int _sampleRate = 16000;

  /// WAV 파일 채널 (mono)
  static const int _channels = 1;

  /// PCM bit depth
  static const int _bitsPerSample = 16;

  /// M4A 파일을 16kHz mono WAV로 변환
  ///
  /// [m4aPath] 변환할 M4A 파일 경로
  ///
  /// 반환: 변환된 WAV 파일
  ///
  /// 예외 발생 상황:
  /// - [ArgumentError]: 빈 경로 입력
  /// - [FileNotFoundException]: 파일 없음
  /// - [FormatException]: 변환 실패
  Future<File> convertToWav(String m4aPath) async {
    // 경로 검증
    if (m4aPath.isEmpty) {
      throw ArgumentError('파일 경로가 비어있습니다');
    }

    final inputFile = File(m4aPath);
    if (!await inputFile.exists()) {
      throw FileSystemException('파일을 찾을 수 없습니다', m4aPath);
    }

    // 이미 WAV 파일일 경우 복사만 수행
    if (m4aPath.toLowerCase().endsWith('.wav')) {
      return inputFile;
    }

    if (await inputFile.length() == 0) {
      throw const FormatException('입력 오디오 파일이 비어있습니다');
    }

    // Native 디코더가 실제 PCM 변환을 수행하도록 출력 경로만 준비합니다.
    final outputPath = _getWavPath(m4aPath);
    final outputFile = await _createWavFile(inputFile, outputPath);

    return outputFile;
  }

  /// 임시 WAV 파일 정리
  ///
  /// [directory] 정리할 디렉토리 경로
  Future<void> cleanupTempFiles(String directory) async {
    final dir = Directory(directory);
    if (!await dir.exists()) {
      return;
    }

    try {
      // WAV 파일만 삭제
      await for (final entity in dir.list()) {
        if (entity is File && entity.path.endsWith('.wav')) {
          await entity.delete();
        }
      }
    } on FileSystemException catch (e) {
      developer.log('임시 파일 정리 실패', error: e);
    }
  }

  /// WAV 파일 경로 생성
  String _getWavPath(String m4aPath) {
    final pathWithoutExt =
        m4aPath.replaceAll(RegExp(r'\.m4a$', caseSensitive: false), '');
    return '$pathWithoutExt.wav';
  }

  /// Native 플랫폼 API로 WAV 파일 생성
  Future<File> _createWavFile(File inputFile, String outputPath) async {
    final outputFile = File(outputPath);

    try {
      final wavPath = await _convertToWav(
        inputFile.path,
        outputPath,
        sampleRate: _sampleRate,
        channels: _channels,
        bitDepth: _bitsPerSample,
      );

      return File(wavPath);
    } catch (e) {
      // 변환 실패 시 생성된 파일 정리
      if (await outputFile.exists()) {
        await outputFile.delete();
      }
      throw FormatException('WAV 변환 실패: $e');
    }
  }
}
