import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/audio_preprocessor.dart';

Future<String> _mockSuccessfulConverter(
  String inputPath,
  String outputPath, {
  int sampleRate = 16000,
  int channels = 1,
  int bitDepth = 16,
}) async {
  final outputFile = File(outputPath);
  await outputFile.create(recursive: true);
  await outputFile.writeAsBytes(
    _buildWavHeader(
      sampleRate: sampleRate,
      channels: channels,
      bitDepth: bitDepth,
      dataSize: 0,
    ),
  );
  return outputPath;
}

Future<String> _mockFailingConverter(
  String inputPath,
  String outputPath, {
  int sampleRate = 16000,
  int channels = 1,
  int bitDepth = 16,
}) async {
  await File(outputPath).writeAsBytes([0x00], flush: true);
  throw const FormatException('mock conversion failed');
}

List<int> _buildWavHeader({
  required int sampleRate,
  required int channels,
  required int bitDepth,
  required int dataSize,
}) {
  final header = List<int>.filled(44, 0);
  final byteRate = sampleRate * channels * bitDepth ~/ 8;
  final blockAlign = channels * bitDepth ~/ 8;

  void writeAscii(int offset, String value) {
    header.setRange(offset, offset + value.length, value.codeUnits);
  }

  void writeUint16LE(int offset, int value) {
    header[offset] = value & 0xff;
    header[offset + 1] = (value >> 8) & 0xff;
  }

  void writeUint32LE(int offset, int value) {
    header[offset] = value & 0xff;
    header[offset + 1] = (value >> 8) & 0xff;
    header[offset + 2] = (value >> 16) & 0xff;
    header[offset + 3] = (value >> 24) & 0xff;
  }

  writeAscii(0, 'RIFF');
  writeUint32LE(4, 36 + dataSize);
  writeAscii(8, 'WAVE');
  writeAscii(12, 'fmt ');
  writeUint32LE(16, 16); // PCM fmt chunk size
  writeUint16LE(20, 1); // PCM audio format
  writeUint16LE(22, channels);
  writeUint32LE(24, sampleRate);
  writeUint32LE(28, byteRate);
  writeUint16LE(32, blockAlign);
  writeUint16LE(34, bitDepth);
  writeAscii(36, 'data');
  writeUint32LE(40, dataSize);

  return header;
}

