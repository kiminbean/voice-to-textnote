// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Korean (`ko`).
class AppLocalizationsKo extends AppLocalizations {
  AppLocalizationsKo([String locale = 'ko']) : super(locale);

  @override
  String get appTitle => 'Voice TextNote';

  @override
  String get newRecording => '새 녹음';

  @override
  String get more => '더보기';

  @override
  String get teams => '팀';

  @override
  String get search => '검색';

  @override
  String get templates => '양식 관리';

  @override
  String get vocabulary => '사용자 사전';

  @override
  String get logout => '로그아웃';

  @override
  String get guestModeBanner => '게스트 모드 — 데이터가 24시간 후 삭제됩니다';

  @override
  String get register => '회원가입';

  @override
  String get meetingListError => '미팅 목록을 불러올 수 없습니다';

  @override
  String get noMeetings => '녹음된 미팅이 없습니다';

  @override
  String get noMeetingsHint => '아래 버튼을 눌러 녹음을 시작하세요';

  @override
  String get syncFailed => '서버 동기화 실패. 로컬 데이터를 표시합니다.';

  @override
  String get deleteMeeting => '미팅 삭제';

  @override
  String get deleteMeetingConfirm => '이 미팅을 삭제하시겠습니까? 서버에서도 삭제됩니다.';

  @override
  String get cancel => '취소';

  @override
  String get delete => '삭제';

  @override
  String get logoutConfirm => '로그아웃하시겠습니까?';

  @override
  String get recordingTitle => '새 녹음';

  @override
  String get startRecording => '녹음 시작';

  @override
  String get stopRecording => '녹음 중지';

  @override
  String get tapToRecord => '탭하여 녹음 시작';

  @override
  String get recordingInProgress => '녹음 중...';

  @override
  String get recordingPaused => '일시 정지됨';

  @override
  String get recordingComplete => '녹음 완료';

  @override
  String get processing => '처리 중';

  @override
  String get processingWait => '처리 시작 대기 중';

  @override
  String get uploading => '오디오 파일 업로드 중...';

  @override
  String get transcribing => '음성 인식(STT) 처리 중...';

  @override
  String get diarizing => '화자 분리 처리 중...';

  @override
  String get generatingMinutes => '회의록 생성 중...';

  @override
  String get summarizing => 'AI 요약 생성 중...';

  @override
  String get processingComplete => '처리 완료!';

  @override
  String get processingFailed => '처리 실패';

  @override
  String get audioProcessing => '오디오 처리 중';
}
