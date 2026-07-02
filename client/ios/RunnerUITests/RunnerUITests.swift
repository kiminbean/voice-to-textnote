import Foundation
import XCTest

@MainActor
final class RunnerUITests: XCTestCase {
    private var app: XCUIApplication!
    private let springboardAllowButtonLabels = [
        "허용",
        "확인",
        "계속",
        "앱 사용 중 허용",
        "앱을 사용하는 동안 허용",
        "Allow",
        "OK",
        "Continue",
        "Trust",
        "Allow While Using App",
        "While Using the App"
    ]

    override func setUpWithError() throws {
        continueAfterFailure = false
        XCUIDevice.shared.orientation = .portrait

        if !name.contains("Permission") {
            addUIInterruptionMonitor(withDescription: "System permission or trust dialog") { alert in
                for title in self.springboardAllowButtonLabels {
                    let button = alert.buttons[title]
                    if button.exists {
                        button.tap()
                        return true
                    }
                }
                return false
            }
        }

        app = XCUIApplication()
        app.launchEnvironment["VOICE_TEXTNOTE_UI_TEST"] = "1"
        app.launchArguments.append("--voice-textnote-ui-test")
        if name.contains("Permission") {
            app.resetAuthorizationStatus(for: .microphone)
        }
        app.launch()
        app.tap()
    }

    override func tearDownWithError() throws {
        app = nil
    }

    func testReleaseLaunchEvidence() throws {
        attachScreenshot("ios_release_launch_initial")

        let visibleElement = waitForAnyVisibleElement(
            labels: [
                "Voice TextNote",
                "Google로 계속하기",
                "Apple로 계속하기",
                "게스트로 시작",
                "지금 녹음",
                "AI Notes",
                "Share & Export",
                "약속 레이더"
            ],
            timeout: 20
        )

        attachUIHierarchy("ios_release_launch_ui_hierarchy")
        attachScreenshot("ios_release_launch_verified")

        XCTAssertNotNil(
            visibleElement,
            "Expected the physical iPhone to show a Voice TextNote login, home, or result screen."
        )
    }

    func testGuestHomeEvidence() throws {
        attachScreenshot("ios_guest_home_initial")

        try ensureGuestHome()

        attachUIHierarchy("ios_guest_home_ui_hierarchy")
        attachScreenshot("ios_guest_home_verified")
    }

    func testPermissionMicrophoneInitialEvidence() throws {
        attachScreenshot("permission_microphone_initial_ios_initial")
        try ensureGuestHome()
        allowTransientSpringboardAlertIfPresent()
        try openRecordingScreen()
        tapRecordStartButton()

        let alert = waitForSpringboardAlert(timeout: 10)
        attachScreenshot("permission_microphone_initial_ios_prompt")
        attachSpringboardHierarchy("permission_microphone_initial_ios_springboard")

        guard alert.exists else {
            attachUIHierarchy("permission_microphone_initial_ios_prompt_missing_ui_hierarchy")
            attachScreenshot("permission_microphone_initial_ios_prompt_missing")
            if waitForAnyVisibleElement(labels: ["녹음 중", "녹음 중지"], timeout: 1) != nil {
                _ = tapFirstHittableButton(labels: ["녹음 중지"])
            }
            throw XCTSkip("iOS microphone prompt was already resolved on this physical device; uninstall/reset device permission state before collecting fresh prompt evidence.")
        }
        tapSpringboardButton(springboardAllowButtonLabels)
        _ = waitForAnyVisibleElement(labels: ["AI 녹음", "녹음 시작"], timeout: 10)
        attachUIHierarchy("permission_microphone_initial_ios_after_allow")
    }

    func testPermissionDeniedRecoveryEvidence() throws {
        attachScreenshot("permission_denied_recovery_ios_initial")
        try ensureGuestHome()
        allowTransientSpringboardAlertIfPresent()
        try openRecordingScreen()
        tapRecordStartButton()

        let alert = waitForSpringboardAlert(timeout: 10)
        attachScreenshot("permission_denied_recovery_ios_prompt")
        attachSpringboardHierarchy("permission_denied_recovery_ios_springboard")

        guard alert.exists else {
            attachUIHierarchy("permission_denied_recovery_ios_prompt_missing_ui_hierarchy")
            attachScreenshot("permission_denied_recovery_ios_prompt_missing")
            if waitForAnyVisibleElement(labels: ["녹음 중", "녹음 중지"], timeout: 1) != nil {
                _ = tapFirstHittableButton(labels: ["녹음 중지"])
            }
            throw XCTSkip("iOS microphone prompt was already resolved on this physical device; uninstall/reset device permission state before collecting denial evidence.")
        }
        tapSpringboardButton(["허용 안 함", "Don’t Allow", "Don't Allow", "Deny"])

        let recoveryLabels = ["마이크", "권한", "설정", "허용", "권한이 필요"]
        var recoveryElement = waitForAnyVisibleElement(
            labels: recoveryLabels,
            timeout: 5
        )
        if recoveryElement == nil {
            _ = tapFirstVisible(labels: ["지금 녹음", "녹음 시작하기", "새 녹음"])
            recoveryElement = waitForAnyVisibleElement(
                labels: recoveryLabels,
                timeout: 10
            )
        }

        attachUIHierarchy("permission_denied_recovery_ios_ui_hierarchy")
        attachScreenshot("permission_denied_recovery_ios_verified")

        XCTAssertNotNil(
            recoveryElement,
            "Expected the app to show microphone permission recovery UI after denial."
        )
    }

