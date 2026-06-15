// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'Voice to TextNote';

  @override
  String get newRecording => 'New Recording';

  @override
  String get more => 'More';

  @override
  String get teams => 'Teams';

  @override
  String get search => 'Search';

  @override
  String get templates => 'Templates';

  @override
  String get vocabulary => 'Vocabulary';

  @override
  String get logout => 'Logout';

  @override
  String get guestModeBanner =>
      'Guest mode — data will be deleted after 24 hours';

  @override
  String get register => 'Sign Up';

  @override
  String get meetingListError => 'Failed to load meeting list';

  @override
  String get noMeetings => 'No recorded meetings';

  @override
  String get noMeetingsHint => 'Tap the button below to start recording';

  @override
  String get syncFailed => 'Server sync failed. Showing local data.';

  @override
  String get deleteMeeting => 'Delete Meeting';

  @override
  String get deleteMeetingConfirm =>
      'Delete this meeting? It will also be deleted from the server.';

  @override
  String get cancel => 'Cancel';

  @override
  String get delete => 'Delete';

  @override
  String get logoutConfirm => 'Do you want to log out?';

  @override
  String get recordingTitle => 'New Recording';

  @override
  String get startRecording => 'Start Recording';

  @override
  String get stopRecording => 'Stop Recording';

  @override
  String get tapToRecord => 'Tap to start recording';

  @override
  String get recordingInProgress => 'Recording...';

  @override
  String get recordingPaused => 'Paused';

  @override
  String get recordingComplete => 'Recording Complete';

  @override
  String get processing => 'Processing';

  @override
  String get processingWait => 'Waiting to start processing';

  @override
  String get uploading => 'Uploading audio file...';

  @override
  String get transcribing => 'Speech recognition (STT) processing...';

  @override
  String get diarizing => 'Speaker diarization processing...';

  @override
  String get generatingMinutes => 'Generating meeting minutes...';

  @override
  String get summarizing => 'Generating AI summary...';

  @override
  String get processingComplete => 'Processing Complete!';

  @override
  String get processingFailed => 'Processing Failed';

  @override
  String get audioProcessing => 'Processing audio';
}
