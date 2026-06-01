import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'api_client.dart';

final exportApiProvider = Provider<ExportApi>((ref) {
  final dio = ref.watch(dioProvider);
  return ExportApi(dio);
});

enum ExportFormat { pdf, docx, markdown }

// @MX:ANCHOR: ExportApi는 result_screen export 기능의 유일한 진입점
// @MX:REASON: 모든 내보내기 포맷(PDF/DOCX/MD)의 공통 로직 집중 관리
class ExportApi {
  final Dio _dio;
  ExportApi(this._dio);

  Future<File> downloadPdf(
    String minutesTaskId, {
    String? summaryTaskId,
  }) =>
      _download(minutesTaskId, ExportFormat.pdf, summaryTaskId: summaryTaskId);

  Future<File> downloadDocx(
    String minutesTaskId, {
    String? summaryTaskId,
  }) =>
      _download(minutesTaskId, ExportFormat.docx, summaryTaskId: summaryTaskId);

  Future<File> downloadMarkdown(
    String minutesTaskId, {
    String? summaryTaskId,
  }) =>
      _download(minutesTaskId, ExportFormat.markdown,
          summaryTaskId: summaryTaskId);

  Future<File> _download(
    String minutesTaskId,
    ExportFormat format, {
    String? summaryTaskId,
  }) async {
    final queryParams = <String, dynamic>{};
    if (summaryTaskId != null) {
      queryParams['summary_task_id'] = summaryTaskId;
    }

    final ext = switch (format) {
      ExportFormat.pdf => 'pdf',
      ExportFormat.docx => 'docx',
      ExportFormat.markdown => 'md',
    };
    final pathSegment = switch (format) {
      ExportFormat.pdf => 'pdf',
      ExportFormat.docx => 'docx',
      ExportFormat.markdown => 'markdown',
    };

    final tempDir = await getTemporaryDirectory();
    final filePath = '${tempDir.path}/minutes_$minutesTaskId.$ext';

    await _dio.download(
      '/export/$pathSegment/$minutesTaskId',
      filePath,
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );

    return File(filePath);
  }
}