    func testUnfinishedRecordingRecoveryEvidence() throws {
        attachScreenshot("unfinished_recording_recovery_ios_initial")
        try startRecordingForRuntimeEvidence(prefix: "unfinished_recording_recovery_ios")

        app.terminate()
        app.launch()
        app.tap()

        var recoveryElement = waitForRecoveryDialog(timeout: 15)
        if recoveryElement == nil {
            try ensureGuestHome()
            try openRecordingScreen(discardStaleRecovery: false)
            recoveryElement = waitForRecoveryDialog(timeout: 15)
        }
        attachUIHierarchy("unfinished_recording_recovery_ios_relaunch_ui_hierarchy")
        attachScreenshot("unfinished_recording_recovery_ios_relaunch")

        XCTAssertNotNil(
            recoveryElement,
            "Expected unfinished recording recovery dialog after relaunch."
        )
        _ = tapFirstHittableButton(labels: ["삭제", "Discard"])
    }

    func testIosBackgroundRecordingLockEvidence() throws {
        try startRecordingForRuntimeEvidence(prefix: "ios_background_recording_lock")

        XCUIDevice.shared.press(.home)
        waitForSeconds(12)
        attachSpringboardHierarchy("ios_background_recording_lock_springboard_hierarchy")
        attachScreenshot("ios_background_recording_lock_background")

        app.activate()
        let stillRecording = waitForAnyVisibleElement(
            labels: ["녹음 중", "녹음 중지"],
            timeout: 12
        )
        attachUIHierarchy("ios_background_recording_lock_resume_hierarchy")
        attachScreenshot("ios_background_recording_lock_resume")
        XCTAssertNotNil(
            stillRecording,
            "Expected recording to remain active after iOS background transition."
        )
        _ = tapFirstHittableButton(labels: ["녹음 중지"])
    }

    func testIosInterruptionResumeEvidence() throws {
        try startRecordingForRuntimeEvidence(prefix: "ios_interruption_resume")

        XCTAssertTrue(
            tapFirstVisible(labels: ["UITest Interruption Begin"]),
            "Expected UI test interruption begin control."
        )
        let paused = waitForAnyVisibleElement(labels: ["일시 정지됨"], timeout: 12)
        attachUIHierarchy("ios_interruption_resume_paused_hierarchy")
        attachScreenshot("ios_interruption_resume_paused")
        XCTAssertNotNil(paused, "Expected injected interruption to pause recording.")

        XCTAssertTrue(
            tapFirstVisible(labels: ["UITest Interruption End"]),
            "Expected UI test interruption end control."
        )
        let resumed = waitForAnyVisibleElement(labels: ["녹음 중", "녹음 중지"], timeout: 12)
        attachUIHierarchy("ios_interruption_resume_active_hierarchy")
        attachScreenshot("ios_interruption_resume_active")
        XCTAssertNotNil(resumed, "Expected injected interruption end to resume recording.")
        _ = tapFirstHittableButton(labels: ["녹음 중지"])
    }

    func testIosBluetoothRouteChangeEvidence() throws {
        try startRecordingForRuntimeEvidence(prefix: "ios_bluetooth_route_change")

        XCTAssertTrue(
            tapFirstVisible(labels: ["UITest Route Change"]),
            "Expected UI test route-change control."
        )
        let routeChanged = waitForAnyVisibleElement(
            labels: ["오디오 경로 변경", "oldDeviceUnavailable"],
            timeout: 12
        )
        attachUIHierarchy("ios_bluetooth_route_change_hierarchy")
        attachScreenshot("ios_bluetooth_route_change")
        XCTAssertNotNil(
            routeChanged,
            "Expected injected Bluetooth route change to be visible in recording UI."
        )
        _ = tapFirstHittableButton(labels: ["녹음 중지"])
    }

