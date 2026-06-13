import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/vocabulary.dart';
import 'api_client.dart';

final vocabularyApiProvider = Provider<VocabularyApi>((ref) {
  final dio = ref.watch(dioProvider);
  return VocabularyApi(dio);
});

class VocabularyApi {
  final Dio _dio;

  VocabularyApi(this._dio);

  Future<List<Vocabulary>> getVocabularies() async {
    final response = await _dio.get('/vocabulary');
    final data = response.data['vocabularies'] as List<dynamic>;
    return data
        .map((item) => Vocabulary.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<Vocabulary> createVocabulary(String name, List<String> words) async {
    final response = await _dio.post(
      '/vocabulary',
      data: {
        'name': name,
        'words': words,
      },
    );
    return Vocabulary.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Vocabulary> updateVocabulary(
      String id, String name, List<String> words) async {
    final response = await _dio.put(
      '/vocabulary/$id',
      data: {
        'name': name,
        'words': words,
      },
    );
    return Vocabulary.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteVocabulary(String id) async {
    await _dio.delete('/vocabulary/$id');
  }
}
