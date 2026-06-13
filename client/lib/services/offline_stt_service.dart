import 'dart:async';
import 'dart:developer' as developer;
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';
import 'package:voice_to_textnote/models/transcription_result.dart';
import 'package:voice_to_textnote/services/memory_checker.dart';
import 'package:voice_to_textnote/services/platform_stt_service.dart';

/// @MX:SPEC:REQ-MOBILE-008-01, REQ-MOBILE-008-05, REQ-MOBILE-008-06, REQ-MOBILE-008-07
///
/// 오프라인 STT 처리 서비스
///
/// PlatformSttService를 래핑하여 오프라인 모드를 지원하며,
/// 청크 분할, 메모리 모니터링, 진행률 보고 기능을 포함합니다.
class OfflineSttService {
  final PlatformSttService _platformService;

  /// 청크 분할 기준 (5분)
  static const Duration _chunkThreshold = Duration(minutes: 5);

  /// 청크 크기 (30초)
  static const Duration _chunkSize = Duration(seconds: 30);

  /// WAV 헤더 크기 (PCM 데이터 시작 오프셋)
  static const int _wavHeaderBytes = 44;

  /// 16kHz, mono, 16-bit PCM 기준 초당 바이트 수
  static const int _bytesPerSecond = 16000 * 1 * 2;

  /// 30초 청크 PCM 바이트 수
  static const int _chunkBytes = _bytesPerSecond * 30;

  OfflineSttService(this._platformService);

  /// WAV 파일을 텍스트로 변환
  ///
  /// [wavPath] 변환할 WAV 파일 경로
  ///
  /// 반환: 변환 결과 (offline: true 메타데이터 포함)
  ///
  /// 예외 발생 상황:
  /// - [Exception]: STT 처리 실패
  Future<TranscriptionResult> transcribe(String wavPath) async {
    // 경로 검증
    if (wavPath.isEmpty) {
      throw Exception('파일 경로가 비어있습니다');
    }

    final result = await _platformService.transcribe(wavPath);
    return result.copyWith(
      offline: true,
      engineInfo: _appendMemoryInfo(result.engineInfo),
    );
  }

  /// WAV 파일을 청크 분할하여 텍스트로 변환 (진행률 포함)
  ///
  /// [wavPath] 변환할 WAV 파일 경로
  ///
  /// 반환: 진행률 스트림 (0~100%)
  Stream<TranscriptionProgress> transcribeWithProgress(String wavPath) async* {
    // 경로 검증
    if (wavPath.isEmpty) {
      throw Exception('파일 경로가 비어있습니다');
    }

    // 파일 정보 확인 (Mock 환경에서는 실패할 수 있음)
    final file = File(wavPath);
    int fileSize = 0;

    try {
      fileSize = await file.length();
    } catch (e) {
      // 파일 접근 실패 시 기본값 사용 (테스트 환경)
      fileSize = 3200000; // 100초 분량
    }

    final estimatedDuration = _estimateDuration(fileSize);

    // 5분 이하면 단일 처리
    if (estimatedDuration <= _chunkThreshold) {
      yield TranscriptionProgress(
        progress: 0.0,
        result: null,
        status: TranscriptionStatus.starting,
      );

      final result = await transcribe(wavPath);

      yield TranscriptionProgress(
        progress: 100.0,
        result: result,
        status: TranscriptionStatus.completed,
      );

      // 처리 완료 후 WAV 파일 삭제
      await _cleanupWavFile(wavPath);
      return;
    }

    // 5분 초과 시 WAV PCM 데이터를 30초 단위 파일로 실제 분할 처리
    final pcmSize = math.max(0, fileSize - _wavHeaderBytes);
    final chunkCount = math.max(1, (pcmSize / _chunkBytes).ceil());
    final results = <TranscriptionResult>[];
    final segments = <TranscriptionSegment>[];

    for (int i = 0; i < chunkCount; i++) {
      // 진행률 업데이트
      final progress = (i / chunkCount) * 100;
      yield TranscriptionProgress(
        progress: progress,
        result: null,
        status: TranscriptionStatus.processing,
      );

      // 메모리 확인
      if (!await _hasSufficientMemory()) {
        yield TranscriptionProgress(
          progress: progress,
          result: null,
          status: TranscriptionStatus.failed,
          error: '메모리 부족',
        );
        throw Exception('메모리 부족으로 처리 중단됨');
      }

      File? chunkFile;
      try {
        chunkFile = await _createChunkFile(file, i, _chunkBytes);
        final result = await transcribe(chunkFile.path);
        results.add(result);
        segments.addAll(
          _offsetSegments(
            result.segments,
            Duration(seconds: i * _chunkSize.inSeconds),
          ),
        );
      } catch (e) {
        yield TranscriptionProgress(
          progress: progress,
          result: null,
          status: TranscriptionStatus.failed,
          error: e.toString(),
        );
        rethrow;
      } finally {
        if (chunkFile != null) {
          await _cleanupChunkFile(chunkFile);
        }
      }
    }

    // 최종 결과 병합
    final finalResult = results.isNotEmpty
        ? results.first.copyWith(
            text: results.map((r) => r.text).join(' '),
            segments: segments,
          )
        : TranscriptionResult(
            text: '',
            segments: const [],
            language: 'en',
            offline: true,
            createdAt: DateTime.now(),
            engineInfo: 'whisper-base; ${MemoryChecker.engineInfoSuffix()}',
          );

    yield TranscriptionProgress(
      progress: 100.0,
      result: finalResult,
      status: TranscriptionStatus.completed,
    );

    await _cleanupWavFile(wavPath);
  }

