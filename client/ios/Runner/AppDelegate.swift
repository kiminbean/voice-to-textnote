// SPEC-MOBILE-005: iOS 백그라운드 녹음 안정성 고도화
// REQ-001: iOS 네이티브 녹음 서비스 구현
import Flutter
import UIKit
import AVFAudio

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  /// 백그라운드 태스크 식별자 (crash 방지 보조 수단)
  // @MX:NOTE: audio mode 앱에는 무제한 실행이 보장되지만, crash 방지용 보조 수단으로 사용
  private var backgroundTaskId: UIBackgroundTaskIdentifier = .invalid

  /// MethodChannel — Android MainActivity.kt와 동일한 인터페이스
  private let channelName = "com.voicetextnote.app/recording"

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    // Flutter 엔진 초기화 후 MethodChannel 등록
    let result = super.application(application, didFinishLaunchingWithOptions: launchOptions)

    setupRecordingMethodChannel()
    setupAudioSessionObservers()

    return result
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
  }

  // MARK: - MethodChannel 설정

  /// 녹음 MethodChannel 핸들러 등록 (REQ-001-01)
  private func setupRecordingMethodChannel() {
    guard let controller = window?.rootViewController as? FlutterViewController else {
      // FlutterViewController가 아직 준비되지 않은 경우 플러그인 레지스트리에서 engine 획득
      // @MX:WARN: window가 nil인 시점에 호출될 수 있음 — 대비 필요
      return
    }

    let channel = FlutterMethodChannel(
      name: channelName,
      binaryMessenger: controller.binaryMessenger
    )

    channel.setMethodCallHandler { [weak self] (call: FlutterMethodCall, result: @escaping FlutterResult) in
      let method = call.method
      if method == "startBackgroundTask" {
        self?.startBackgroundTask(result: result)
      } else if method == "stopBackgroundTask" {
        self?.stopBackgroundTask(result: result)
      } else if method == "flushRecording" {
        self?.flushRecording(result: result)
      } else if method == "startForegroundService" {
        // iOS에서는 불필요 — 호환성을 위해 no-op 응답
        result(true)
      } else if method == "stopForegroundService" {
        // iOS에서는 불필요 — 호환성을 위해 no-op 응답
        result(true)
      } else {
        result(FlutterMethodNotImplemented)
      }
    }
  }

  // MARK: - 백그라운드 태스크 관리

  /// 백그라운드 태스크 시작 (REQ-001-02)
  // @MX:NOTE: audio mode 앱에는 무제한 실행이 보장되지만, crash 방지 보조 수단
  private func startBackgroundTask(result: @escaping FlutterResult) {
    backgroundTaskId = UIApplication.shared.beginBackgroundTask(withName: "RecordingTask") {
      // 만료 핸들러 — OS가 백그라운드 시간을 회수할 때 호출
      self.endBackgroundTask()
    }
    result(true)
  }

  /// 백그라운드 태스크 중지 (REQ-001-03)
  private func stopBackgroundTask(result: @escaping FlutterResult) {
    endBackgroundTask()
    result(true)
  }

  /// 백그라운드 태스크 해제 (내부용)
  private func endBackgroundTask() {
    if backgroundTaskId != .invalid {
      UIApplication.shared.endBackgroundTask(backgroundTaskId)
      backgroundTaskId = .invalid
    }
  }

  // MARK: - 플러시 (오디오 세션 갱신)

  /// 녹음 플러시 — AVAudioSession 활성 상태 확인 및 갱신 (REQ-001-04)
  private func flushRecording(result: @escaping FlutterResult) {
    let session = AVAudioSession.sharedInstance()

    do {
      // 세션이 비활성화된 경우 재활성화
      if !session.isOtherAudioPlaying {
        try session.setActive(true, options: [])
      }
      result(true)
    } catch {
      NSLog("flushRecording 세션 활성화 실패: %@", error.localizedDescription)
      result(false)
    }
  }

  // MARK: - AVAudioSession 관찰

  /// 오디오 세션 알림 옵저버 등록
  private func setupAudioSessionObservers() {
    let session = AVAudioSession.sharedInstance()
    let notificationCenter = NotificationCenter.default

    // 인터럽션 알림 (REQ-002 네이티브 보조)
    notificationCenter.addObserver(
      forName: AVAudioSession.interruptionNotification,
      object: session,
      queue: nil
    ) { [weak self] notification in
      self?.handleInterruptionNotification(notification)
    }

    // 라우트 변경 알림 (REQ-003-04)
    notificationCenter.addObserver(
      forName: AVAudioSession.routeChangeNotification,
      object: session,
      queue: nil
    ) { [weak self] notification in
      self?.handleRouteChangeNotification(notification)
    }
  }

  /// 인터럽션 알림 처리 — Dart에 이벤트 전달
  private func handleInterruptionNotification(_ notification: Notification) {
    guard let userInfo = notification.userInfo,
          let typeValue = userInfo[AVAudioSessionInterruptionTypeKey] as? UInt,
          let type = AVAudioSession.InterruptionType(rawValue: typeValue) else {
      return
    }

    switch type {
    case .began:
      // 인터럽션 시작 (전화 수신 등)
      forwardToDart(method: "onInterruptionBegin", arguments: nil)

    case .ended:
      // 인터럽션 종료 — shouldResume 힌트 확인 (REQ-002-02)
      let optionsValue = userInfo[AVAudioSessionInterruptionOptionKey] as? UInt ?? 0
      let options = AVAudioSession.InterruptionOptions(rawValue: optionsValue)
      let shouldResume = options.contains(.shouldResume)

      forwardToDart(
        method: "onInterruptionEnd",
        arguments: ["shouldResume": shouldResume]
      )

    @unknown default:
      break
    }
  }

  /// 라우트 변경 알림 처리 — Dart에 이벤트 전달
  private func handleRouteChangeNotification(_ notification: Notification) {
    guard let userInfo = notification.userInfo,
          let reasonValue = userInfo[AVAudioSessionRouteChangeReasonKey] as? UInt,
          let reason = AVAudioSession.RouteChangeReason(rawValue: reasonValue) else {
      return
    }

    let reasonString: String
    switch reason {
    case .oldDeviceUnavailable:
      reasonString = "oldDeviceUnavailable"
    case .newDeviceAvailable:
      reasonString = "newDeviceAvailable"
    case .categoryChange:
      reasonString = "categoryChange"
    case .override:
      reasonString = "override"
    case .wakeFromSleep:
      reasonString = "wakeFromSleep"
    case .noSuitableRouteForCategory:
      reasonString = "noSuitableRouteForCategory"
    case .routeConfigurationChange:
      reasonString = "routeConfigurationChange"
    @unknown default:
      reasonString = "unknown"
    }

    forwardToDart(
      method: "onRouteChange",
      arguments: ["reason": reasonString]
    )
  }

  /// Dart에 MethodChannel 이벤트 전달
  private func forwardToDart(method: String, arguments: Any?) {
    guard let controller = window?.rootViewController as? FlutterViewController else {
      return
    }

    let channel = FlutterMethodChannel(
      name: channelName,
      binaryMessenger: controller.binaryMessenger
    )

    channel.invokeMethod(method, arguments: arguments)
  }
}
