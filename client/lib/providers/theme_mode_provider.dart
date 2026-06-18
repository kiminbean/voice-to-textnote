// 테마 모드 프로바이더 — 시스템/라이트/다크 전환 (shared_preferences 영속화)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 저장된 키
const _kThemeModeKey = 'app_theme_mode';

/// 사용 가능한 테마 모드 enum
enum AppThemeMode { system, light, dark }

extension AppThemeModeX on AppThemeMode {
  String get label => switch (this) {
        AppThemeMode.system => '시스템 설정 따름',
        AppThemeMode.light => '라이트',
        AppThemeMode.dark => '다크',
      };

  ThemeMode toMaterial() => switch (this) {
        AppThemeMode.system => ThemeMode.system,
        AppThemeMode.light => ThemeMode.light,
        AppThemeMode.dark => ThemeMode.dark,
      };
}

class ThemeModeState {
  final AppThemeMode mode;
  final bool initialized;
  const ThemeModeState({this.mode = AppThemeMode.system, this.initialized = false});

  ThemeModeState copyWith({AppThemeMode? mode, bool? initialized}) =>
      ThemeModeState(
        mode: mode ?? this.mode,
        initialized: initialized ?? this.initialized,
      );
}

class ThemeModeNotifier extends StateNotifier<ThemeModeState> {
  ThemeModeNotifier() : super(const ThemeModeState());

  /// 저장된 모드 로드 (앱 시작 시 1회)
  Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final idx = prefs.getInt(_kThemeModeKey) ?? 0;
      state = ThemeModeState(
        mode: AppThemeMode.values[idx.clamp(0, AppThemeMode.values.length - 1)],
        initialized: true,
      );
    } catch (_) {
      state = const ThemeModeState(initialized: true);
    }
  }

  Future<void> setMode(AppThemeMode mode) async {
    state = state.copyWith(mode: mode);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(_kThemeModeKey, mode.index);
    } catch (_) {
      // 영속화 실패는 무시 — 세션 내에서는 유지됨
    }
  }

  /// 시스템 밝기와 현재 모드를 조합해 실제 밝기를 반환 (다크 우선)
  Brightness resolve(Brightness systemBrightness) {
    if (state.mode == AppThemeMode.dark) return Brightness.dark;
    if (state.mode == AppThemeMode.light) return Brightness.light;
    return systemBrightness;
  }
}

final themeModeProvider =
    StateNotifierProvider<ThemeModeNotifier, ThemeModeState>(
  (ref) => ThemeModeNotifier(),
);
