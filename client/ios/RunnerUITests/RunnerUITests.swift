import XCTest

@MainActor
final class RunnerUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        XCUIDevice.shared.orientation = .portrait

        if !name.contains("Permission") {
            addUIInterruptionMonitor(withDescription: "System permission or trust dialog") { alert in
                for title in ["허용", "확인", "계속", "Allow", "OK", "Continue", "Trust"] {
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
        if name.contains("Permission") || name.contains("UnfinishedRecording") {
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
        tapSpringboardButton(["허용", "Allow", "OK"])
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
        allowAnySpringboardAlertIfPresent()
        discardRecoveryDialogIfPresent(timeout: 8)
        allowAnySpringboardAlertIfPresent()
        attachScreenshot("unfinished_recording_recovery_ios_initial")
        try ensureGuestHome()
        allowAnySpringboardAlertIfPresent()
        try openRecordingScreen()
        tapRecordStartButton()

        let alert = waitForSpringboardAlert(timeout: 5)
        if alert.exists {
            tapSpringboardButton(["허용", "Allow", "OK"])
        }

        var activeRecording = waitForAnyVisibleElement(
            labels: ["녹음 중", "녹음 중지"],
            timeout: 5
        )
        if activeRecording == nil {
            tapRecordStartButton()
            activeRecording = waitForAnyVisibleElement(
                labels: ["녹음 중", "녹음 중지"],
                timeout: 15
            )
        }
        attachUIHierarchy("unfinished_recording_recovery_ios_active_ui_hierarchy")
        attachScreenshot("unfinished_recording_recovery_ios_active")
        XCTAssertNotNil(activeRecording, "Expected active recording before forced relaunch.")

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
        return tapFirstHittableButton(labels: ["녹음 시작"])
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
        tapSpringboardButton(["허용", "확인", "계속", "Allow", "OK", "Continue"])
    }

    private func allowAnySpringboardAlertIfPresent() {
        let alert = waitForSpringboardAlert(timeout: 1)
        guard alert.exists else { return }
        attachScreenshot("ios_springboard_alert_before_continue")
        attachSpringboardHierarchy("ios_springboard_alert_before_continue_hierarchy")
        tapSpringboardButton(["허용", "확인", "계속", "Allow", "OK", "Continue"])
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
