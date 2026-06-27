// SSE(Server-Sent Events) 스트림 클라이언트 서비스
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:voice_to_textnote/config/app_config.dart';

typedef SseHeadersProvider = FutureOr<Map<String, String>> Function();

// @MX:ANCHOR: SSE 스트리밍 연결 관리 - 리소스 정리 필수
// @MX:REASON: 화면 종료 시 disconnect() 호출 없으면 메모리 누수 발생
class SseService {
  final String baseUrl;

  // 클라이언트 팩토리 (테스트에서 목 주입 허용)
  final http.Client Function() clientFactory;
  final SseHeadersProvider? headersProvider;

  final Set<http.Client> _clients = {};

  SseService({
    required this.baseUrl,
    http.Client Function()? clientFactory,
    this.headersProvider,
  }) : clientFactory = clientFactory ?? (() => http.Client());

  // SSE 스트림 연결 - task_id에 해당하는 실시간 이벤트 수신
  Stream<Map<String, dynamic>> connect(String taskId) async* {
    final client = clientFactory();
    _clients.add(client);
    final request = http.Request(
      'GET',
      Uri.parse('$baseUrl/tasks/$taskId/stream'),
    );
    request.headers['Accept'] = 'text/event-stream';
    request.headers['Cache-Control'] = 'no-cache';
    final authHeaders = await headersProvider?.call();
    if (authHeaders != null) {
      request.headers.addAll(authHeaders);
    } else if (AppConfig.apiKey.isNotEmpty) {
      request.headers['X-API-Key'] = AppConfig.apiKey;
    }

    try {
      final response = await client.send(request);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw http.ClientException(
          'SSE 연결 실패 (${response.statusCode})',
          request.url,
        );
      }

      String buffer = '';
      await for (final chunk in response.stream.transform(utf8.decoder)) {
        buffer += chunk;
        final lines = buffer.split('\n');
        // 마지막 줄은 불완전할 수 있으므로 버퍼에 유지
        buffer = lines.removeLast();

        for (final line in lines) {
          if (line.startsWith('data: ')) {
            final jsonStr = line.substring(6).trim();
            if (jsonStr.isNotEmpty) {
              try {
                final parsed = json.decode(jsonStr);
                if (parsed is Map<String, dynamic>) {
                  yield parsed;
                }
              } catch (_) {
                // 잘못된 JSON은 무시 - 스트림 계속 처리
              }
            }
          }
        }
      }
    } catch (e) {
      // SSE 연결 실패 - 호출자가 폴링으로 폴백 처리
      rethrow;
    } finally {
      // 스트림 종료 시 항상 클라이언트 정리
      _clients.remove(client);
      client.close();
    }
  }

  // SSE 연결 해제 및 리소스 정리
  void disconnect() {
    for (final client in List<http.Client>.from(_clients)) {
      client.close();
    }
    _clients.clear();
  }
}
