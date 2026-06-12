import Flutter
import Foundation

/// @MX:SPEC:REQ-MOBILE-011-01
///
/// iOS whisper.cpp + Core ML MethodChannel skeleton.
///
/// **Deprecated**: whisper_ggml_plus 패키지가 자체 네이티브 통합을 제공하므로
/// 이 플러그인은 더 이상 사용되지 않습니다. 제거 예정.
@available(*, deprecated, message: "whisper_ggml_plus 패키지로 대체됨")
final class WhisperSttPlugin: NSObject, FlutterPlugin {
  static let channelName = "com.voicetextnote/whisper_stt"

  static func register(with registrar: FlutterPluginRegistrar) {
    let channel = FlutterMethodChannel(
      name: channelName,
      binaryMessenger: registrar.messenger()
    )
    let instance = WhisperSttPlugin()
    channel.setMethodCallHandler(instance.handle)
  }

  private func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    switch call.method {
    case "isAvailable":
      result(false)
    case "getEngineInfo":
      result([
        "name": "whisper.cpp",
        "platform": "ios",
        "accelerator": "coreml",
        "model_version": "whisper-base"
      ])
    case "transcribe":
      result(FlutterError(
        code: "UNIMPLEMENTED",
        message: "iOS whisper.cpp Core ML transcription is not linked yet.",
        details: nil
      ))
    default:
      result(FlutterMethodNotImplemented)
    }
  }
}
