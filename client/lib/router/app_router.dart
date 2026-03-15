// 앱 라우터 설정 (go_router 사용)
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/screens/home_screen.dart';
import 'package:voice_to_textnote/screens/processing_screen.dart';
import 'package:voice_to_textnote/screens/recording_screen.dart';
import 'package:voice_to_textnote/screens/result_screen.dart';

// 앱 전체 라우터 정의
final goRouter = GoRouter(
  initialLocation: '/',
  routes: [
    // 홈 화면 - 미팅 목록
    GoRoute(
      path: '/',
      builder: (_, __) => const HomeScreen(),
    ),
    // 녹음 화면
    GoRoute(
      path: '/recording',
      builder: (_, __) => const RecordingScreen(),
    ),
    // 처리 중 화면 (미팅 ID 파라미터)
    GoRoute(
      path: '/processing/:id',
      builder: (_, state) => ProcessingScreen(
        meetingId: state.pathParameters['id']!,
      ),
    ),
    // 결과 화면 (미팅 ID 파라미터)
    GoRoute(
      path: '/result/:id',
      builder: (_, state) => ResultScreen(
        meetingId: state.pathParameters['id']!,
      ),
    ),
  ],
);
