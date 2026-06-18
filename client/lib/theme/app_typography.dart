// 디자인 시스템 타이포그래피 스케일
// @MX:ANCHOR: 텍스트 스타일의 단일 진실 원째.
import 'package:flutter/material.dart';
import 'app_colors.dart';

/// 일관된 타이포 계층. Linear/Notion 스타일 — 적당한 자간, 명확한 가중치 대비.
class AppTypography {
  AppTypography._();

  static TextTheme get textTheme => const TextTheme(
        // 디스플레이 — 타이머, 히어로 숫자
        displayLarge: TextStyle(
          fontSize: 48,
          height: 1.1,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
        ),
        displayMedium: TextStyle(
          fontSize: 36,
          height: 1.15,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.4,
        ),
        // 헤드라인 — 화면 제목
        headlineLarge: TextStyle(
          fontSize: 30,
          height: 1.25,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.3,
        ),
        headlineMedium: TextStyle(
          fontSize: 26,
          height: 1.3,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.2,
        ),
        // 타이틀 — 섹션 헤더, 카드 제목
        titleLarge: TextStyle(
          fontSize: 20,
          height: 1.3,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.2,
        ),
        titleMedium: TextStyle(
          fontSize: 16,
          height: 1.4,
          fontWeight: FontWeight.w600,
        ),
        titleSmall: TextStyle(
          fontSize: 14,
          height: 1.4,
          fontWeight: FontWeight.w600,
        ),
        // 본문
        bodyLarge: TextStyle(
          fontSize: 15,
          height: 1.5,
          fontWeight: FontWeight.w400,
        ),
        bodyMedium: TextStyle(
          fontSize: 14,
          height: 1.5,
          fontWeight: FontWeight.w400,
        ),
        bodySmall: TextStyle(
          fontSize: 13,
          height: 1.45,
          fontWeight: FontWeight.w400,
        ),
        // 라벨 — 버튼, 배지, 캡션
        labelLarge: TextStyle(
          fontSize: 15,
          height: 1.2,
          fontWeight: FontWeight.w600,
        ),
        labelMedium: TextStyle(
          fontSize: 13,
          height: 1.2,
          fontWeight: FontWeight.w600,
        ),
        labelSmall: TextStyle(
          fontSize: 11,
          height: 1.3,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.2,
        ),
      );

  /// 모노스페이스 타이머 표시용 (녹음 화면)
  static TextStyle timer(BuildContext context) => TextStyle(
        fontFamily: 'SF Mono',
        fontFamilyFallback: const ['Roboto Mono', 'monospace'],
        fontSize: 64,
        height: 1.0,
        fontWeight: FontWeight.w300,
        letterSpacing: 2,
        color: AppColors.of(context).textPrimary,
        fontFeatures: const [FontFeature.tabularFigures()],
      );
}
