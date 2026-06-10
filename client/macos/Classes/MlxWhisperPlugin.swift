import FlutterMacOS
import Foundation

/// @MX:SPEC:REQ-MOBILE-011-02
///
/// macOS mlx-whisper MethodChannel skeleton.
final class MlxWhisperPlugin: NSObject, FlutterPlugin {
  static let channelName = "com.voicetextnote/whisper_stt"

  static func register(with registrar: FlutterPluginRegistrar) {
    let channel = FlutterMethodChannel(
      name: channelName,
      binaryMessenger: registrar.messenger
    )
    let instance = MlxWhisperPlugin()
    channel.setMethodCallHandler(instance.handle)
  }

  private func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    switch call.method {
    case "isAvailable":
      result(false)
    case "getEngineInfo":
      result([
        "name": "mlx-whisper",
        "platform": "macos",
        "accelerator": "mps",
        "model_version": "whisper-base"
      ])
    case "transcribe":
      result(FlutterError(
        code: "UNIMPLEMENTED",
        message: "macOS mlx-whisper transcription is not linked yet.",
        details: nil
      ))
    default:
      result(FlutterMethodNotImplemented)
    }
  }
}
