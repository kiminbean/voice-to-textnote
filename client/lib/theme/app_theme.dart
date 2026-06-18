// 앱 테마 통합 — Light/Dark ThemeData 생성
// @MX:ANCHOR: MaterialApp.theme/darkTheme 진입점.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'app_colors.dart';
import 'app_spacing.dart';
import 'app_typography.dart';

/// 라이트 테마 생성
ThemeData buildAppLightTheme() {
  final scheme = AppColors.light;
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    scaffoldBackgroundColor: scheme.background,
    colorScheme: ColorScheme(
      brightness: Brightness.light,
      primary: scheme.primary,
      onPrimary: scheme.onPrimary,
      primaryContainer: scheme.primarySoft,
      onPrimaryContainer: scheme.primary,
      secondary: AppColors.violet500,
      onSecondary: Colors.white,
      tertiary: AppColors.violet400,
      error: AppColors.error,
      onError: Colors.white,
      surface: scheme.surface,
      onSurface: scheme.textPrimary,
      surfaceContainerHighest: scheme.surfaceAlt,
      outline: scheme.border,
      outlineVariant: scheme.border,
    ),
    textTheme: AppTypography.textTheme,
    splashFactory: InkSparkle.splashFactory,
  );

  return _applyComponentThemes(base, scheme);
}

/// 다크 테마 생성
ThemeData buildAppDarkTheme() {
  final scheme = AppColors.dark;
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: scheme.background,
    colorScheme: ColorScheme(
      brightness: Brightness.dark,
      primary: scheme.primary,
      onPrimary: scheme.onPrimary,
      primaryContainer: scheme.primarySoft,
      onPrimaryContainer: scheme.primary,
      secondary: AppColors.violet400,
      onSecondary: Colors.white,
      tertiary: AppColors.violet400,
      error: AppColors.error,
      onError: Colors.white,
      surface: scheme.surface,
      onSurface: scheme.textPrimary,
      surfaceContainerHighest: scheme.surfaceAlt,
      outline: scheme.border,
      outlineVariant: scheme.border,
    ),
    textTheme: AppTypography.textTheme,
    splashFactory: InkSparkle.splashFactory,
  );

  return _applyComponentThemes(base, scheme);
}

ThemeData _applyComponentThemes(ThemeData base, AppColorScheme scheme) {
  return base.copyWith(
    // AppBar: 투명/플랫, 미묘한 보더
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.background,
      foregroundColor: scheme.textPrimary,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: AppTypography.textTheme.titleLarge?.copyWith(
        color: scheme.textPrimary,
        fontWeight: FontWeight.w700,
      ),
      systemOverlayStyle: scheme.isDark
          ? SystemUiOverlayStyle.light
          : SystemUiOverlayStyle.dark,
    ),
    // 카드: 보더 + 미세 그림자, 둥근 모서리
    cardTheme: CardThemeData(
      color: scheme.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: AppRadius.brLg,
        side: BorderSide(color: scheme.border),
      ),
    ),
    // 입력필드: 보더 중심, 포커스 시 액센트
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: scheme.surface,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.md,
      ),
      hintStyle: AppTypography.textTheme.bodyMedium?.copyWith(
        color: scheme.textTertiary,
      ),
      labelStyle: AppTypography.textTheme.bodyMedium?.copyWith(
        color: scheme.textSecondary,
      ),
      border: OutlineInputBorder(
        borderRadius: AppRadius.brSm,
        borderSide: BorderSide(color: scheme.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: AppRadius.brSm,
        borderSide: BorderSide(color: scheme.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: AppRadius.brSm,
        borderSide: BorderSide(color: scheme.primary, width: 1.5),
      ),
      errorBorder: const OutlineInputBorder(
        borderRadius: AppRadius.brSm,
        borderSide: BorderSide(color: AppColors.error),
      ),
    ),
    // FilledButton: 액센트, 둥근 모서리
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: scheme.primary,
        foregroundColor: scheme.onPrimary,
        minimumSize: const Size.fromHeight(50),
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.brSm),
        textStyle: AppTypography.textTheme.labelLarge,
        elevation: 0,
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.textPrimary,
        elevation: 0,
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.brSm),
        side: BorderSide(color: scheme.border),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: scheme.textPrimary,
        minimumSize: const Size.fromHeight(50),
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.brSm),
        side: BorderSide(color: scheme.border),
        textStyle: AppTypography.textTheme.labelLarge,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: scheme.primary,
        textStyle: AppTypography.textTheme.labelMedium,
      ),
    ),
    // 바텀시트: 둥근 상단
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: scheme.surface,
      surfaceTintColor: Colors.transparent,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.xl)),
      ),
      showDragHandle: true,
      dragHandleColor: scheme.borderStrong,
    ),
    // 다이얼로그
    dialogTheme: DialogThemeData(
      backgroundColor: scheme.surface,
      elevation: 0,
      shape: const RoundedRectangleBorder(borderRadius: AppRadius.brLg),
    ),
    // 스낵바
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: scheme.textPrimary,
      contentTextStyle: TextStyle(color: scheme.background, fontSize: 14),
      shape: const RoundedRectangleBorder(borderRadius: AppRadius.brSm),
    ),
    // 칩/배지
    chipTheme: ChipThemeData(
      backgroundColor: scheme.surfaceAlt,
      labelStyle: AppTypography.textTheme.labelMedium?.copyWith(
        color: scheme.textSecondary,
      ),
      shape: const RoundedRectangleBorder(borderRadius: AppRadius.brPill),
      side: BorderSide.none,
    ),
    // 분할선
    dividerTheme: DividerThemeData(
      color: scheme.border,
      thickness: 1,
      space: 1,
    ),
    // 리스트타일
    listTileTheme: const ListTileThemeData(
      shape: RoundedRectangleBorder(borderRadius: AppRadius.brMd),
      contentPadding: EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.xs,
      ),
    ),
    // 탭바
    tabBarTheme: TabBarThemeData(
      labelColor: scheme.textPrimary,
      unselectedLabelColor: scheme.textTertiary,
      indicatorColor: scheme.primary,
      labelStyle: AppTypography.textTheme.labelMedium,
      unselectedLabelStyle: AppTypography.textTheme.labelMedium,
      indicatorSize: TabBarIndicatorSize.label,
      dividerColor: scheme.border,
    ),
    // 플로팅액션버튼
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: scheme.primary,
      foregroundColor: scheme.onPrimary,
      elevation: 2,
      shape: const RoundedRectangleBorder(borderRadius: AppRadius.brLg),
    ),
    // 프로그레스바
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: scheme.primary,
      linearTrackColor: scheme.surfaceAlt,
      circularTrackColor: scheme.surfaceAlt,
    ),
    // 아이콘
    iconTheme: IconThemeData(
      color: scheme.textSecondary,
      size: 22,
    ),
  );
}
