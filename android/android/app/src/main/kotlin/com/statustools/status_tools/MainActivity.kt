package com.statustools.status_tools

import android.app.ActivityManager
import android.content.Context
import android.os.Environment
import android.os.StatFs
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

/**
 * Platform channel providing CPU / memory / storage metrics that Dart cannot read
 * directly. Channel: "statustools/metrics".
 *
 * CPU uses a snapshot-delta approach: each call compares the current /proc/stat
 * against the previous snapshot, so the sampling window is the time between calls
 * (no blocking sleep on the platform thread).
 */
class MainActivity : FlutterActivity() {

    private val channelName = "statustools/metrics"

    // Previous /proc/stat snapshot as [total, idle].
    private var lastCpu: LongArray? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "getCpuPercent" -> result.success(readCpuPercent())
                    "getMemoryInfo" -> result.success(readMemoryInfo())
                    "getStorageInfo" -> result.success(readStorageInfo())
                    else -> result.notImplemented()
                }
            }
    }

    private fun readCpuPercent(): Double {
        return try {
            val line = File("/proc/stat").readLines().first()
            // "cpu  user nice system idle iowait irq softirq steal ..."
            val fields = line.split(Regex("\\s+")).drop(1).map { it.toLong() }
            val idle = fields.getOrElse(3) { 0L } + fields.getOrElse(4) { 0L } // idle + iowait
            val total = fields.sum()

            val prev = lastCpu
            lastCpu = longArrayOf(total, idle)

            if (prev == null) {
                0.0 // First sample has no baseline yet.
            } else {
                val dTotal = total - prev[0]
                val dIdle = idle - prev[1]
                if (dTotal <= 0) 0.0
                else ((dTotal - dIdle).toDouble() / dTotal * 100.0).coerceIn(0.0, 100.0)
            }
        } catch (e: Exception) {
            0.0
        }
    }

    private fun readMemoryInfo(): Map<String, Any> {
        return try {
            val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val mi = ActivityManager.MemoryInfo()
            am.getMemoryInfo(mi)
            val total = mi.totalMem.toDouble()
            val avail = mi.availMem.toDouble()
            val used = total - avail
            mapOf(
                "percent" to if (total > 0) used / total * 100.0 else 0.0,
                "usedMb" to (used / 1_048_576L).toLong(),
                "totalMb" to (total / 1_048_576L).toLong()
            )
        } catch (e: Exception) {
            mapOf("percent" to 0.0, "usedMb" to 0L, "totalMb" to 0L)
        }
    }

    private fun readStorageInfo(): Map<String, Any> {
        return try {
            val stat = StatFs(Environment.getDataDirectory().path)
            val total = stat.totalBytes.toDouble()
            val free = stat.availableBytes.toDouble()
            val used = total - free
            mapOf(
                "percent" to if (total > 0) used / total * 100.0 else 0.0,
                "usedGb" to used / 1_073_741_824.0,
                "totalGb" to total / 1_073_741_824.0
            )
        } catch (e: Exception) {
            mapOf("percent" to 0.0, "usedGb" to 0.0, "totalGb" to 0.0)
        }
    }
}
