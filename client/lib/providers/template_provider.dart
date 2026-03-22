// 양식(Template) 상태 관리 프로바이더 - SPEC-TMPL-001 REQ-TMPL-005
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/template.dart';
import 'package:voice_to_textnote/services/template_api.dart';

// 선택된 양식 ID 상태 (null = 기본 양식 사용)
final selectedTemplateIdProvider = StateProvider<String?>((ref) => null);

// 양식 목록 Notifier
class TemplateListNotifier extends AsyncNotifier<List<Template>> {
  @override
  Future<List<Template>> build() async {
    // 초기 로딩 시 목록 조회
    return _fetchTemplates();
  }

  Future<List<Template>> _fetchTemplates() async {
    final api = ref.read(templateApiProvider);
    return api.getTemplates();
  }

  // 양식 파일 업로드
  Future<void> uploadTemplate(File file) async {
    final api = ref.read(templateApiProvider);
    final newTemplate = await api.uploadTemplate(file);

    // 현재 목록에 새 양식 추가
    state = state.whenData((templates) => [newTemplate, ...templates]);
  }

  // 양식 삭제
  Future<void> deleteTemplate(String templateId) async {
    final api = ref.read(templateApiProvider);
    await api.deleteTemplate(templateId);

    // 현재 목록에서 삭제된 양식 제거
    state = state.whenData(
      (templates) =>
          templates.where((t) => t.templateId != templateId).toList(),
    );

    // 삭제된 양식이 선택되어 있으면 선택 해제
    if (ref.read(selectedTemplateIdProvider) == templateId) {
      ref.read(selectedTemplateIdProvider.notifier).state = null;
    }
  }

  // 목록 새로고침
  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(_fetchTemplates);
  }
}

// 양식 목록 프로바이더
final templateListProvider =
    AsyncNotifierProvider<TemplateListNotifier, List<Template>>(
  TemplateListNotifier.new,
);