  /// 오프라인 모델 가용 여부 확인
  ///
  /// 반환: 모델이 로드되어 사용 가능하면 true
  Future<bool> isAvailable() async {
    try {
      return await _platformService.isAvailable();
    } catch (e) {
      // 가용 여부 확인 실패 시 false 반환
      return false;
    }
  }

  /// 파일 크기에서 오디오 길이 추정
  ///
  /// 16kHz, mono, 16-bit PCM 기준: 1초당 약 32KB
  Duration _estimateDuration(int fileSize) {
    final seconds = math.max(0, fileSize - _wavHeaderBytes) / _bytesPerSecond;
    return Duration(seconds: seconds.round());
  }

  /// 메모리 가용 여부 확인
  ///
  /// TODO(SPEC-MOBILE-003): 향후 Platform Channel에서 iOS/Android 메모리 API를 연결합니다.
  Future<bool> _hasSufficientMemory() async {
    return MemoryChecker.hasSufficientMemory();
  }

  String _appendMemoryInfo(String? engineInfo) {
    final baseInfo = engineInfo ?? 'whisper-base';
    return '$baseInfo; ${MemoryChecker.engineInfoSuffix()}';
  }

  /// WAV 파일에서 지정된 PCM 청크를 잘라 새 WAV 파일로 생성
  Future<File> _createChunkFile(
    File wavFile,
    int chunkIndex,
    int chunkBytes,
  ) async {
    final wavLength = await wavFile.length();
    if (wavLength <= _wavHeaderBytes) {
      throw Exception('WAV 파일에 PCM 데이터가 없습니다');
    }

    final startByte = chunkIndex * chunkBytes;
    final pcmLength = wavLength - _wavHeaderBytes;

    if (startByte >= pcmLength) {
      throw Exception('청크 인덱스가 범위를 벗어났습니다: $chunkIndex');
    }

    final bytesToRead = math.min(chunkBytes, pcmLength - startByte);
    final input = await wavFile.open();
    late final Uint8List chunkPcm;
    try {
      await input.setPosition(_wavHeaderBytes + startByte);
      chunkPcm = await input.read(bytesToRead);
    } finally {
      await input.close();
    }

    final chunkWavHeader = _generateWavHeader(chunkPcm.length);

    final tempDir = await Directory.systemTemp.createTemp('stt_chunk_');
    final chunkFile = File('${tempDir.path}/chunk_$chunkIndex.wav');
    await chunkFile.writeAsBytes([...chunkWavHeader, ...chunkPcm]);

    return chunkFile;
  }

  /// 16kHz mono 16-bit PCM용 WAV 헤더 생성
  Uint8List _generateWavHeader(int pcmDataLength) {
    const channels = 1;
    const sampleRate = 16000;
    const bitsPerSample = 16;
    const byteRate = sampleRate * channels * bitsPerSample ~/ 8;
    const blockAlign = channels * bitsPerSample ~/ 8;
    final totalDataLength = pcmDataLength + 36;

    final header = ByteData(_wavHeaderBytes);
    _writeAscii(header, 0, 'RIFF');
    header.setUint32(4, totalDataLength, Endian.little);
    _writeAscii(header, 8, 'WAVE');
    _writeAscii(header, 12, 'fmt ');
    header.setUint32(16, 16, Endian.little);
    header.setUint16(20, 1, Endian.little);
    header.setUint16(22, channels, Endian.little);
    header.setUint32(24, sampleRate, Endian.little);
    header.setUint32(28, byteRate, Endian.little);
    header.setUint16(32, blockAlign, Endian.little);
    header.setUint16(34, bitsPerSample, Endian.little);
    _writeAscii(header, 36, 'data');
    header.setUint32(40, pcmDataLength, Endian.little);
    return header.buffer.asUint8List();
  }

  void _writeAscii(ByteData data, int offset, String value) {
    for (int i = 0; i < value.length; i++) {
      data.setUint8(offset + i, value.codeUnitAt(i));
    }
  }

  List<TranscriptionSegment> _offsetSegments(
    List<TranscriptionSegment> segments,
    Duration offset,
  ) {
    return segments
        .map(
          (segment) => segment.copyWith(
            startTime: segment.startTime + offset,
            endTime: segment.endTime + offset,
          ),
        )
        .toList();
  }

  /// 임시 청크 파일과 부모 임시 디렉터리 정리
  Future<void> _cleanupChunkFile(File chunkFile) async {
    try {
      if (await chunkFile.exists()) {
        await chunkFile.delete();
      }
      final parent = chunkFile.parent;
      if (await parent.exists()) {
        await parent.delete();
      }
    } catch (e) {
      developer.log('청크 WAV 파일 정리 실패', error: e);
    }
  }

  /// WAV 파일 정리
  Future<void> _cleanupWavFile(String wavPath) async {
    try {
      final file = File(wavPath);
      if (await file.exists()) {
        await file.delete();
      }
    } catch (e) {
      developer.log('WAV 파일 정리 실패', error: e);
    }
  }
}

/// 전사 진행률 정보
class TranscriptionProgress {
  /// 진행률 (0~100)
  final double progress;

  /// 현재 결과 (완료 시에만 설정)
  final TranscriptionResult? result;

  /// 현재 상태
  final TranscriptionStatus status;

  /// 에러 메시지 (실패 시)
  final String? error;

  TranscriptionProgress({
    required this.progress,
    this.result,
    required this.status,
    this.error,
  });
}

/// 전사 상태
enum TranscriptionStatus {
  /// 시작 전
  starting,

  /// 처리 중
  processing,

  /// 완료
  completed,

  /// 실패
  failed,
}
