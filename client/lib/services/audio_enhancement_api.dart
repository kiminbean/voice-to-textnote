import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'package:voice_to_textnote/services/api_client.dart';
import 'package:voice_to_textnote/utils/file_validator.dart';

final audioEnhancementApiProvider = Provider<AudioEnhancementApi>((ref) {
  final dio = ref.watch(dioProvider);
  return AudioEnhancementApi(dio);
});

enum EnhancementMode {
  clean('clean'),
  enhanced('enhanced'),
  speechOnly('speech_only'),
  musicFocused('music_focused');

  const EnhancementMode(this.value);
  final String value;
}

enum NoiseReductionLevel {
  light('light'),
  moderate('moderate'),
  aggressive('aggressive');

  const NoiseReductionLevel(this.value);
  final String value;
}

enum VoiceEnhancementMode {
  natural('natural'),
  clear('clear'),
  broadcast('broadcast');

  const VoiceEnhancementMode(this.value);
  final String value;
}

class AudioEnhancementOptions {
  final EnhancementMode enhancementMode;
  final NoiseReductionLevel noiseReductionLevel;
  final VoiceEnhancementMode voiceEnhancement;
  final bool extractSpeechOnly;
  final bool normalizeAudio;
  final int targetSampleRate;

  const AudioEnhancementOptions({
    this.enhancementMode = EnhancementMode.enhanced,
    this.noiseReductionLevel = NoiseReductionLevel.moderate,
    this.voiceEnhancement = VoiceEnhancementMode.natural,
    this.extractSpeechOnly = false,
    this.normalizeAudio = true,
    this.targetSampleRate = 16000,
  });

  Map<String, dynamic> toFormFields() => {
        'enhancement_mode': enhancementMode.value,
        'noise_reduction_level': noiseReductionLevel.value,
        'voice_enhancement': voiceEnhancement.value,
        'extract_speech_only': extractSpeechOnly.toString(),
        'normalize_audio': normalizeAudio.toString(),
        'target_sample_rate': targetSampleRate.toString(),
      };
}

class AudioEnhancementResponse {
  final String taskId;
  final String status;
  final AudioEnhancementResult? result;
  final String? errorMessage;

  const AudioEnhancementResponse({
    required this.taskId,
    required this.status,
    this.result,
    this.errorMessage,
  });

  factory AudioEnhancementResponse.fromJson(Map<String, dynamic> json) {
    final resultJson = json['result'];
    return AudioEnhancementResponse(
      taskId: json['task_id'] as String,
      status: json['status'] as String,
      result: resultJson is Map<String, dynamic>
          ? AudioEnhancementResult.fromJson(resultJson)
          : null,
      errorMessage: json['error_message'] as String?,
    );
  }
}

class AudioEnhancementStatus {
  final String taskId;
  final String status;
  final double progressPercent;
  final String currentStep;
  final String? errorMessage;

  const AudioEnhancementStatus({
    required this.taskId,
    required this.status,
    required this.progressPercent,
    required this.currentStep,
    this.errorMessage,
  });

  factory AudioEnhancementStatus.fromJson(Map<String, dynamic> json) {
    return AudioEnhancementStatus(
      taskId: json['task_id'] as String,
      status: json['status'] as String,
      progressPercent: (json['progress_percent'] as num).toDouble(),
      currentStep: json['current_step'] as String,
      errorMessage: json['error_message'] as String?,
    );
  }
}

class AudioEnhancementResult {
  final int originalFileSize;
  final int enhancedFileSize;
  final double processingTimeSeconds;
  final double compressionRatio;
  final AudioQualityScore qualityScores;
  final List<String> warnings;

  const AudioEnhancementResult({
    required this.originalFileSize,
    required this.enhancedFileSize,
    required this.processingTimeSeconds,
    required this.compressionRatio,
    required this.qualityScores,
    required this.warnings,
  });

  factory AudioEnhancementResult.fromJson(Map<String, dynamic> json) {
    final warningsJson = json['warnings'];
    return AudioEnhancementResult(
      originalFileSize: json['original_file_size'] as int,
      enhancedFileSize: json['enhanced_file_size'] as int,
      processingTimeSeconds:
          (json['processing_time_seconds'] as num).toDouble(),
      compressionRatio: (json['compression_ratio'] as num).toDouble(),
      qualityScores: AudioQualityScore.fromJson(
        json['quality_scores'] as Map<String, dynamic>,
      ),
      warnings: warningsJson is List
          ? warningsJson.map((value) => value.toString()).toList()
          : const [],
    );
  }
}

class AudioQualityScore {
  final double overallScore;
  final double clarityScore;
  final double noiseLevel;
  final double volumeLevel;
  final double voiceActivityRatio;

  const AudioQualityScore({
    required this.overallScore,
    required this.clarityScore,
    required this.noiseLevel,
    required this.volumeLevel,
    required this.voiceActivityRatio,
  });

  factory AudioQualityScore.fromJson(Map<String, dynamic> json) {
    return AudioQualityScore(
      overallScore: (json['overall_score'] as num).toDouble(),
      clarityScore: (json['clarity_score'] as num).toDouble(),
      noiseLevel: (json['noise_level'] as num).toDouble(),
      volumeLevel: (json['volume_level'] as num).toDouble(),
      voiceActivityRatio: (json['voice_activity_ratio'] as num).toDouble(),
    );
  }
}

class AudioEnhancementApi {
  final Dio _dio;

  AudioEnhancementApi(this._dio);

  Future<AudioEnhancementResponse> enhance(
    String filePath, {
    AudioEnhancementOptions options = const AudioEnhancementOptions(),
  }) async {
    final validation = await validateAudioFile(filePath);
    if (!validation.isValid) {
      throw Exception(validation.errorMessage);
    }

    final formData = FormData.fromMap({
      ...options.toFormFields(),
      'file': await MultipartFile.fromFile(
        filePath,
        filename: File(filePath).uri.pathSegments.last,
      ),
    });

    final response = await _dio.post(
      '/enhance',
      data: formData,
      options: Options(
        contentType: 'multipart/form-data',
        sendTimeout: AppConfig.uploadSendTimeout,
        receiveTimeout: AppConfig.uploadReceiveTimeout,
      ),
    );

    return AudioEnhancementResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<AudioEnhancementStatus> getStatus(String taskId) async {
    final response = await _dio.get('/enhance/status/$taskId');
    return AudioEnhancementStatus.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<AudioEnhancementResponse> getResult(String taskId) async {
    final response = await _dio.get('/enhance/results/$taskId');
    return AudioEnhancementResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }
}
