package com.voicetextnote.app

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity: FlutterActivity() {
    // Android 기본 설정 - Flutter 엔진 라이프사이클 관리

    private val CHANNEL = "com.voicetextnote.app/recording"
    private val SHARED_IMPORT_CHANNEL = "com.voicetextnote.app/shared_import"
    private var latestSharedImport: Map<String, String>? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

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
                        val ok = RecordingService.flushRecording()
                        result.success(ok)
                    }
                    else -> result.notImplemented()
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, SHARED_IMPORT_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "consumeInitialSharedImport" -> {
                        val payload = extractSharedImport(intent)
                        result.success(payload)
                    }
                    "consumeLatestSharedImport" -> {
                        val payload = latestSharedImport
                        latestSharedImport = null
                        result.success(payload)
                    }
                    else -> result.notImplemented()
                }
            }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        latestSharedImport = extractSharedImport(intent)
    }

    private fun extractSharedImport(intent: Intent?): Map<String, String>? {
        if (intent?.action != Intent.ACTION_SEND) return null
        val type = intent.type ?: return null
        if (!type.startsWith("text/")) return null

        val text = intent.getStringExtra(Intent.EXTRA_TEXT)?.trim().orEmpty()
        if (text.isEmpty()) return null

        val title = intent.getStringExtra(Intent.EXTRA_TITLE)?.trim().orEmpty()
        return buildMap {
            put("text", text)
            put("mimeType", type)
            if (title.isNotEmpty()) put("title", title)
        }
    }
}
