// 협업 편집 중 표시 인디케이터
// SPEC-COLLAB-001: AC-041, AC-043 (REQ-COLLAB-041, 043)
import 'package:flutter/material.dart';

class CollabEditingIndicator extends StatelessWidget {
  final String? editingUserName;
  final String? editingUserColor;
  final bool isBeingEditedByOther;

  const CollabEditingIndicator({
    super.key,
    this.editingUserName,
    this.editingUserColor,
    this.isBeingEditedByOther = false,
  });

  @override
  Widget build(BuildContext context) {
    if (!isBeingEditedByOther || editingUserName == null) {
      return const SizedBox.shrink();
    }

    final color = _parseColor(editingUserColor);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.4), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              '$editingUserName 편집 중',
              style: TextStyle(
                fontSize: 11,
                color: color,
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Color _parseColor(String? hex) {
    if (hex == null || hex.isEmpty) return Colors.orange;
    try {
      final cleaned = hex.replaceFirst('#', '');
      if (cleaned.length == 6) {
        return Color(int.parse('FF$cleaned', radix: 16));
      }
    } catch (_) {}
    return Colors.orange;
  }
}
