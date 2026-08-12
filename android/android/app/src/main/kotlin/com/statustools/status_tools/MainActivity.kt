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

/**
 * Platform channel providing memory / storage / battery-temperature metrics
 * that need Android system APIs. Channel: "statustools/metrics".
 *
 * CPU is read by the Dart side directly from `/proc/stat` (dart:io), so it is
 * not here.
 */
class MainActivity : FlutterActivity() {

    private val channelName = "statustools/metrics"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "getMemoryInfo" -> result.success(readMemoryInfo())
                    "getStorageInfo" -> result.success(readStorageInfo())
                    "getBatteryTemp" -> result.success(readBatteryTemp())
                    else -> result.notImplemented()
                }
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
