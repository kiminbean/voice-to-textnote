// 디자인 시스템 스페이싱/반경/그림자 토큰
// @MX:ANCHOR: 레이아웃 리듬의 단일 진실 원천. 매직 넘버 금지.
import 'package:flutter/material.dart';

/// 4px 기반 스페이싱 스케일. 일관된 리듬을 위해 항상 이 값들을 사용한다.
class AppSpacing {
  AppSpacing._();

  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 48;

  /// 화면 가장자리 기본 패딩
  static const double pagePadding = lg; // 16
}

/// 모서리 반경 스케일.
class AppRadius {
  AppRadius._();

  static const double sm = 8; // 입력필드, 작은 버튼
  static const double md = 12; // 카드, 시트
  static const double lg = 16; // 큰 카드, 컨테이너
  static const double xl = 20; // 모달
  static const double pill = 999; // 알약형 배지/버튼

  static const BorderRadius brSm = BorderRadius.all(Radius.circular(sm));
  static const BorderRadius brMd = BorderRadius.all(Radius.circular(md));
  static const BorderRadius brLg = BorderRadius.all(Radius.circular(lg));
  static const BorderRadius brXl = BorderRadius.all(Radius.circular(xl));
  static const BorderRadius brPill = BorderRadius.all(Radius.circular(pill));
}

/// 모던 미니멀용 매우 부드러운 그림자.
class AppElevation {
  AppElevation._();

  /// 거의 보이지 않는 구분용 (카드)
  static List<BoxShadow> subtle(Color color) => [
        BoxShadow(
          color: color.withAlpha(8),
          blurRadius: 16,
          offset: const Offset(0, 1),
        ),
        BoxShadow(
          color: color.withAlpha(6),
          blurRadius: 4,
          offset: const Offset(0, 1),
        ),
      ];

  /// 떠 있는 요소 (바텀시트, 팝오버)
  static List<BoxShadow> floating(Color color) => [
        BoxShadow(
          color: color.withAlpha(16),
          blurRadius: 32,
          offset: const Offset(0, 8),
        ),
      ];
}
