// 텍스트 shimmer 위젯 - 결과 화면 로딩 상태용
import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

class ShimmerText extends StatelessWidget {
  // 표시할 shimmer 텍스트 라인 수
  final int lines;

  const ShimmerText({
    super.key,
    this.lines = 3,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Shimmer.fromColors(
      baseColor: colorScheme.surfaceContainerHighest,
      highlightColor: colorScheme.surface,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: List.generate(lines, (index) {
          // 마지막 줄은 짧게 표시 (자연스러운 텍스트 효과)
          final isLastLine = index == lines - 1;
          return Padding(
            padding: EdgeInsets.only(bottom: index < lines - 1 ? 8 : 0),
            child: Container(
              height: 14,
              width: isLastLine
                  ? MediaQuery.of(context).size.width * 0.6
                  : double.infinity,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
          );
        }),
      ),
    );
  }
}
