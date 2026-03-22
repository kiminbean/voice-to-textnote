// 양식(Template) API 서비스 - SPEC-TMPL-001 REQ-TMPL-005
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/template.dart';
import 'api_client.dart';

// TemplateApi 프로바이더
final templateApiProvider = Provider<TemplateApi>((ref) {
  final dio = ref.watch(dioProvider);
  return TemplateApi(dio);
});

class TemplateApi {
  final Dio _dio;

  TemplateApi(this._dio);

  // 양식 파일 업로드 (PDF 또는 DOCX)
  // multipart/form-data 방식으로 전송
  Future<Template> uploadTemplate(File file) async {
    final fileName = file.path.split('/').last;
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        file.path,
        filename: fileName,
      ),
    });

    final response = await _dio.post(
      '/templates',
      data: formData,
      options: Options(
        headers: {'Content-Type': 'multipart/form-data'},
      ),
    );

    return Template.fromJson(response.data as Map<String, dynamic>);
  }

  // 업로드된 양식 목록 조회
  Future<List<Template>> getTemplates() async {
    final response = await _dio.get('/templates');
    final List<dynamic> data = response.data as List<dynamic>;
    return data
        .map((item) => Template.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  // 특정 양식 상세 조회 (structure 포함)
  Future<Template> getTemplate(String templateId) async {
    final response = await _dio.get('/templates/$templateId');
    return Template.fromJson(response.data as Map<String, dynamic>);
  }

  // 양식 삭제
  Future<void> deleteTemplate(String templateId) async {
    await _dio.delete('/templates/$templateId');
  }
}
