import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

final obsidianApiProvider = Provider<ObsidianApi>((ref) {
  final dio = ref.watch(dioProvider);
  return ObsidianApi(dio);
});

class ObsidianConfig {
  final String vaultPath;
  final String vaultName;
  final bool vaultValid;
  final String folderPattern;
  final String filenamePattern;
  final bool autoExport;
  final String conflictPolicy;
  final Map<String, dynamic>? frontmatterCustom;
  final String? noteTemplateId;

  const ObsidianConfig({
    required this.vaultPath,
    required this.vaultName,
    required this.vaultValid,
    required this.folderPattern,
    required this.filenamePattern,
    required this.autoExport,
    required this.conflictPolicy,
    this.frontmatterCustom,
    this.noteTemplateId,
  });

  factory ObsidianConfig.fromJson(Map<String, dynamic> json) => ObsidianConfig(
        vaultPath: json['vault_path'] as String? ?? '',
        vaultName: json['vault_name'] as String? ?? '',
        vaultValid: json['vault_valid'] as bool? ?? false,
        folderPattern: json['folder_pattern'] as String? ?? 'Voice-to-TextNote/{{date}}',
        filenamePattern: json['filename_pattern'] as String? ?? '{{date}}_{{title}}',
        autoExport: json['auto_export'] as bool? ?? false,
        conflictPolicy: json['conflict_policy'] as String? ?? 'overwrite',
        frontmatterCustom: json['frontmatter_custom'] as Map<String, dynamic>?,
        noteTemplateId: json['note_template_id'] as String?,
      );

  static ObsidianConfig empty() => const ObsidianConfig(
        vaultPath: '',
        vaultName: '',
        vaultValid: false,
        folderPattern: 'Voice-to-TextNote/{{date}}',
        filenamePattern: '{{date}}_{{title}}',
        autoExport: false,
        conflictPolicy: 'overwrite',
      );
}

class ObsidianValidation {
  final bool valid;
  final String vaultName;
  final bool obsidianFolderExists;
  final bool writable;
  final bool isSymlink;

  const ObsidianValidation({
    required this.valid,
    required this.vaultName,
    required this.obsidianFolderExists,
    required this.writable,
    required this.isSymlink,
  });

  factory ObsidianValidation.fromJson(Map<String, dynamic> json) =>
      ObsidianValidation(
        valid: json['valid'] as bool? ?? false,
        vaultName: json['vault_name'] as String? ?? '',
        obsidianFolderExists: json['obsidian_folder_exists'] as bool? ?? false,
        writable: json['writable'] as bool? ?? false,
        isSymlink: json['is_symlink'] as bool? ?? false,
      );
}

class ObsidianExportResult {
  final bool success;
  final String filePath;
  final String obsidianUri;
  final String? error;

  const ObsidianExportResult({
    required this.success,
    this.filePath = '',
    this.obsidianUri = '',
    this.error,
  });

  factory ObsidianExportResult.fromJson(Map<String, dynamic> json) =>
      ObsidianExportResult(
        success: json['success'] as bool? ?? false,
        filePath: json['file_path'] as String? ?? '',
        obsidianUri: json['obsidian_uri'] as String? ?? '',
        error: json['error'] as String?,
      );
}

class ObsidianApi {
  final Dio _dio;
  ObsidianApi(this._dio);

  Future<ObsidianConfig> getConfig() async {
    final response = await _dio.get('/obsidian/config');
    return ObsidianConfig.fromJson(response.data as Map<String, dynamic>);
  }

  Future<ObsidianConfig> saveConfig({
    required String vaultPath,
    String folderPattern = 'Voice-to-TextNote/{{date}}',
    String filenamePattern = '{{date}}_{{title}}',
    bool autoExport = false,
    String conflictPolicy = 'overwrite',
    Map<String, dynamic>? frontmatterCustom,
    String? noteTemplateId,
  }) async {
    final response = await _dio.post('/obsidian/config', data: {
      'vault_path': vaultPath,
      'folder_pattern': folderPattern,
      'filename_pattern': filenamePattern,
      'auto_export': autoExport,
      'conflict_policy': conflictPolicy,
      if (frontmatterCustom != null) 'frontmatter_custom': frontmatterCustom,
      if (noteTemplateId != null) 'note_template_id': noteTemplateId,
    });
    return ObsidianConfig.fromJson(response.data as Map<String, dynamic>);
  }

  Future<ObsidianValidation> validateVault(String vaultPath) async {
    final response = await _dio.post('/obsidian/validate', data: {
      'vault_path': vaultPath,
    });
    return ObsidianValidation.fromJson(response.data as Map<String, dynamic>);
  }

  Future<ObsidianExportResult> exportMeeting(String meetingId) async {
    final response = await _dio.post('/obsidian/export/$meetingId');
    return ObsidianExportResult.fromJson(response.data as Map<String, dynamic>);
  }
}
