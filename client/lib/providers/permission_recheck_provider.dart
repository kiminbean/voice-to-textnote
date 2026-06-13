// 앱 resume 시 권한 재확인 트리거 (T-015)
// 설정 앱에서 권한 변경 후 복귀 시 화면에서 감지하기 위함
import 'package:flutter_riverpod/flutter_riverpod.dart';

class PermissionRecheckNotifier extends Notifier<int> {
  @override
  int build() => 0;

  /// 앱이 background에서 복귀할 때 호출 → 상태 증가
  void triggerRecheck() => state++;
}

final permissionRecheckProvider =
    NotifierProvider<PermissionRecheckNotifier, int>(
  PermissionRecheckNotifier.new,
);
