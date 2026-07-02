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

String audioEnhancementErrorMessage(Object error) {
  if (error is DioException) {
    final statusCode = error.response?.statusCode;
    if (statusCode == 401 || statusCode == 403) {
      return '오디오 향상 인증이 만료되었습니다. 다시 로그인하거나 게스트로 시작한 뒤 시도해주세요.';
    }
    if (statusCode == 413) {
      return '오디오 파일이 너무 큽니다. 100MB 이하 파일로 다시 시도해주세요.';
    }
    if (statusCode == 422) {
      return _responseDetail(error.response?.data) ??
          '지원하지 않는 오디오 파일이거나 파일을 읽을 수 없습니다.';
    }

    return switch (error.type) {
      DioExceptionType.connectionTimeout => '서버 연결 시간이 초과되었습니다.',
      DioExceptionType.receiveTimeout => '서버 응답 시간이 초과되었습니다.',
      DioExceptionType.sendTimeout => '오디오 파일 전송 시간이 초과되었습니다.',
      DioExceptionType.connectionError => '서버에 연결할 수 없습니다. 네트워크를 확인해주세요.',
      DioExceptionType.badResponse
          when statusCode != null && statusCode >= 500 =>
        '서버에서 오디오 향상을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.',
      DioExceptionType.badResponse =>
        '오디오 향상 요청이 실패했습니다. (${statusCode ?? '응답 오류'})',
      _ => '오디오 향상 중 네트워크 오류가 발생했습니다.',
    };
  }

  final message = error.toString().replaceFirst('Exception: ', '').trim();
  if (message.isEmpty) {
    return '오디오 향상 중 오류가 발생했습니다.';
  }
  if (message.contains('401') || message.contains('Unauthorized')) {
    return '오디오 향상 인증이 만료되었습니다. 다시 로그인하거나 게스트로 시작한 뒤 시도해주세요.';
  }
  return message;
}

String? _responseDetail(Object? data) {
  if (data is Map) {
    final detail = data['detail'];
    if (detail is String && detail.isNotEmpty) return detail;
    if (detail is Map) {
      final message = detail['message'] ?? detail['msg'];
      if (message is String && message.isNotEmpty) return message;
    }
  }
  return null;
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
