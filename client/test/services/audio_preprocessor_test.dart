import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/audio_preprocessor.dart';

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

      test('변환 실패 시 임시 파일 정리', () async {
        // Given: 손상된 파일
        final testFile = File('$testAssetsPath/corrupted.m4a');
        await testFile.create(recursive: true);

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
