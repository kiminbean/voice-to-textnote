// 디자인 시스템 컬러 토큰 — 모던 미니멀 (Linear/Notion 계열)
// @MX:ANCHOR: 앱 전체 색상의 단일 진실 원천. 하드코딩 Colors.xxx 사용 금지.
import 'package:flutter/material.dart';

/// 라이트/다크 모드를 모두 지원하는 시맨틱 컬러 토큰.
/// 모든 화면/위젯은 [AppColors.of] 또는 [AppColors.resolve]를 통해 색상에 접근한다.
class AppColors {
  AppColors._();

  // --- 브랜드 액센트 (Indigo / Violet) ---
  // AI·생산성 앱 트렌드. 신뢰 + 지능 + 프라이버시.
  static const Color indigo50 = Color(0xFFEEF2FF);
  static const Color indigo100 = Color(0xFFE0E7FF);
  static const Color indigo200 = Color(0xFFC7D2FE);
  static const Color indigo400 = Color(0xFF818CF8);
  static const Color indigo500 = Color(0xFF6366F1);
  static const Color indigo600 = Color(0xFF4F46E5); // primary (light)
  static const Color indigo700 = Color(0xFF4338CA);

  static const Color violet400 = Color(0xFFA78BFA);
  static const Color violet500 = Color(0xFF8B5CF6);
  static const Color violet600 = Color(0xFF7C3AED);

  /// 브랜드 그라데이션 (로고/히어로 영역)
  static const LinearGradient brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [indigo600, violet500],
  );

  // --- 시맨틱 컬러 ---
  static const Color success = Color(0xFF10B981); // emerald-500
  static const Color successSoft = Color(0xFFD1FAE5); // emerald-100
  static const Color warning = Color(0xFFF59E0B); // amber-500
  static const Color warningSoft = Color(0xFFFEF3C7); // amber-100
  static const Color error = Color(0xFFEF4444); // red-500
  static const Color errorSoft = Color(0xFFFEE2E2); // red-100
  static const Color info = Color(0xFF3B82F6); // blue-500

  // --- 뉴트럴 스케일 (Light) ---
  static const Color lightBg = Color(0xFFFAFAFA); // zinc-50
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightSurfaceAlt = Color(0xFFF4F4F5); // zinc-100
  static const Color lightBorder = Color(0xFFE4E4E7); // zinc-200
  static const Color lightBorderStrong = Color(0xFFD4D4D8); // zinc-300
  static const Color lightTextPrimary = Color(0xFF18181B); // zinc-900
  static const Color lightTextSecondary = Color(0xFF52525B); // zinc-600
  static const Color lightTextTertiary = Color(0xFFA1A1AA); // zinc-400

  // --- 뉴트럴 스케일 (Dark) ---
  static const Color darkBg = Color(0xFF09090B); // zinc-950
  static const Color darkSurface = Color(0xFF18181B); // zinc-900
  static const Color darkSurfaceAlt = Color(0xFF27272A); // zinc-800
  static const Color darkBorder = Color(0xFF27272A); // zinc-800
  static const Color darkBorderStrong = Color(0xFF3F3F46); // zinc-700
  static const Color darkTextPrimary = Color(0xFFFAFAFA); // zinc-50
  static const Color darkTextSecondary = Color(0xFFA1A1AA); // zinc-400
  static const Color darkTextTertiary = Color(0xFF71717A); // zinc-500

  /// 컨텍스트(Brightness)에 따라 시맨틱 팔레트를 반환한다.
  static AppColorScheme of(BuildContext context) {
    return Theme.of(context).brightness == Brightness.dark
        ? _dark
        : _light;
  }

  // 테마 빌더에서 접근 가능한 공개 게터
  static AppColorScheme get light => _light;
  static AppColorScheme get dark => _dark;

  static const AppColorScheme _light = AppColorScheme(
    brightness: Brightness.light,
    primary: indigo600,
    primaryHover: indigo700,
    primarySoft: indigo50,
    onPrimary: Color(0xFFFFFFFF),
    background: lightBg,
    surface: lightSurface,
    surfaceAlt: lightSurfaceAlt,
    border: lightBorder,
    borderStrong: lightBorderStrong,
    textPrimary: lightTextPrimary,
    textSecondary: lightTextSecondary,
    textTertiary: lightTextTertiary,
  );

  static const AppColorScheme _dark = AppColorScheme(
    brightness: Brightness.dark,
    primary: indigo500,
    primaryHover: indigo400,
    primarySoft: Color(0xFF1E1B4B), // indigo-950
    onPrimary: Color(0xFFFFFFFF),
    background: darkBg,
    surface: darkSurface,
    surfaceAlt: darkSurfaceAlt,
    border: darkBorder,
    borderStrong: darkBorderStrong,
    textPrimary: darkTextPrimary,
    textSecondary: darkTextSecondary,
    textTertiary: darkTextTertiary,
  );
}

/// 시맨틱 색상 집합. [AppColors.of]로 획득.
@immutable
class AppColorScheme {
  final Brightness brightness;
  final Color primary;
  final Color primaryHover;
  final Color primarySoft; // 액센트 배경용 옅은 색
  final Color onPrimary;
  final Color background;
  final Color surface;
  final Color surfaceAlt;
  final Color border;
  final Color borderStrong;
  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;

  const AppColorScheme({
    required this.brightness,
    required this.primary,
    required this.primaryHover,
    required this.primarySoft,
    required this.onPrimary,
    required this.background,
    required this.surface,
    required this.surfaceAlt,
    required this.border,
    required this.borderStrong,
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
  });

  bool get isDark => brightness == Brightness.dark;
}
