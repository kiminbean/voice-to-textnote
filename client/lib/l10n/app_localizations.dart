import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_ko.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('ko')
  ];

  /// Application title
  ///
  /// In ko, this message translates to:
  /// **'Voice TextNote'**
  String get appTitle;

  /// FAB tooltip for starting new recording
  ///
  /// In ko, this message translates to:
  /// **'새 녹음'**
  String get newRecording;

  /// Popup menu tooltip
  ///
  /// In ko, this message translates to:
  /// **'더보기'**
  String get more;

  /// No description provided for @teams.
  ///
  /// In ko, this message translates to:
  /// **'팀'**
  String get teams;

  /// No description provided for @search.
  ///
  /// In ko, this message translates to:
  /// **'검색'**
  String get search;

  /// No description provided for @templates.
  ///
  /// In ko, this message translates to:
  /// **'양식 관리'**
  String get templates;

  /// No description provided for @vocabulary.
  ///
  /// In ko, this message translates to:
  /// **'사용자 사전'**
  String get vocabulary;

  /// No description provided for @logout.
  ///
  /// In ko, this message translates to:
  /// **'로그아웃'**
  String get logout;

  /// No description provided for @guestModeBanner.
  ///
  /// In ko, this message translates to:
  /// **'게스트 모드 — 데이터가 24시간 후 삭제됩니다'**
  String get guestModeBanner;

  /// No description provided for @register.
  ///
  /// In ko, this message translates to:
  /// **'회원가입'**
  String get register;

  /// No description provided for @meetingListError.
  ///
  /// In ko, this message translates to:
  /// **'미팅 목록을 불러올 수 없습니다'**
  String get meetingListError;

  /// No description provided for @noMeetings.
  ///
  /// In ko, this message translates to:
  /// **'녹음된 미팅이 없습니다'**
  String get noMeetings;

  /// No description provided for @noMeetingsHint.
  ///
  /// In ko, this message translates to:
  /// **'아래 버튼을 눌러 녹음을 시작하세요'**
  String get noMeetingsHint;

  /// No description provided for @syncFailed.
  ///
  /// In ko, this message translates to:
  /// **'서버 동기화 실패. 로컬 데이터를 표시합니다.'**
  String get syncFailed;

  /// No description provided for @deleteMeeting.
  ///
  /// In ko, this message translates to:
  /// **'미팅 삭제'**
  String get deleteMeeting;

  /// No description provided for @deleteMeetingConfirm.
  ///
  /// In ko, this message translates to:
  /// **'이 미팅을 삭제하시겠습니까? 서버에서도 삭제됩니다.'**
  String get deleteMeetingConfirm;

  /// No description provided for @cancel.
  ///
  /// In ko, this message translates to:
  /// **'취소'**
  String get cancel;

  /// No description provided for @delete.
  ///
  /// In ko, this message translates to:
  /// **'삭제'**
  String get delete;

  /// No description provided for @logoutConfirm.
  ///
  /// In ko, this message translates to:
  /// **'로그아웃하시겠습니까?'**
  String get logoutConfirm;

  /// No description provided for @recordingTitle.
  ///
  /// In ko, this message translates to:
  /// **'새 녹음'**
  String get recordingTitle;

  /// No description provided for @startRecording.
  ///
  /// In ko, this message translates to:
  /// **'녹음 시작'**
  String get startRecording;

  /// No description provided for @stopRecording.
  ///
  /// In ko, this message translates to:
  /// **'녹음 중지'**
  String get stopRecording;

  /// No description provided for @tapToRecord.
  ///
  /// In ko, this message translates to:
  /// **'탭하여 녹음 시작'**
  String get tapToRecord;

  /// No description provided for @recordingInProgress.
  ///
  /// In ko, this message translates to:
  /// **'녹음 중...'**
  String get recordingInProgress;

  /// No description provided for @recordingPaused.
  ///
  /// In ko, this message translates to:
  /// **'일시 정지됨'**
  String get recordingPaused;

  /// No description provided for @recordingComplete.
  ///
  /// In ko, this message translates to:
  /// **'녹음 완료'**
  String get recordingComplete;

  /// No description provided for @processing.
  ///
  /// In ko, this message translates to:
  /// **'처리 중'**
  String get processing;

  /// No description provided for @processingWait.
  ///
  /// In ko, this message translates to:
  /// **'처리 시작 대기 중'**
  String get processingWait;

  /// No description provided for @uploading.
  ///
  /// In ko, this message translates to:
  /// **'오디오 파일 업로드 중...'**
  String get uploading;

  /// No description provided for @transcribing.
  ///
  /// In ko, this message translates to:
  /// **'음성 인식(STT) 처리 중...'**
  String get transcribing;

  /// No description provided for @diarizing.
  ///
  /// In ko, this message translates to:
  /// **'화자 분리 처리 중...'**
  String get diarizing;

  /// No description provided for @generatingMinutes.
  ///
  /// In ko, this message translates to:
  /// **'회의록 생성 중...'**
  String get generatingMinutes;

  /// No description provided for @summarizing.
  ///
  /// In ko, this message translates to:
  /// **'AI 요약 생성 중...'**
  String get summarizing;

  /// No description provided for @processingComplete.
  ///
  /// In ko, this message translates to:
  /// **'처리 완료!'**
  String get processingComplete;

  /// No description provided for @processingFailed.
  ///
  /// In ko, this message translates to:
  /// **'처리 실패'**
  String get processingFailed;

  /// No description provided for @audioProcessing.
  ///
  /// In ko, this message translates to:
  /// **'오디오 처리 중'**
  String get audioProcessing;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'ko'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'ko':
      return AppLocalizationsKo();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
