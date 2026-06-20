import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/utils/file_validator.dart';

void main() {
  group('validateAudioFile', () {
    test('MP4 video containers with ftyp signature are accepted', () async {
      final file = File('${Directory.systemTemp.path}/voice_note_test.mp4');
      await file.writeAsBytes([
        0x00,
        0x00,
        0x00,
        0x20,
        0x66,
        0x74,
        0x79,
        0x70,
        0x69,
        0x73,
        0x6F,
        0x6D,
        0x00,
        0x00,
        0x00,
        0x00,
      ]);

      try {
        final result = await validateAudioFile(file.path);
        expect(result.isValid, isTrue);
      } finally {
        await file.delete();
      }
    });

    test('unknown extensions are rejected with the supported format list',
        () async {
      final file = File('${Directory.systemTemp.path}/voice_note_test.mov');
      await file.writeAsBytes([1, 2, 3, 4]);

      try {
        final result = await validateAudioFile(file.path);
        expect(result.isValid, isFalse);
        expect(result.errorMessage, contains('WAV, MP3, M4A, MP4, OGG'));
      } finally {
        await file.delete();
      }
    });
  });
}
