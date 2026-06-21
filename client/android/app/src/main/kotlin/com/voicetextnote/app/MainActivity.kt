package com.voicetextnote.app

import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

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

        val stream = intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
        if (stream != null && isSupportedSharedFile(type)) {
            return copySharedFile(stream, type)
        }

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

    private fun isSupportedSharedFile(type: String): Boolean {
        return type == "application/pdf" ||
            type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
            type.startsWith("image/")
    }

    private fun copySharedFile(uri: Uri, mimeType: String): Map<String, String>? {
        val originalName = displayName(uri) ?: "shared-import.${extensionForMimeType(mimeType)}"
        val safeName = originalName.replace(Regex("[^A-Za-z0-9가-힣._-]"), "_")
        val targetDir = File(cacheDir, "shared-imports").apply { mkdirs() }
        val target = File(targetDir, "${System.currentTimeMillis()}-$safeName")

        return try {
            contentResolver.openInputStream(uri)?.use { input ->
                target.outputStream().use { output -> input.copyTo(output) }
            } ?: return null
            buildMap {
                put("filePath", target.absolutePath)
                put("fileName", originalName)
                put("mimeType", mimeType)
                put("title", originalName.substringBeforeLast('.', originalName))
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun displayName(uri: Uri): String? {
        contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (index >= 0 && cursor.moveToFirst()) {
                return cursor.getString(index)
            }
        }
        return uri.lastPathSegment?.substringAfterLast('/')
    }

    private fun extensionForMimeType(mimeType: String): String {
        return when (mimeType) {
            "application/pdf" -> "pdf"
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document" -> "docx"
            "image/png" -> "png"
            "image/webp" -> "webp"
            "image/heic", "image/heif" -> "heic"
            else -> if (mimeType.startsWith("image/")) "jpg" else "bin"
        }
    }
}
