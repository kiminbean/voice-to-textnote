package com.voicetextnote.app

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity: FlutterActivity() {
    // Android 기본 설정 - Flutter 엔진 라이프사이클 관리

    private val CHANNEL = "com.voicetextnote.app/recording"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        WhisperSttPlugin.registerWith(flutterEngine)

        // MethodChannel 핸들러 등록
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "startForegroundService" -> {
                        RecordingService.startForeground(this)
                        result.success(null)
                    }
                    "stopForegroundService" -> {
                        RecordingService.stopForeground(this)
                        result.success(null)
                    }
                    "flushRecording" -> {
                        // 주기적 플러시 (녹음 파일 갱신)
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
    }
}