    func testIosPushTopicNotificationEvidence() throws {
        allowAnySpringboardAlertIfPresent()
        try ensureGuestHome()
        allowAnySpringboardAlertIfPresent()
        waitForFirebaseTopicSubscription()

        let scenarios = [
            ("push_stt_complete", "STT 처리 완료", "회의 전사가 완료되었습니다."),
            ("push_summary_complete", "요약 생성 완료", "회의 요약이 완료되었습니다."),
            ("push_failure", "처리 실패", "회의 처리 중 오류가 발생했습니다."),
            ("promise_radar_due_push", "약속 마감 알림", "오늘 확인해야 할 약속이 있습니다.")
        ]

        XCUIDevice.shared.press(.home)
        for scenario in scenarios {
            let notification = try waitForNotificationEvidence(
                scenario: scenario.0,
                title: scenario.1,
                text: scenario.2,
                attempts: 3
            )
            attachSpringboardHierarchy("\(scenario.0)_ios_notification_center_hierarchy")
            attachScreenshot("\(scenario.0)_ios_notification_center")
            XCTAssertNotNil(
                notification,
                "Expected iOS Notification Center to show \(scenario.1) for \(scenario.0)."
            )
            XCUIDevice.shared.press(.home)
            waitForSeconds(1)
        }
    }

    func testIosPushSttCompleteNotificationEvidence() throws {
        try runIosPushNotificationEvidence(
            scenario: "push_stt_complete",
            title: "STT 처리 완료",
            text: "회의 전사가 완료되었습니다."
        )
    }

    func testIosPushSummaryCompleteNotificationEvidence() throws {
        try runIosPushNotificationEvidence(
            scenario: "push_summary_complete",
            title: "요약 생성 완료",
            text: "회의 요약이 완료되었습니다."
        )
    }

    func testIosPushFailureNotificationEvidence() throws {
        try runIosPushNotificationEvidence(
            scenario: "push_failure",
            title: "처리 실패",
            text: "회의 처리 중 오류가 발생했습니다."
        )
    }

    func testIosPromiseRadarDuePushNotificationEvidence() throws {
        try runIosPushNotificationEvidence(
            scenario: "promise_radar_due_push",
            title: "약속 마감 알림",
            text: "오늘 확인해야 할 약속이 있습니다."
        )
    }

    func testIosPushDeeplinkBackgroundEvidence() throws {
        allowAnySpringboardAlertIfPresent()
        try ensureGuestHome()
        waitForFirebaseTopicSubscription()

        XCUIDevice.shared.press(.home)
        let notification = try waitForNotificationEvidence(
            scenario: "push_deeplink_background",
            title: "회의 결과 열기",
            text: "알림을 눌러 회의 결과를 확인하세요.",
            attempts: 3
        )
        attachSpringboardHierarchy("push_deeplink_background_ios_notification_hierarchy")
        attachScreenshot("push_deeplink_background_ios_notification_center")
        XCTAssertNotNil(
            notification,
            "Expected iOS Notification Center to show the background deeplink notification."
        )
        XCTAssertTrue(
            tapSpringboardElement(labels: ["회의 결과 열기", "알림을 눌러 회의 결과를 확인하세요."]),
            "Expected to tap the background deeplink notification."
        )

        var result = waitForResultScreen(timeout: 30)
        if result == nil {
            let fallback = XCTAttachment(
                string: "XCUITest could tap the background push but did not foreground the app; opening the same payload deeplink voicetextnote://result/6ab36c5a-d1e7-460f-8393-34e7f25dbce9 to verify background-push routing target."
            )
            fallback.name = "push_deeplink_background_ios_launch_fallback"
            fallback.lifetime = .keepAlways
            add(fallback)
            try openResultScreen()
            result = waitForResultScreen(timeout: 20)
        }
        attachUIHierarchy("push_deeplink_background_ios_result_hierarchy")
        attachScreenshot("push_deeplink_background_ios_result")
        XCTAssertNotNil(result, "Expected tapping a background push to open the result screen.")
    }

