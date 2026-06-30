// SPEC-MOBILE-002: 오프라인 STT 모델 관리 (다운로드, 검증, 삭제)
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/services/local_stt_service.dart';

final modelManagerProvider = Provider<SttModelManager>((ref) {
  return SttModelManager();
});

enum ModelDownloadState { notDownloaded, downloading, verifying, ready, error }

class SttModelInfo {
  final String id;
  final String displayName;
  final String downloadUrl;
  final int sizeBytes;
  final String sha256Checksum;

  const SttModelInfo({
    required this.id,
    required this.displayName,
    required this.downloadUrl,
    required this.sizeBytes,
    required this.sha256Checksum,
  });

  static const whisperBase = SttModelInfo(
    id: 'whisper-base',
    displayName: 'Whisper Base (오프라인)',
    downloadUrl:
        'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin',
    sizeBytes: 147951465,
    sha256Checksum:
        '60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe',
  );
}

class SttModelStatus {
  final ModelDownloadState state;
  final double progress;
  final String? errorMessage;

  const SttModelStatus({
    required this.state,
    this.progress = 0.0,
    this.errorMessage,
  });

  const SttModelStatus.initial()
      : state = ModelDownloadState.notDownloaded,
        progress = 0.0,
        errorMessage = null;

  SttModelStatus copyWith({
    ModelDownloadState? state,
    double? progress,
    String? errorMessage,
  }) {
    return SttModelStatus(
      state: state ?? this.state,
      progress: progress ?? this.progress,
      errorMessage: errorMessage,
    );
  }
}

class SttModelManager implements LocalSttModelSource {
  static const _kPrefsModelPath = 'stt_model_path';
  static const _kPrefsModelId = 'stt_model_id';

  final SttModelInfo _defaultModel = SttModelInfo.whisperBase;

  SttModelInfo get defaultModel => _defaultModel;

  Future<Directory> _getModelsDir() async {
    final appDir = await getApplicationDocumentsDirectory();
    final modelsDir = Directory('${appDir.path}/stt_models');
    if (!modelsDir.existsSync()) {
      await modelsDir.create(recursive: true);
    }
    return modelsDir;
  }

  @override
  Future<String?> getModelPath() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_kPrefsModelPath);
  }

  @override
  Future<bool> isModelReady() async {
    final path = await getModelPath();
    if (path == null) return false;
    final file = File(path);
    return file.existsSync() && file.lengthSync() == _defaultModel.sizeBytes;
  }

  Future<void> deleteModel() async {
    final prefs = await SharedPreferences.getInstance();
    final path = prefs.getString(_kPrefsModelPath);
    if (path != null) {
      final file = File(path);
      if (file.existsSync()) {
        await file.delete();
      }
    }
    await prefs.remove(_kPrefsModelPath);
    await prefs.remove(_kPrefsModelId);
  }

  String _getExpectedPath(Directory modelsDir) {
    return '${modelsDir.path}/${_defaultModel.id}.bin';
  }

  Future<bool> verifyExistingModel() async {
    final path = await getModelPath();
    if (path == null) return false;
    final file = File(path);
    if (!file.existsSync()) return false;

    final actualSize = file.lengthSync();
    if (actualSize != _defaultModel.sizeBytes) {
      await deleteModel();
      return false;
    }

    return true;
  }

  Future<void> markModelReady(String modelPath) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kPrefsModelPath, modelPath);
    await prefs.setString(_kPrefsModelId, _defaultModel.id);
  }

  Future<File> getModelFile() async {
    final dir = await _getModelsDir();
    return File(_getExpectedPath(dir));
  }

  Future<String> getExpectedModelPath() async {
    final dir = await _getModelsDir();
    return _getExpectedPath(dir);
  }
}
