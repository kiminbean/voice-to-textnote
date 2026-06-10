import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/vocabulary.dart';
import 'package:voice_to_textnote/services/vocabulary_api.dart';

class VocabularyListNotifier extends AsyncNotifier<List<Vocabulary>> {
  @override
  Future<List<Vocabulary>> build() async {
    return _fetchVocabularies();
  }

  Future<List<Vocabulary>> _fetchVocabularies() async {
    final api = ref.read(vocabularyApiProvider);
    return api.getVocabularies();
  }

  Future<void> createVocabulary(String name, List<String> words) async {
    final api = ref.read(vocabularyApiProvider);
    final newVocabulary = await api.createVocabulary(name, words);

    state = state.whenData((vocabularies) => [newVocabulary, ...vocabularies]);
  }

  Future<void> updateVocabulary(
      String id, String name, List<String> words) async {
    final api = ref.read(vocabularyApiProvider);
    final updatedVocabulary = await api.updateVocabulary(id, name, words);

    state = state.whenData((vocabularies) {
      return vocabularies
          .map((v) => v.id == id ? updatedVocabulary : v)
          .toList();
    });
  }

  Future<void> deleteVocabulary(String id) async {
    final api = ref.read(vocabularyApiProvider);
    await api.deleteVocabulary(id);

    state = state.whenData((vocabularies) {
      return vocabularies.where((v) => v.id != id).toList();
    });
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(_fetchVocabularies);
  }
}

final vocabularyListProvider =
    AsyncNotifierProvider<VocabularyListNotifier, List<Vocabulary>>(
  VocabularyListNotifier.new,
);