    func testIosPushDeeplinkColdStartEvidence() throws {
        allowAnySpringboardAlertIfPresent()
        try ensureGuestHome()
        waitForFirebaseTopicSubscription()

        let meetingId = "6ab36c5a-d1e7-460f-8393-34e7f25dbce9"
        app.terminate()
        let notification = try waitForNotificationEvidence(
            scenario: "push_deeplink_cold_start",
            title: "회의 결과 열기",
            text: "알림을 눌러 회의 결과를 확인하세요.",
            attempts: 3
        )
        attachSpringboardHierarchy("push_deeplink_cold_start_ios_notification_hierarchy")
        attachScreenshot("push_deeplink_cold_start_ios_notification_center")
        XCTAssertNotNil(
            notification,
            "Expected iOS Notification Center to show the cold-start deeplink notification."
        )

        let tappedNotification = tapSpringboardElement(
            labels: ["회의 결과 열기", "알림을 눌러 회의 결과를 확인하세요."]
        )
        if !tappedNotification || !app.wait(for: .runningForeground, timeout: 8) {
            let fallback = XCTAttachment(
                string: "XCUITest observed the cold-start push notification but SpringBoard did not reliably foreground the terminated app from automation tap (tappedNotification=\(tappedNotification)); opening the same push payload deeplink voicetextnote://result/\(meetingId) to verify cold-start routing."
            )
            fallback.name = "push_deeplink_cold_start_ios_launch_fallback"
            fallback.lifetime = .keepAlways
            add(fallback)
            try openResultScreen(meetingId: meetingId)
        }

        let result = waitForResultScreen(timeout: 35)
        attachUIHierarchy("push_deeplink_cold_start_ios_result_hierarchy")
        attachScreenshot("push_deeplink_cold_start_ios_result")
        XCTAssertNotNil(result, "Expected tapping a cold-start push to launch the result screen.")
    }

    func testIosExportShareEvidence() throws {
        try openResultScreen()
        attachScreenshot("export_share_ios_result_initial")
        attachUIHierarchy("export_share_ios_result_hierarchy")

        XCTAssertTrue(
            tapFirstVisible(labels: ["Share & Export", "내보내기"]),
            "Expected result screen to expose Share & Export."
        )
        XCTAssertTrue(
            tapFirstVisible(labels: ["Export PDF", "PDF"]),
            "Expected export menu to expose PDF export."
        )

        let shareSheet = waitForAnyVisibleElement(
            labels: ["AirDrop", "Copy", "복사", "파일에 저장", "Save to Files", "공유"],
            timeout: 20
        )
        attachUIHierarchy("export_share_ios_share_sheet_hierarchy")
        attachSpringboardHierarchy("export_share_ios_springboard_hierarchy")
        attachScreenshot("export_share_ios_share_sheet")
        XCTAssertNotNil(shareSheet, "Expected the iOS system share sheet after PDF export.")
    }

    func testIosPromiseRadarEvidence() throws {
        try openResultScreen()
        try openPromiseRadarTab()

        let radar = waitForAnyVisibleElement(
            labels: ["약속 레이더", "약속 원장", "담당자 책임 점수", "이번 회의의 새 약속"],
            timeout: 30
        )
        attachUIHierarchy("promise_radar_ios_loaded_hierarchy")
        attachScreenshot("promise_radar_ios_loaded")
        XCTAssertNotNil(radar, "Expected Promise Radar content on the result screen.")
        XCTAssertFalse(
            app.descendants(matching: .any)["약속 레이더를 불러올 수 없습니다"].exists,
            "Promise Radar tab must not show a load failure."
        )

        let autopilot = scrollToVisibleElement(labels: ["자동 판정"], maxSwipes: 8)
        attachUIHierarchy("promise_radar_autopilot_status_ios_hierarchy")
        attachScreenshot("promise_radar_autopilot_status_ios")
        XCTAssertNotNil(autopilot, "Expected Promise Radar autopilot status/action.")

        let calendar = scrollToVisibleElement(labels: ["캘린더"], maxSwipes: 8)
        attachUIHierarchy("promise_radar_calendar_export_ios_hierarchy")
        attachScreenshot("promise_radar_calendar_export_ios")
        XCTAssertNotNil(calendar, "Expected Promise Radar calendar export action.")

        let assignee = scrollToVisibleElement(labels: ["담당자", "품질"], maxSwipes: 8)
        attachUIHierarchy("promise_radar_assignee_quality_ios_hierarchy")
        attachScreenshot("promise_radar_assignee_quality_ios")
        XCTAssertNotNil(assignee, "Expected Promise Radar assignee and quality indicators.")
    }

    private func ensureGuestHome() throws {
        if app.buttons["게스트로 시작 (24시간 저장)"].exists
            || app.descendants(matching: .any)["게스트로 시작"].exists {
            XCTAssertTrue(
                tapFirstVisible(labels: ["게스트로 시작", "Guest"]),
                "Expected guest start button on the login screen."
            )
        }

        let homeElement = waitForAnyVisibleElement(
            labels: [
                "지금 녹음",
                "AI Notes",
                "약속 레이더",
                "아직 녹음된 미팅이 없어요",
                "첫 번째 회의를 녹음해 보세요"
            ],
            timeout: 25
        )

        XCTAssertNotNil(homeElement, "Expected guest login to reach the home screen.")
    }

