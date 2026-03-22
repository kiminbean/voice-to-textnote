// PDF 내보내기 API 서비스 - SPEC-EXPORT-001
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'api_client.dart';

// ExportApi 프로바이더
final exportApiProvider = Provider<ExportApi>((ref) {
  final dio = ref.watch(dioProvider);
  return ExportApi(dio);
});

// @MX:ANCHOR: ExportApi.downloadPdf는 PDF 내보내기의 유일한 진입점
// @MX:REASON: result_screen에서 직접 호출되는 public API 경계
class ExportApi {
  final Dio _dio;
  ExportApi(this._dio);

  /// PDF 파일 다운로드 후 임시 디렉토리에 저장
  ///
  /// [minutesTaskId] - 회의록 태스크 ID (필수)
  /// [summaryTaskId] - 요약 태스크 ID (선택, 있으면 요약 내용도 포함)
  /// 반환값: 저장된 PDF File 객체
  Future<File> downloadPdf(
    String minutesTaskId, {
    String? summaryTaskId,
  }) async {
    // 쿼리 파라미터 조건부 추가
    final queryParams = <String, dynamic>{};
    if (summaryTaskId != null) {
      queryParams['summary_task_id'] = summaryTaskId;
    }

    // 임시 디렉토리에 파일 경로 생성
    final tempDir = await getTemporaryDirectory();
    final filePath = '${tempDir.path}/minutes_$minutesTaskId.pdf';

    // Dio download로 바이너리 파일 수신
    await _dio.download(
      '/export/pdf/$minutesTaskId',
      filePath,
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );

    return File(filePath);
  }
}
