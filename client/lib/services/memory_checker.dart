import 'dart:developer' as developer;
import 'dart:io';

/// 디바이스 메모리 가용성 확인 유틸리티
class MemoryChecker {
  /// 오프라인 STT에 필요한 최소 메모리 (MB)
  static const int minRequiredMb = 512;

  /// whisper-base 모델과 추론 버퍼를 고려한 보수적 기준 (MB)
  static const int _baseModelEstimateMb = 300;

  static const int _bytesPerMb = 1024 * 1024;

  /// 현재 프로세스/시스템 메모리 정보를 기반으로 가용 여부 판단
  ///
  /// 실제 iOS/Android 저수준 메모리 API는 Platform Channel이 필요하므로,
  /// Dart에서 가능한 시스템 명령과 [ProcessInfo.currentRss]를 먼저 사용합니다.
  static Future<bool> hasSufficientMemory() async {
    try {
      final requiredMb = estimatedRequiredMb;

      if (Platform.isMacOS) {
        final availableMb = await _availableMemoryMbFromVmStat();
        return availableMb == null || availableMb >= requiredMb;
      }

      if (Platform.isLinux) {
        final availableMb = await _availableMemoryMbFromProcMeminfo();
        return availableMb == null || availableMb >= requiredMb;
      }

      // TODO(SPEC-MOBILE-003): iOS/Android은 Platform Channel로 os_proc_available_memory,
      // ActivityManager.MemoryInfo 등 네이티브 값을 연결해 정확도를 높입니다.
      return _hasReasonableProcessHeadroom(requiredMb);
    } catch (e, stackTrace) {
      developer.log(
        '메모리 확인 실패, 기본값 true 사용',
        error: e,
        stackTrace: stackTrace,
      );
      return true;
    }
  }

  /// 모델 크기와 CPU 코어 수를 반영한 최소 필요 메모리 추정치 (MB)
  static int get estimatedRequiredMb {
    final processorBufferMb = Platform.numberOfProcessors * 16;
    final estimated = _baseModelEstimateMb + processorBufferMb;
    return estimated < minRequiredMb ? minRequiredMb : estimated;
  }

  /// 엔진 정보 문자열에 붙일 메모리/플랫폼 요약
  static String engineInfoSuffix() {
    return 'platform=${_platformName()}, required_mb=$estimatedRequiredMb, rss_mb=$currentRssMb';
  }

  /// 현재 프로세스 RSS (MB)
  static int get currentRssMb => (ProcessInfo.currentRss / _bytesPerMb).ceil();

  static bool _hasReasonableProcessHeadroom(int requiredMb) {
    final rssMb = currentRssMb;
    // 현재 프로세스가 필요 추정치의 4배 이상을 이미 사용 중이면 보수적으로 중단합니다.
    return rssMb < requiredMb * 4;
  }

  static Future<int?> _availableMemoryMbFromVmStat() async {
    final result = await Process.run('vm_stat', const []);
    if (result.exitCode != 0) return null;

    final output = result.stdout as String;
    final pageSize = _parseVmStatPageSize(output) ?? 4096;
    final freePages = _parseVmStatPages(output, 'Pages free') ?? 0;
    final inactivePages = _parseVmStatPages(output, 'Pages inactive') ?? 0;
    final speculativePages = _parseVmStatPages(output, 'Pages speculative') ?? 0;
    final availableBytes =
        (freePages + inactivePages + speculativePages) * pageSize;
    return (availableBytes / _bytesPerMb).floor();
  }

  static int? _parseVmStatPageSize(String output) {
    final match = RegExp(r'page size of (\d+) bytes').firstMatch(output);
    return match == null ? null : int.tryParse(match.group(1)!);
  }

  static int? _parseVmStatPages(String output, String label) {
    final escapedLabel = RegExp.escape(label);
    final match = RegExp('$escapedLabel:\\s+(\\d+)\\.').firstMatch(output);
    return match == null ? null : int.tryParse(match.group(1)!);
  }

  static Future<int?> _availableMemoryMbFromProcMeminfo() async {
    final file = File('/proc/meminfo');
    if (!await file.exists()) return null;

    final lines = await file.readAsLines();
    for (final line in lines) {
      if (line.startsWith('MemAvailable:')) {
        final match = RegExp(r'MemAvailable:\s+(\d+)\s+kB').firstMatch(line);
        final kb = match == null ? null : int.tryParse(match.group(1)!);
        return kb == null ? null : (kb / 1024).floor();
      }
    }
    return null;
  }

  static String _platformName() {
    if (Platform.isIOS) return 'ios';
    if (Platform.isAndroid) return 'android';
    if (Platform.isMacOS) return 'macos';
    if (Platform.isWindows) return 'windows';
    if (Platform.isLinux) return 'linux';
    return 'unknown';
  }
}