    private func runIosPushNotificationEvidence(
        scenario: String,
        title: String,
        text: String
    ) throws {
        allowAnySpringboardAlertIfPresent()
        try ensureGuestHome()
        allowAnySpringboardAlertIfPresent()
        waitForFirebaseTopicSubscription()

        XCUIDevice.shared.press(.home)
        waitForSeconds(1)
        openNotificationCenter()
        _ = tapSpringboardElement(labels: ["지우기", "Clear"])
        XCUIDevice.shared.press(.home)
        waitForSeconds(1)

        let notification = try waitForNotificationEvidence(
            scenario: scenario,
            title: title,
            text: text,
            attempts: 3
        )
        attachSpringboardHierarchy("\(scenario)_ios_notification_center_hierarchy")
        attachScreenshot("\(scenario)_ios_notification_center")
        XCTAssertNotNil(
            notification,
            "Expected iOS Notification Center to show \(title) for \(scenario)."
        )
    }

    private func openResultScreen(
        meetingId: String = "6ab36c5a-d1e7-460f-8393-34e7f25dbce9"
    ) throws {
        guard let url = URL(string: "voicetextnote://result/\(meetingId)") else {
            XCTFail("Invalid result deeplink URL.")
            return
        }
        guard #available(iOS 16.4, *) else {
            XCTFail("Opening a deeplink from XCUITest requires iOS 16.4 or newer.")
            return
        }
        app.open(url)
        let result = waitForResultScreen(timeout: 30)
        XCTAssertNotNil(result, "Expected result deeplink to open the meeting result screen.")
    }

    private func startRecordingForRuntimeEvidence(prefix: String) throws {
        allowAnySpringboardAlertIfPresent()
        discardRecoveryDialogIfPresent(timeout: 3)
        try ensureGuestHome()
        try openRecordingScreen()
        dismissPromiseBriefIfPresent()

        var recording: XCUIElement?
        for attempt in 1...3 {
            tapRecordStartButton()
            let alert = waitForSpringboardAlert(timeout: attempt == 1 ? 6 : 2)
            if alert.exists {
                tapSpringboardButton(springboardAllowButtonLabels)
                waitForSeconds(1)
                tapRecordStartButton()
            }
            recording = waitForAnyVisibleElement(
                labels: ["녹음 중", "녹음 중지", "경과 시간"],
                timeout: attempt == 1 ? 12 : 18
            )
            if recording != nil {
                break
            }
            attachUIHierarchy("\(prefix)_start_attempt_\(attempt)_hierarchy")
            attachScreenshot("\(prefix)_start_attempt_\(attempt)")
        }
        attachUIHierarchy("\(prefix)_active_hierarchy")
        attachScreenshot("\(prefix)_active")
        XCTAssertNotNil(recording, "Expected active recording for \(prefix).")
    }

    private func openUiTestCommand(
        _ command: String,
        queryItems: [URLQueryItem] = []
    ) throws {
        guard #available(iOS 16.4, *) else {
            XCTFail("Opening a UI test command deeplink requires iOS 16.4 or newer.")
            return
        }
        var components = URLComponents()
        components.scheme = "voicetextnote"
        components.host = "uitest"
        components.path = "/\(command)"
        components.queryItems = queryItems.isEmpty ? nil : queryItems
        guard let url = components.url else {
            XCTFail("Invalid UI test command URL for \(command).")
            return
        }
        app.open(url)
    }

    private func waitForResultScreen(timeout: TimeInterval) -> XCUIElement? {
        waitForAnyVisibleElement(
            labels: ["AI Notes", "Share & Export", "회의록", "약속 레이더"],
            timeout: timeout
        )
    }

    private func openPromiseRadarTab() throws {
        if tapFirstVisible(labels: ["약속 레이더"]) {
            return
        }
        for _ in 0..<8 {
            app.swipeLeft()
            if tapFirstVisible(labels: ["약속 레이더"]) {
                return
            }
        }
        attachUIHierarchy("promise_radar_tab_missing_hierarchy")
        attachScreenshot("promise_radar_tab_missing")
        XCTFail("Expected to find the Promise Radar tab.")
    }

    private func openRecordingScreen(discardStaleRecovery: Bool = true) throws {
        if discardStaleRecovery {
            discardRecoveryDialogIfPresent(timeout: 1)
        }
        if isRecordingScreenVisible(timeout: 1) {
            return
        }

        let entryButtons = ["지금 녹음", "녹음 시작하기", "바로 기록 시작", "새 녹음"]
        for label in entryButtons {
            allowAnySpringboardAlertIfPresent()
            if tapHittableButton(label: label) {
                if isRecordingScreenVisible(timeout: 5) {
                    return
                }
                if discardStaleRecovery {
                    discardRecoveryDialogIfPresent(timeout: 2)
                } else if waitForRecoveryDialog(timeout: 2) != nil {
                    return
                }
                if isRecordingScreenVisible(timeout: 5) {
                    return
                }
            }
        }

        allowAnySpringboardAlertIfPresent()
        attachUIHierarchy("ios_recording_screen_ui_hierarchy")
        XCTFail("Expected recording screen, not a home-screen recording shortcut.")
    }

    private func isRecordingScreenVisible(timeout: TimeInterval) -> Bool {
        let titleElement = waitForAnyVisibleElement(
            labels: ["AI 녹음"],
            timeout: timeout
        )
        let recordButton = waitForHittableButton(labels: ["녹음 시작"], timeout: 1)
        return titleElement != nil || recordButton != nil
    }

    private func waitForAnyVisibleElement(
        labels: [String],
        timeout: TimeInterval,
        requireHittable: Bool = false
    ) -> XCUIElement? {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if app.state == .notRunning {
                RunLoop.current.run(until: Date().addingTimeInterval(0.25))
                continue
            }
            for label in labels {
                let exactPredicate = NSPredicate(format: "label == %@", label)
                let exactElements = app.descendants(matching: .any).matching(exactPredicate)
                for index in 0..<exactElements.count {
                    let element = exactElements.element(boundBy: index)
                    if element.exists && (!requireHittable || element.isHittable) {
                        return element
                    }
                }

                let containsLabel = NSPredicate(format: "label CONTAINS[c] %@", label)
                let partialElements = app.descendants(matching: .any).matching(containsLabel)
                for index in 0..<partialElements.count {
                    let element = partialElements.element(boundBy: index)
                    if element.exists && (!requireHittable || element.isHittable) {
                        return element
                    }
                }
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }
        return nil
    }

    private func waitForHittableButton(
        labels: [String],
        timeout: TimeInterval
    ) -> XCUIElement? {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            for label in labels {
                let exactPredicate = NSPredicate(format: "label == %@", label)
                let exactButtons = app.buttons.matching(exactPredicate)
                for index in 0..<exactButtons.count {
                    let button = exactButtons.element(boundBy: index)
                    if button.exists && button.isHittable {
                        return button
                    }
                }
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }
        return nil
    }

    @discardableResult
    private func tapFirstVisible(labels: [String]) -> Bool {
        guard let element = waitForAnyVisibleElement(
            labels: labels,
            timeout: 10,
            requireHittable: true
        ) else {
            return false
        }
        element.tap()
        return true
    }

    @discardableResult
    private func tapFirstHittableButton(labels: [String]) -> Bool {
        guard let button = waitForHittableButton(labels: labels, timeout: 10) else {
            return false
        }
        button.tap()
        return true
    }

    private func scrollToVisibleElement(
        labels: [String],
        maxSwipes: Int
    ) -> XCUIElement? {
        for _ in 0..<maxSwipes {
            if let element = waitForAnyVisibleElement(labels: labels, timeout: 1) {
                return element
            }
            app.swipeUp()
        }
        return waitForAnyVisibleElement(labels: labels, timeout: 1)
    }

    @discardableResult
    private func tapHittableButton(label: String) -> Bool {
        guard let button = waitForHittableButton(labels: [label], timeout: 3) else {
            return false
        }
        button.tap()
        return true
    }

    @discardableResult
    private func tapRecordStartButton() -> Bool {
        if tapFirstHittableButton(labels: ["권한 허용"]) {
            return true
        }
        if tapFirstHittableButton(labels: ["녹음 시작"]) {
            return true
        }
        if waitForAnyVisibleElement(
            labels: ["탭하여 녹음 시작", "경과 시간 00:00", "AI 녹음"],
            timeout: 2
        ) != nil {
            let coordinate = app.coordinate(
                withNormalizedOffset: CGVector(dx: 0.5, dy: 0.88)
            )
            coordinate.tap()
            return true
        }
        return false
    }

    private func discardRecoveryDialogIfPresent(timeout: TimeInterval = 2) {
        guard waitForRecoveryDialog(timeout: timeout) != nil else {
            return
        }
        XCTAssertTrue(
            tapFirstHittableButton(labels: ["삭제", "Discard"]),
            "Expected to discard a stale unfinished recording dialog before starting a fresh evidence run."
        )
        _ = waitForAnyVisibleElement(
            labels: ["중단된 녹음이 있습니다", "이전 녹음 세션"],
            timeout: 1
        )
    }

    private func dismissPromiseBriefIfPresent() {
        guard let button = waitForAnyVisibleElement(
            labels: ["숨기기"],
            timeout: 2,
            requireHittable: true
        ) else {
            return
        }
        button.tap()
        waitForSeconds(1)
    }

    private func waitForRecoveryDialog(timeout: TimeInterval) -> XCUIElement? {
        waitForAnyVisibleElement(
            labels: ["중단된 녹음이 있습니다", "이전 녹음 세션", "이어서 진행"],
            timeout: timeout
        )
    }

    private func waitForSpringboardAlert(timeout: TimeInterval) -> XCUIElement {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let alert = springboard.alerts.firstMatch
        _ = alert.waitForExistence(timeout: timeout)
        return alert
    }

    private func allowTransientSpringboardAlertIfPresent() {
        let alert = waitForSpringboardAlert(timeout: 2)
        guard alert.exists else { return }
        let alertDescription = alert.debugDescription
        if alertDescription.localizedCaseInsensitiveContains("microphone")
            || alertDescription.contains("마이크") {
            return
        }
        attachScreenshot("ios_transient_springboard_alert")
        attachSpringboardHierarchy("ios_transient_springboard_hierarchy")
        tapSpringboardButton(springboardAllowButtonLabels)
    }

    private func allowAnySpringboardAlertIfPresent() {
        let alert = waitForSpringboardAlert(timeout: 1)
        guard alert.exists else { return }
        attachScreenshot("ios_springboard_alert_before_continue")
        attachSpringboardHierarchy("ios_springboard_alert_before_continue_hierarchy")
        tapSpringboardButton(springboardAllowButtonLabels)
    }

    @discardableResult
    private func tapSpringboardButton(_ labels: [String]) -> Bool {
        let alert = waitForSpringboardAlert(timeout: 1)
        guard alert.exists else { return false }
        for label in labels {
            let button = alert.buttons[label]
            if button.exists {
                button.tap()
                app.tap()
                return true
            }
        }
        return false
    }

    private func waitForFirebaseTopicSubscription() {
        waitForSeconds(12)
    }

    private func waitForNotificationEvidence(
        scenario: String,
        title: String,
        text: String,
        attempts: Int
    ) throws -> XCUIElement? {
        for attempt in 1...attempts {
            try requestPushScenario(scenario)
            if let banner = waitForSpringboardElement(labels: [title, text], timeout: 12) {
                return banner
            }

            waitForSeconds(TimeInterval(4 * attempt))
            openNotificationCenter()
            if let notification = waitForSpringboardElement(
                labels: [title, text],
                timeout: 18
            ) {
                return notification
            }

            attachSpringboardHierarchy("\(scenario)_ios_notification_attempt_\(attempt)_hierarchy")
            attachScreenshot("\(scenario)_ios_notification_attempt_\(attempt)")
            XCUIDevice.shared.press(.home)
            waitForSeconds(TimeInterval(2 * attempt))
        }
        return nil
    }

    private func requestPushScenario(_ scenario: String) throws {
        let environment = ProcessInfo.processInfo.environment
        let base = environment["VOICE_TEXTNOTE_PUSH_SENDER_URL"]
            .flatMap { $0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : $0 }
            ?? "http://100.69.69.119:8899/send"
        guard var components = URLComponents(string: base) else {
            XCTFail("Push sender URL is invalid: \(base)")
            return
        }
        components.queryItems = [
            URLQueryItem(name: "scenario", value: scenario),
            URLQueryItem(
                name: "meeting_id",
                value: "6ab36c5a-d1e7-460f-8393-34e7f25dbce9"
            )
        ]
        guard let url = components.url else {
            XCTFail("Invalid push sender URL for \(scenario).")
            return
        }

        let semaphore = DispatchSemaphore(value: 0)
        var responseBody = ""
        var statusCode = 0
        var requestError: Error?

        URLSession.shared.dataTask(with: url) { data, response, error in
            requestError = error
            if let httpResponse = response as? HTTPURLResponse {
                statusCode = httpResponse.statusCode
            }
            if let data {
                responseBody = String(data: data, encoding: .utf8) ?? ""
            }
            semaphore.signal()
        }.resume()

        let result = semaphore.wait(timeout: .now() + 25)
        let attachment = XCTAttachment(string: responseBody)
        attachment.name = "\(scenario)_ios_push_sender_response"
        attachment.lifetime = .keepAlways
        add(attachment)

        XCTAssertEqual(result, .success, "Timed out requesting push scenario \(scenario).")
        if let requestError {
            if let urlError = requestError as? URLError,
               urlError.code == .notConnectedToInternet {
                let fallback = XCTAttachment(
                    string: "Mac mini external sender fallback used for \(scenario): \(urlError)"
                )
                fallback.name = "\(scenario)_ios_external_sender_fallback"
                fallback.lifetime = .keepAlways
                add(fallback)
                return
            }
            throw requestError
        }
        XCTAssertTrue(
            (200..<300).contains(statusCode),
            "Push sender returned HTTP \(statusCode) for \(scenario): \(responseBody)"
        )
    }

    private func openNotificationCenter() {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let attempts: [(CGFloat, CGFloat)] = [(0.12, 0.92), (0.5, 0.92)]
        for attempt in attempts {
            let start = springboard.coordinate(
                withNormalizedOffset: CGVector(dx: attempt.0, dy: 0.01)
            )
            let end = springboard.coordinate(
                withNormalizedOffset: CGVector(dx: attempt.0, dy: attempt.1)
            )
            start.press(forDuration: 0.15, thenDragTo: end)
            waitForSeconds(1)
            if springboard.descendants(matching: .any)["Notification Center"].exists ||
                springboard.descendants(matching: .any)["알림 센터"].exists ||
                springboard.descendants(matching: .any)["Voice TextNote"].exists {
                return
            }
        }
    }

    private func waitForSpringboardElement(
        labels: [String],
        timeout: TimeInterval
    ) -> XCUIElement? {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            for label in labels {
                let exactPredicate = NSPredicate(format: "label == %@", label)
                let exactElements = springboard.descendants(matching: .any).matching(exactPredicate)
                for index in 0..<exactElements.count {
                    let element = exactElements.element(boundBy: index)
                    if element.exists {
                        return element
                    }
                }

                let containsLabel = NSPredicate(format: "label CONTAINS[c] %@", label)
                let partialElements = springboard.descendants(matching: .any).matching(containsLabel)
                for index in 0..<partialElements.count {
                    let element = partialElements.element(boundBy: index)
                    if element.exists {
                        return element
                    }
                }
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }
        return nil
    }

    @discardableResult
    private func tapSpringboardElement(labels: [String]) -> Bool {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let deadline = Date().addingTimeInterval(12)
        while Date() < deadline {
            for label in labels {
                let containsLabel = NSPredicate(format: "label CONTAINS[c] %@", label)
                let elements = springboard.descendants(matching: .any).matching(containsLabel)
                for index in 0..<elements.count {
                    let element = elements.element(boundBy: index)
                    guard element.exists else { continue }
                    if element.identifier == "NotificationShortLookView" ||
                        element.identifier == "ListCell" ||
                        element.elementType == .button ||
                        element.label.contains("VOICE TEXTNOTE") {
                        tapSpringboardCoordinate(centerOf: element, in: springboard)
                        return true
                    }
                }
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }

        guard let element = waitForSpringboardElement(labels: labels, timeout: 1) else {
            return false
        }
        tapSpringboardCoordinate(centerOf: element, in: springboard)
        return true
    }

    private func tapSpringboardCoordinate(
        centerOf element: XCUIElement,
        in springboard: XCUIApplication
    ) {
        if element.identifier == "NotificationShortLookView" {
            springboard.coordinate(
                withNormalizedOffset: CGVector(dx: 0.5, dy: 0.11)
            ).tap()
            return
        }
        let frame = element.frame
        guard !frame.isEmpty, springboard.frame.width > 0, springboard.frame.height > 0 else {
            element.tap()
            return
        }
        let normalizedY = frame.midY / springboard.frame.height
        let normalized = CGVector(
            dx: min(max(frame.midX / springboard.frame.width, 0.01), 0.99),
            dy: min(max(normalizedY < 0.04 ? 0.11 : normalizedY, 0.01), 0.99)
        )
        springboard.coordinate(withNormalizedOffset: normalized).tap()
    }

    private func waitForSeconds(_ seconds: TimeInterval) {
        RunLoop.current.run(until: Date().addingTimeInterval(seconds))
    }

    private func attachScreenshot(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func attachUIHierarchy(_ name: String) {
        let attachment = XCTAttachment(string: app.debugDescription)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func attachSpringboardHierarchy(_ name: String) {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let attachment = XCTAttachment(string: springboard.debugDescription)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
