package com.voicetextnote.app

import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * @MX:SPEC:REQ-MOBILE-011-03
 *
 * Android whisper.cpp + TFLite MethodChannel skeleton.
 *
 * @deprecated whisper_ggml_plus 패키지가 자체 네이티브 통합을 제공하므로
 *             이 플러그인은 더 이상 사용되지 않습니다. 제거 예정.
 */
@Deprecated("whisper_ggml_plus 패키지로 대체됨")
class WhisperSttPlugin : MethodChannel.MethodCallHandler {
    companion object {
        private const val CHANNEL = "com.voicetextnote/whisper_stt"

        fun registerWith(flutterEngine: FlutterEngine) {
            MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
                .setMethodCallHandler(WhisperSttPlugin())
        }
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "isAvailable" -> result.success(false)
            "getEngineInfo" -> result.success(
                mapOf(
                    "name" to "whisper.cpp",
                    "platform" to "android",
                    "accelerator" to "tflite",
                    "model_version" to "whisper-base",
                )
            )
            "transcribe" -> result.error(
                "UNIMPLEMENTED",
                "Android whisper.cpp TFLite transcription is not linked yet.",
                null,
            )
            else -> result.notImplemented()
        }
    }
}
