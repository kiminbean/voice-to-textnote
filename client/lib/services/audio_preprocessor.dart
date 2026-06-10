import 'dart:developer' as developer;
import 'dart:io';
import 'dart:typed_data';

/// @MX:SPEC:REQ-MOBILE-008-01
///
/// M4A 오디오 파일을 16kHz mono WAV 형식으로 변환하는 전처리기
///
/// 현재 구현은 시뮬레이션 패턴을 사용합니다. 실제 ffmpeg 변환은
/// Native 플러그인 통합이 필요하므로 추후 구현 예정입니다.
class AudioPreprocessor {
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

    // WAV 변환 (시뮬레이션)
    // TODO: 실제 ffmpeg 통합 필요 (Native 플러그인)
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

  /// WAV 파일 생성 (시뮬레이션)
  ///
  /// 실제 구현에서는 ffmpeg를 사용하여:
  /// - 16kHz 샘플 레이트 변환
  /// - mono 채널 변환
  /// - PCM 16-bit 인코딩
  Future<File> _createWavFile(File inputFile, String outputPath) async {
    final outputFile = File(outputPath);

    try {
      // 원본 데이터 읽기 (실제로는 ffmpeg 처리)
      final inputData = await inputFile.readAsBytes();

      // WAV 헤더 생성 (시뮬레이션)
      final wavData = _generateWavHeader(inputData.length);

      // WAV 파일 쓰기
      await outputFile.writeAsBytes([...wavData, ...inputData]);

      return outputFile;
    } catch (e) {
      // 변환 실패 시 생성된 파일 정리
      if (await outputFile.exists()) {
        await outputFile.delete();
      }
      throw FormatException('WAV 변환 실패: $e');
    }
  }

  /// WAV 파일 헤더 생성 (16kHz, mono, 16-bit PCM)
  List<int> _generateWavHeader(int dataLength) {
    final header = ByteData(44);
    final bytes = header.buffer.asUint8List();

    void writeAscii(int offset, String value) {
      for (var i = 0; i < value.length; i++) {
        bytes[offset + i] = value.codeUnitAt(i);
      }
    }

    const byteRate = _sampleRate * _channels * _bitsPerSample ~/ 8;
    const blockAlign = _channels * _bitsPerSample ~/ 8;

    writeAscii(0, 'RIFF');
    header.setUint32(4, 36 + dataLength, Endian.little);
    writeAscii(8, 'WAVE');
    writeAscii(12, 'fmt ');
    header.setUint32(16, 16, Endian.little);
    header.setUint16(20, 1, Endian.little);
    header.setUint16(22, _channels, Endian.little);
    header.setUint32(24, _sampleRate, Endian.little);
    header.setUint32(28, byteRate, Endian.little);
    header.setUint16(32, blockAlign, Endian.little);
    header.setUint16(34, _bitsPerSample, Endian.little);
    writeAscii(36, 'data');
    header.setUint32(40, dataLength, Endian.little);

    return bytes;
  }
}
