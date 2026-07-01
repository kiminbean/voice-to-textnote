import XCTest

@MainActor
final class RunnerUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        XCUIDevice.shared.orientation = .portrait

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

        app = XCUIApplication()
        app.launchEnvironment["VOICE_TEXTNOTE_UI_TEST"] = "1"
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

    private func waitForAnyVisibleElement(
        labels: [String],
        timeout: TimeInterval
    ) -> XCUIElement? {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            for label in labels {
                let exact = app.descendants(matching: .any)[label]
                if exact.exists {
                    return exact
                }

                let containsLabel = NSPredicate(format: "label CONTAINS[c] %@", label)
                let partial = app.descendants(matching: .any).matching(containsLabel).firstMatch
                if partial.exists {
                    return partial
                }
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }
        return nil
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
}
