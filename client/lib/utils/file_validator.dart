import 'dart:io';
import 'dart:typed_data';

class FileValidationResult {
  final bool isValid;
  final String? errorMessage;
  const FileValidationResult.valid() : isValid = true, errorMessage = null;
  const FileValidationResult.invalid(this.errorMessage)
      : isValid = false;
}

const _allowedExtensions = {'.wav', '.mp3', '.m4a', '.ogg'};
const _maxFileSizeBytes = 500 * 1024 * 1024;

const _magicBytes = <String, List<int>>{
  '.wav': [0x52, 0x49, 0x46, 0x46],
  '.mp3': [0x49, 0x44, 0x33],
  '.m4a': [0x66, 0x74, 0x79, 0x70],
  '.ogg': [0x4F, 0x67, 0x67, 0x53],
};

const _magicByteOffsets = <String, int>{
  '.wav': 0,
  '.mp3': 0,
  '.m4a': 4,
  '.ogg': 0,
};

const _mp3FrameSyncBytes = [0xFF, 0xFB, 0xFF, 0xF3, 0xFF, 0xF2];

String _getExtension(String filename) {
  final dotIndex = filename.lastIndexOf('.');
  if (dotIndex < 0) return '';
  return filename.substring(dotIndex).toLowerCase();
}

bool _checkMagicBytes(Uint8List header, String ext) {
  final expected = _magicBytes[ext];
  final offset = _magicByteOffsets[ext] ?? 0;
  if (expected == null) return true;

  if (header.length < offset + expected.length) return false;
  for (var i = 0; i < expected.length; i++) {
    if (header[offset + i] != expected[i]) {
      if (ext == '.mp3') {
        return _checkMp3FrameSync(header);
      }
      return false;
    }
  }

  if (ext == '.wav' && header.length >= 12) {
    return header[8] == 0x57 &&
        header[9] == 0x41 &&
        header[10] == 0x56 &&
        header[11] == 0x45;
  }

  return true;
}

bool _checkMp3FrameSync(Uint8List header) {
  if (header.length < 2) return false;
  for (var i = 0; i < _mp3FrameSyncBytes.length; i += 2) {
    if (header[0] == _mp3FrameSyncBytes[i] &&
        header[1] == _mp3FrameSyncBytes[i + 1]) {
      return true;
    }
  }
  return false;
}

Future<FileValidationResult> validateAudioFile(String filePath) async {
  final filename = filePath.split('/').last;
  final ext = _getExtension(filename);

  if (!_allowedExtensions.contains(ext)) {
    return FileValidationResult.invalid(
      '지원하지 않는 파일 형식입니다. 허용: WAV, MP3, M4A, OGG (받은 형식: $ext)',
    );
  }

  final file = File(filePath);
  final fileSize = await file.length();
  if (fileSize == 0) {
    return const FileValidationResult.invalid('빈 파일은 업로드할 수 없습니다.');
  }
  if (fileSize > _maxFileSizeBytes) {
    const maxMb = _maxFileSizeBytes ~/ (1024 * 1024);
    final actualMb = (fileSize / (1024 * 1024)).toStringAsFixed(1);
    return FileValidationResult.invalid(
      '파일 크기가 제한(${maxMb}MB)을 초과합니다. 실제 크기: ${actualMb}MB',
    );
  }

  final raf = await file.open();
  try {
    final header = await raf.read(16);
    if (!_checkMagicBytes(header, ext)) {
      return const FileValidationResult.invalid(
        '파일 시그니처(매직 바이트)가 확장자와 일치하지 않습니다.',
      );
    }
  } finally {
    await raf.close();
  }

  return const FileValidationResult.valid();
}
