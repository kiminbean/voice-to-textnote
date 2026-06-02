// 백그라운드 녹음 서비스 (Android)
// @MX:ANCHOR: Android 포그라운드 서비스의 중앙 구현
// @MX:REASON: Foreground Service + 알림 표시로 백그라운드 녹음 지원

package com.voicetextnote.app

import android.app.*
import android.content.*
import android.os.*
import androidx.core.app.*
import kotlinx.coroutines.*

// 녹음 서비스
class RecordingService : Service() {

    private var serviceScope: CoroutineScope? = null
    private val CHANNEL_ID = "recording_channel"
    private val NOTIFICATION_ID = 1

    companion object {
        // Foreground Service 시작
        fun startForeground(context: Context) {
            val intent = Intent(context, RecordingService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        // Foreground Service 중지
        fun stopForeground(context: Context) {
            val intent = Intent(context, RecordingService::class.java)
            context.stopService(intent)
        }
    }

    override fun onCreate() {
        super.onCreate()
        serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Foreground Service 알림 표시
        startForeground(NOTIFICATION_ID, createNotification())
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        serviceScope?.cancel()
    }

    // 알림 채널 생성 (Android O+)
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "녹음 서비스",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "회의 녹음 중임을 표시하는 알림"
            }

            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    // 포그라운드 알림 생성
    private fun createNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("녹음 중")
            .setContentText("회의 녹음이 진행 중입니다...")
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
    }
}
