// 오프라인 상태 상단 배너 위젯
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/providers/connectivity_provider.dart';

class OfflineBanner extends ConsumerWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(connectivityProvider);

    // 온라인 상태면 빈 위젯 반환
    if (isOnline) return const SizedBox.shrink();

    return Material(
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        color: Theme.of(context).colorScheme.errorContainer,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.wifi_off,
              size: 16,
              color: Theme.of(context).colorScheme.onErrorContainer,
            ),
            const SizedBox(width: 8),
            Text(
              '서버에 연결할 수 없습니다',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onErrorContainer,
                    fontWeight: FontWeight.w500,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}
