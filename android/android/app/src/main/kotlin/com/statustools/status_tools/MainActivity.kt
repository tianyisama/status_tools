package com.statustools.status_tools

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Environment
import android.os.StatFs
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

/**
 * Platform channel providing memory / storage / battery-temperature metrics
 * that need Android system APIs, plus a CPU fallback for devices where the
 * Dart side cannot read /proc (Java stream reads work where dart:io may not).
 * Channel: "statustools/metrics".
 */
class MainActivity : FlutterActivity() {

    private val channelName = "statustools/metrics"

    // Last successfully computed CPU percent, so a transient/blocked read
    // does not drop the display.
    private var lastGoodCpuPercent: Double? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "getCpuPercent" -> {
                        // Measure off the platform thread (sampling sleeps),
                        // then deliver the result back on the UI thread.
                        Thread {
                            val v = measureCpuPercent()
                            runOnUiThread { result.success(v) }
                        }.start()
                    }
                    "getMemoryInfo" -> result.success(readMemoryInfo())
                    "getStorageInfo" -> result.success(readStorageInfo())
                    "getBatteryTemp" -> result.success(readBatteryTemp())
                    else -> result.notImplemented()
                }
            }
    }

    /**
     * CPU usage, best-effort. Java streams read /proc to EOF (no fstat-size
     * issue), so this works on any device where /proc is readable at all.
     *
     * 1. Two-sample `/proc/stat` delta (accurate, ~250ms window).
     * 2. `/proc/loadavg` estimate (load1 / cores).
     * 3. `top -n 1` batch output.
     * 4. Otherwise the last known-good value (or null if never read).
     */
    private fun measureCpuPercent(): Double? {
        // Attempt 1: two-sample /proc/stat delta.
        val s1 = readProcStat()
        if (s1 != null) {
            try {
                Thread.sleep(250)
            } catch (_: InterruptedException) {
            }
            val s2 = readProcStat()
            if (s2 != null) {
                val dTotal = s2[0] - s1[0]
                val dIdle = s2[1] - s1[1]
                if (dTotal > 0) {
                    val pct = ((dTotal - dIdle).toDouble() / dTotal * 100.0).coerceIn(0.0, 100.0)
                    lastGoodCpuPercent = pct
                    return pct
                }
            }
        }

        // Attempt 2: /proc/loadavg estimate.
        try {
            val parts = File("/proc/loadavg").readText().trim().split(Regex("\\s+"))
            val load1 = parts[0].toDouble()
            val cores = Runtime.getRuntime().availableProcessors().coerceAtLeast(1)
            val pct = (load1 / cores * 100.0).coerceIn(0.0, 100.0)
            lastGoodCpuPercent = pct
            return pct
        } catch (_: Exception) {
        }

        // Attempt 3: `top -n 1` batch output.
        try {
            val proc = Runtime.getRuntime().exec(arrayOf("top", "-n", "1", "-b"))
            val out = proc.inputStream.bufferedReader().use { it.readText() }
            proc.waitFor()
            val totalMatch = Regex("(\\d+(?:\\.\\d+)?)%\\s*TOTAL").find(out)
            if (totalMatch != null) {
                val pct = totalMatch.groupValues[1].toDouble().coerceIn(0.0, 100.0)
                lastGoodCpuPercent = pct
                return pct
            }
        } catch (_: Exception) {
        }

        // Attempt 4: last known-good value.
        return lastGoodCpuPercent
    }

    /** Reads the aggregate cpu line of /proc/stat as [total, idle]; null if blocked. */
    private fun readProcStat(): LongArray? {
        return try {
            val line = File("/proc/stat").readLines().first()
            // "cpu  user nice system idle iowait irq softirq steal ..."
            val fields = line.split(Regex("\\s+")).drop(1).map { it.toLong() }
            val idle = fields.getOrElse(3) { 0L } + fields.getOrElse(4) { 0L } // idle + iowait
            longArrayOf(fields.sum(), idle)
        } catch (_: Exception) {
            null
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

    /** Battery temperature in degrees Celsius (BatteryManager reports tenths). */
    private fun readBatteryTemp(): Double {
        return try {
            val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            val status = registerReceiver(null, filter)
            val tenths = status?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1
            if (tenths > 0) tenths / 10.0 else 0.0
        } catch (e: Exception) {
            0.0
        }
    }
}
