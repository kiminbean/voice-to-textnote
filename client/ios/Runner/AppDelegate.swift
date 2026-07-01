// SPEC-MOBILE-005: iOS 백그라운드 녹음 안정성 고도화
// REQ-001: iOS 네이티브 녹음 서비스 구현
import Flutter
import UIKit
import AVFAudio
import FirebaseMessaging
import UserNotifications

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  /// 백그라운드 태스크 식별자 (crash 방지 보조 수단)
  // @MX:NOTE: audio mode 앱에는 무제한 실행이 보장되지만, crash 방지용 보조 수단으로 사용
  private var backgroundTaskId: UIBackgroundTaskIdentifier = .invalid

  /// MethodChannel — Android MainActivity.kt와 동일한 인터페이스
  private let channelName = "com.voicetextnote.app/recording"
  private let sharedImportChannelName = "com.voicetextnote.app/shared_import"
  private let deepLinkChannelName = "com.voicetextnote.app/deep_link"
  private var pendingInitialSharedImport: [String: String]?
  private var pendingLatestSharedImport: [String: String]?
  private var pendingInitialDeepLink: String?
  private var pendingLatestDeepLink: String?

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    // Flutter 엔진 초기화 후 MethodChannel 등록
    let result = super.application(application, didFinishLaunchingWithOptions: launchOptions)

    setupRecordingMethodChannel()
    setupSharedImportMethodChannel()
    setupDeepLinkMethodChannel()
    setupAudioSessionObservers()
    UNUserNotificationCenter.current().delegate = self
    if let remoteNotification = launchOptions?[.remoteNotification] as? [AnyHashable: Any] {
      queueNotificationDeepLink(from: remoteNotification)
    }
    DispatchQueue.main.async {
      application.registerForRemoteNotifications()
    }

    return result
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
  }

  override func application(
    _ application: UIApplication,
    didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
  ) {
    Messaging.messaging().apnsToken = deviceToken
    super.application(
      application,
      didRegisterForRemoteNotificationsWithDeviceToken: deviceToken
    )
  }

  override func application(
    _ application: UIApplication,
    didFailToRegisterForRemoteNotificationsWithError error: Error
  ) {
    NSLog("APNs 등록 실패: %@", error.localizedDescription)
    super.application(
      application,
      didFailToRegisterForRemoteNotificationsWithError: error
    )
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

  /// iOS Open In / deep link import를 Android shared_import 채널과 같은 계약으로 노출
  private func setupSharedImportMethodChannel() {
    guard let controller = window?.rootViewController as? FlutterViewController else {
      return
    }

    let channel = FlutterMethodChannel(
      name: sharedImportChannelName,
      binaryMessenger: controller.binaryMessenger
    )

    channel.setMethodCallHandler { [weak self] (call: FlutterMethodCall, result: @escaping FlutterResult) in
      guard let self = self else {
        result(nil)
        return
      }

      if call.method == "consumeInitialSharedImport" {
        let payload = self.pendingInitialSharedImport
        self.pendingInitialSharedImport = nil
        self.pendingLatestSharedImport = nil
        result(payload)
      } else if call.method == "consumeLatestSharedImport" {
        let payload = self.pendingLatestSharedImport
        self.pendingLatestSharedImport = nil
        result(payload)
      } else {
        result(FlutterMethodNotImplemented)
      }
    }
  }

  private func setupDeepLinkMethodChannel() {
    guard let controller = window?.rootViewController as? FlutterViewController else {
      return
    }

    let channel = FlutterMethodChannel(
      name: deepLinkChannelName,
      binaryMessenger: controller.binaryMessenger
    )

    channel.setMethodCallHandler { [weak self] (call: FlutterMethodCall, result: @escaping FlutterResult) in
      guard let self = self else {
        result(nil)
        return
      }

      if call.method == "consumeInitialDeepLink" {
        let path = self.pendingInitialDeepLink
        self.pendingInitialDeepLink = nil
        self.pendingLatestDeepLink = nil
        result(path)
      } else if call.method == "consumeLatestDeepLink" {
        let path = self.pendingLatestDeepLink
        self.pendingLatestDeepLink = nil
        result(path)
      } else if call.method == "activateNotificationDelegate" {
        UNUserNotificationCenter.current().delegate = self
        result(true)
      } else {
        result(FlutterMethodNotImplemented)
      }
    }
  }

  override func application(
    _ app: UIApplication,
    open url: URL,
    options: [UIApplication.OpenURLOptionsKey: Any] = [:]
  ) -> Bool {
    if let payload = sharedImportPayload(from: url) {
      queueSharedImport(payload)
      return true
    }

    if let path = deepLinkPath(from: url) {
      queueDeepLink(path)
      return true
    }

    return super.application(app, open: url, options: options)
  }

  override func userNotificationCenter(
    _ center: UNUserNotificationCenter,
    didReceive response: UNNotificationResponse,
    withCompletionHandler completionHandler: @escaping () -> Void
  ) {
    queueNotificationDeepLink(from: response.notification.request.content.userInfo)
    super.userNotificationCenter(
      center,
      didReceive: response,
      withCompletionHandler: completionHandler
    )
  }

  private func sharedImportPayload(from url: URL) -> [String: String]? {
    if url.isFileURL {
      return copySharedFile(url)
    }

    guard url.scheme == "voicetextnote",
          let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
          let items = components.queryItems else {
      return nil
    }

    var payload: [String: String] = [:]
    let supportedKeys = [
      "shared_url": "text",
      "shared_text": "text",
      "shared_title": "title",
      "shared_mime": "mimeType",
      "shared_file_path": "filePath",
      "shared_file_name": "fileName",
    ]

    for item in items {
      guard let mappedKey = supportedKeys[item.name],
            let value = item.value?.trimmingCharacters(in: .whitespacesAndNewlines),
            !value.isEmpty else {
        continue
      }

      if mappedKey == "text" {
        let existingText = payload[mappedKey].map { "\($0)\n" } ?? ""
        payload[mappedKey] = "\(existingText)\(value)"
      } else {
        payload[mappedKey] = value
      }
    }

    return payload.isEmpty ? nil : payload
  }

  private func queueSharedImport(_ payload: [String: String]) {
    pendingInitialSharedImport = payload
    pendingLatestSharedImport = payload
  }

  private func queueNotificationDeepLink(from userInfo: [AnyHashable: Any]) {
    if let deeplink = userInfo["deeplink"] as? String,
       let url = URL(string: deeplink),
       let path = deepLinkPath(from: url) {
      queueDeepLink(path)
      return
    }

    guard let meetingId = userInfo["meeting_id"] as? String,
          !meetingId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
      return
    }

    queueDeepLink("/result/\(meetingId)")
  }

  private func queueDeepLink(_ path: String) {
    pendingInitialDeepLink = path
    pendingLatestDeepLink = path
    forwardDeepLinkToDart(path)
  }

  private func deepLinkPath(from url: URL) -> String? {
    guard url.scheme == "voicetextnote" else {
      return nil
    }

    let host = url.host?.lowercased()
    let pathComponents = url.pathComponents.filter { $0 != "/" }
    let meetingId: String?
    if host == "result" || host == "summary" {
      meetingId = pathComponents.first
    } else if pathComponents.count >= 2 &&
                (pathComponents[0] == "result" || pathComponents[0] == "summary") {
      meetingId = pathComponents[1]
    } else {
      meetingId = nil
    }

    guard let id = meetingId?.trimmingCharacters(in: .whitespacesAndNewlines),
          !id.isEmpty else {
      return nil
    }
    return "/result/\(id)"
  }

  private func copySharedFile(_ url: URL) -> [String: String]? {
    let didAccess = url.startAccessingSecurityScopedResource()
    defer {
      if didAccess {
        url.stopAccessingSecurityScopedResource()
      }
    }

    let originalName = url.lastPathComponent.isEmpty ? "shared-import" : url.lastPathComponent
    let safeName = originalName.replacingOccurrences(
      of: "[^A-Za-z0-9가-힣._-]",
      with: "_",
      options: .regularExpression
    )
    let targetDir = FileManager.default.temporaryDirectory
      .appendingPathComponent("shared-imports", isDirectory: true)
    let target = targetDir.appendingPathComponent("\(Int(Date().timeIntervalSince1970 * 1000))-\(safeName)")

    do {
      try FileManager.default.createDirectory(
        at: targetDir,
        withIntermediateDirectories: true
      )
      if FileManager.default.fileExists(atPath: target.path) {
        try FileManager.default.removeItem(at: target)
      }
      try FileManager.default.copyItem(at: url, to: target)
    } catch {
      NSLog("shared import 파일 복사 실패: %@", error.localizedDescription)
      return nil
    }

    let mimeType = mimeTypeForSharedFile(url)
    return [
      "filePath": target.path,
      "fileName": originalName,
      "mimeType": mimeType,
      "title": (originalName as NSString).deletingPathExtension,
    ]
  }

  private func mimeTypeForSharedFile(_ url: URL) -> String {
    let ext = url.pathExtension.lowercased()
    if ext == "pdf" {
      return "application/pdf"
    }
    if ext == "docx" {
      return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
    switch ext {
    case "png":
      return "image/png"
    case "jpg", "jpeg":
      return "image/jpeg"
    case "webp":
      return "image/webp"
    case "heic":
      return "image/heic"
    case "heif":
      return "image/heif"
    default:
      return "application/octet-stream"
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
    default:
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

  private func forwardDeepLinkToDart(_ path: String) {
    guard let controller = window?.rootViewController as? FlutterViewController else {
      return
    }

    let channel = FlutterMethodChannel(
      name: deepLinkChannelName,
      binaryMessenger: controller.binaryMessenger
    )

    channel.invokeMethod("onDeepLink", arguments: path)
  }
}
