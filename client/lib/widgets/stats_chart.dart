// 일별 처리 추이 차트 위젯
// @MX:NOTE: SPEC-APP-005 REQ-020 — fl_chart 기반 30일 라인 차트

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:voice_to_textnote/models/processing_stats.dart';

/// 일별 처리 추이 라인 차트 (REQ-020)
class StatsChart extends StatelessWidget {
  final List<DailyStats> dailyStats;

  const StatsChart({super.key, required this.dailyStats});

  @override
  Widget build(BuildContext context) {
    if (dailyStats.isEmpty) {
      return const SizedBox(
        height: 200,
        child: Center(child: Text('표시할 통계 데이터가 없습니다')),
      );
    }

    return SizedBox(
      height: 200,
      child: LineChart(
        LineChartData(
          gridData: const FlGridData(show: true, drawVerticalLine: false),
          titlesData: FlTitlesData(
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 40,
                getTitlesWidget: (value, meta) =>
                    Text('${value.toInt()}', style: const TextStyle(fontSize: 10)),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                interval: _bottomInterval,
                getTitlesWidget: (value, meta) {
                  final idx = value.toInt();
                  if (idx < 0 || idx >= dailyStats.length) {
                    return const SizedBox.shrink();
                  }
                  final d = dailyStats[idx].date;
                  return Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      '${d.month}/${d.day}',
                      style: const TextStyle(fontSize: 10),
                    ),
                  );
                },
              ),
            ),
            topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          ),
          borderData: FlBorderData(show: false),
          lineBarsData: [
            // 처리 건수
            LineChartBarData(
              spots: _buildCountSpots(),
              isCurved: true,
              color: Theme.of(context).colorScheme.primary,
              barWidth: 2,
              dotData: const FlDotData(show: false),
              belowBarData: BarAreaData(show: false),
            ),
            // 성공 건수
            LineChartBarData(
              spots: _buildSuccessSpots(),
              isCurved: true,
              color: Colors.green,
              barWidth: 2,
              dotData: const FlDotData(show: false),
              belowBarData: BarAreaData(show: false),
            ),
          ],
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipItems: (spots) => spots.map((s) {
                final label = s.bar.color == Colors.green ? '성공' : '전체';
                return LineTooltipItem('$label: ${s.y.toInt()}', TextStyle(color: s.bar.color));
              }).toList(),
            ),
          ),
        ),
      ),
    );
  }

  List<FlSpot> _buildCountSpots() => [
        for (var i = 0; i < dailyStats.length; i++)
          FlSpot(i.toDouble(), dailyStats[i].count.toDouble()),
      ];

  List<FlSpot> _buildSuccessSpots() => [
        for (var i = 0; i < dailyStats.length; i++)
          FlSpot(i.toDouble(), dailyStats[i].successCount.toDouble()),
      ];

  /// 데이터 개수에 따른 x축 라벨 간격
  double get _bottomInterval {
    if (dailyStats.length <= 7) return 1;
    if (dailyStats.length <= 15) return 2;
    return 5;
  }
}
