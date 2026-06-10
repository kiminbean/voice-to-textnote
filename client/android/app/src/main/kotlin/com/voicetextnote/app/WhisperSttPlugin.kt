package com.voicetextnote.app

import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * @MX:SPEC:REQ-MOBILE-011-03
 *
 * Android whisper.cpp + TFLite MethodChannel skeleton.
 */
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
