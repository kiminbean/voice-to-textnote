import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/obsidian_api.dart';

final obsidianConfigProvider =
    FutureProvider.autoDispose<ObsidianConfig>((ref) async {
  final api = ref.watch(obsidianApiProvider);
  return api.getConfig();
});

class ObsidianExportNotifier extends StateNotifier<AsyncValue<ObsidianExportResult?>> {
  final ObsidianApi _api;
  ObsidianExportNotifier(this._api) : super(const AsyncValue.data(null));

  Future<void> exportMeeting(String meetingId) async {
    state = const AsyncValue.loading();
    try {
      final result = await _api.exportMeeting(meetingId);
      state = AsyncValue.data(result);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  void reset() {
    state = const AsyncValue.data(null);
  }
}

final obsidianExportProvider =
    StateNotifierProvider<ObsidianExportNotifier, AsyncValue<ObsidianExportResult?>>(
  (ref) {
    final api = ref.watch(obsidianApiProvider);
    return ObsidianExportNotifier(api);
  },
);