void main() {
  group('AudioPreprocessor', () {
    late AudioPreprocessor preprocessor;
    late String testAssetsPath;
    late Directory tempDir;

    setUp(() async {
      preprocessor = AudioPreprocessor();
      tempDir =
          await Directory.systemTemp.createTemp('audio_preprocessor_test_');
      testAssetsPath = tempDir.path;
    });

    tearDown(() async {
      // 테스트 후 임시 파일 정리
      if (await tempDir.exists()) {
        await tempDir.delete(recursive: true);
      }
    });

    group('convertToWav', () {
      test('빈 파일 경로일 때 예외 발생', () async {
        await expectLater(
          () => preprocessor.convertToWav(''),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('존재하지 않는 파일일 때 예외 발생', () async {
        await expectLater(
          () => preprocessor.convertToWav('/nonexistent/file.m4a'),
          throwsA(isA<FileSystemException>()),
        );
      });

      test('M4A 파일을 16kHz mono WAV로 변환', () async {
        final preprocessor = AudioPreprocessor(
          converter: _mockSuccessfulConverter,
        );

        // Given: 테스트용 M4A 파일 생성 (시뮬레이션)
        final testFile = File('$testAssetsPath/test.m4a');
        await testFile.create(recursive: true);
        await testFile.writeAsBytes([0x00, 0x01, 0x02]); // Dummy data

        // When: WAV 변환
        final result = await preprocessor.convertToWav(testFile.path);

        // Then: WAV 파일 생성 확인
        expect(result, isNotNull);
        expect(await result.exists(), isTrue);
        expect(result.path.endsWith('.wav'), isTrue);

        // WAV 파일 헤더 검증 (RIFF, WAVE, fmt 청크)
        final bytes = await result.readAsBytes();
        expect(bytes.sublist(0, 4), [0x52, 0x49, 0x46, 0x46]); // "RIFF"
        expect(bytes.sublist(8, 12), [0x57, 0x41, 0x56, 0x45]); // "WAVE"
        expect(bytes.sublist(12, 16), [0x66, 0x6d, 0x74, 0x20]); // "fmt "
        expect(bytes.sublist(24, 28), [0x80, 0x3e, 0x00, 0x00]); // 16kHz
        expect(bytes.sublist(22, 24), [0x01, 0x00]); // mono
        expect(bytes.sublist(34, 36), [0x10, 0x00]); // 16-bit
      });

      test('이미 WAV 파일일 때 복사만 수행', () async {
        // Given: WAV 파일 생성
        final testFile = File('$testAssetsPath/test.wav');
        await testFile.create(recursive: true);
        await testFile.writeAsBytes([0x52, 0x49, 0x46, 0x46]); // WAV 헤더

        // When: WAV 변환
        final result = await preprocessor.convertToWav(testFile.path);

        // Then: 같은 파일 반환
        expect(result.path, equals(testFile.path));
      });

      test('빈 파일(0 bytes) 입력 시 FormatException 발생', () async {
        // Given: 비어있는 M4A 파일 생성
        final testFile = File('$testAssetsPath/empty.m4a');
        await testFile.create(recursive: true);

        // When & Then: 변환 전 입력 검증에서 실패
        await expectLater(
          () => preprocessor.convertToWav(testFile.path),
          throwsA(isA<FormatException>()),
        );
      });

      test('변환 실패 시 임시 파일 정리', () async {
        final preprocessor = AudioPreprocessor(converter: _mockFailingConverter);

        // Given: 손상된 파일
        final testFile = File('$testAssetsPath/corrupted.m4a');
        await testFile.create(recursive: true);
        await testFile.writeAsBytes([0x00, 0x01, 0x02]);

        // When & Then: 변환 실패 시 임시 파일 존재하지 않음
        try {
          await preprocessor.convertToWav(testFile.path);
          fail('예외가 발생해야 합니다');
        } catch (_) {
          // 임시 WAV 파일 정리 확인
          final tempWav = File('$testAssetsPath/corrupted.wav');
          expect(await tempWav.exists(), isFalse);
        }
      });

      test('변환 완료 후 원본 M4A 파일 유지', () async {
        final preprocessor = AudioPreprocessor(
          converter: _mockSuccessfulConverter,
        );

        // Given: M4A 파일 생성
        final testFile = File('$testAssetsPath/test.m4a');
        await testFile.create(recursive: true);
        await testFile.writeAsBytes([0x00, 0x01, 0x02]);

        // When: WAV 변환
        await preprocessor.convertToWav(testFile.path);

        // Then: 원본 파일 존재
        expect(await testFile.exists(), isTrue);
      });
    });

    group('cleanupTempFiles', () {
      test('지정된 디렉토리의 WAV 파일 삭제', () async {
        // Given: WAV 파일 생성
        final wavFile = File('$testAssetsPath/temp.wav');
        await wavFile.create(recursive: true);

        // When: 정리 실행
        await preprocessor.cleanupTempFiles(testAssetsPath);

        // Then: WAV 파일 삭제
        expect(await wavFile.exists(), isFalse);
      });

      test('WAV 확장자가 아닌 파일은 삭제 안 함', () async {
        // Given: 다른 확장자 파일 생성
        final txtFile = File('$testAssetsPath/notes.txt');
        await txtFile.create(recursive: true);

        // When: 정리 실행
        await preprocessor.cleanupTempFiles(testAssetsPath);

        // Then: 파일 유지
        expect(await txtFile.exists(), isTrue);
      });

      test('빈 디렉토리일 때 정상 완료', () async {
        // When: 빈 디렉토리 정리
        await expectLater(
          () => preprocessor.cleanupTempFiles(testAssetsPath),
          returnsNormally,
        );
      });
    });
  });
}
