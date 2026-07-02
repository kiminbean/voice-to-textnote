import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/services/audio_enhancement_api.dart';
import 'package:voice_to_textnote/services/auth_api.dart';
import 'package:voice_to_textnote/services/auth_service.dart';
import 'package:voice_to_textnote/widgets/audio_enhancement_panel.dart';

class _MockAuthApi extends Mock implements AuthApi {}

class _MockAuthService extends Mock implements AuthService {}

class _TestAuthNotifier extends AuthNotifier {
  final AuthState restoredState;
  int checkAuthCalls = 0;

  _TestAuthNotifier(
    AuthState initialState, {
    AuthState? restoredState,
  })  : restoredState = restoredState ?? initialState,
        super(_MockAuthApi(), _MockAuthService()) {
    state = initialState;
  }

  @override
  Future<void> checkAuth() async {
    checkAuthCalls += 1;
    state = restoredState;
  }
}

class _FakeAudioEnhancementApi extends AudioEnhancementApi {
  final Object? error;
  bool called = false;

  _FakeAudioEnhancementApi({this.error}) : super(Dio());

  @override
  Future<AudioEnhancementResponse> enhance(
    String filePath, {
    AudioEnhancementOptions options = const AudioEnhancementOptions(),
  }) async {
    called = true;
    final thrown = error;
    if (thrown != null) throw thrown;
    return const AudioEnhancementResponse(
      taskId: 'enhance-001',
      status: 'completed',
    );
  }
}

Widget _buildPanel({
  required AudioEnhancementApi api,
  required AuthNotifier authNotifier,
}) {
  return ProviderScope(
    overrides: [
      audioEnhancementApiProvider.overrideWithValue(api),
      authStateProvider.overrideWith((ref) => authNotifier),
    ],
    child: const MaterialApp(
      home: Scaffold(
        body: AudioEnhancementPanel(audioFilePath: '/tmp/meeting.wav'),
      ),
    ),
  );
}

void main() {
  testWidgets('오디오 향상 설정은 버튼을 누른 뒤 bottom sheet로 열린다', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: AudioEnhancementLauncher(audioFilePath: '/tmp/meeting.wav'),
          ),
        ),
      ),
    );

    expect(find.byType(AudioEnhancementPanel), findsNothing);
    expect(find.text('오디오 향상'), findsOneWidget);

    await tester.tap(find.text('오디오 향상'));
    await tester.pumpAndSettle();

    expect(find.byType(AudioEnhancementPanel), findsOneWidget);
    expect(find.text('음성만'), findsOneWidget);
  });

  testWidgets('인증 세션이 없으면 오디오 향상 API를 호출하지 않는다', (tester) async {
    final api = _FakeAudioEnhancementApi();
    final authNotifier = _TestAuthNotifier(
      const AuthState.initial(),
      restoredState: const AuthState.unauthenticated(),
    );

    await tester.pumpWidget(
      _buildPanel(api: api, authNotifier: authNotifier),
    );

    await tester.tap(find.byTooltip('실행'));
    await tester.pumpAndSettle();

    expect(authNotifier.checkAuthCalls, 1);
    expect(api.called, isFalse);
    expect(find.textContaining('로그인 또는 게스트 세션이 필요합니다'), findsOneWidget);
  });

  testWidgets('오디오 향상 401 응답은 인증 만료 메시지로 표시한다', (tester) async {
    final error = DioException(
      requestOptions: RequestOptions(path: '/enhance'),
      response: Response(
        requestOptions: RequestOptions(path: '/enhance'),
        statusCode: 401,
      ),
      type: DioExceptionType.badResponse,
    );
    final api = _FakeAudioEnhancementApi(error: error);
    final authNotifier = _TestAuthNotifier(const AuthState.guest());

    await tester.pumpWidget(
      _buildPanel(api: api, authNotifier: authNotifier),
    );

    await tester.tap(find.byTooltip('실행'));
    await tester.pumpAndSettle();

    expect(api.called, isTrue);
    expect(find.textContaining('오디오 향상 인증이 만료되었습니다'), findsOneWidget);
  });
}
