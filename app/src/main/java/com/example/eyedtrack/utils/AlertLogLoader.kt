package com.example.eyedtrack.utils

import android.content.Context
import android.os.Environment
import android.util.Log
import com.example.eyedtrack.model.AlertHistoryItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
import java.io.FileInputStream
import java.io.InputStreamReader
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Utility class to load and parse alert logs from driver monitoring logs
 */
class AlertLogLoader(private val context: Context) {
    private val TAG = "AlertLogLoader"
    private val ALERT_LOG_DIR = "driver_monitoring_logs"
    private val ALERT_LOG_FILE = "driver_monitoring.json"

    /**
     * Find the most recent log file in various possible locations
     * @return The most recent log file, or null if none found
     */
    private fun getMostRecentLogFile(): File? {
        try {
            val possibleLocations = listOf(
                // External storage locations (accessible by both backend and app)
                File(Environment.getExternalStorageDirectory(), "Download/$ALERT_LOG_FILE"),
                File(Environment.getExternalStorageDirectory(), "Documents/$ALERT_LOG_FILE"),
                File(Environment.getExternalStorageDirectory(), ALERT_LOG_FILE),
                File(Environment.getExternalStorageDirectory(), "EyeDTrack/$ALERT_LOG_FILE"),
                File(Environment.getExternalStorageDirectory(), "$ALERT_LOG_DIR/$ALERT_LOG_FILE"),
                
                // App's external files directory
                File(context.getExternalFilesDir(null), ALERT_LOG_FILE),
                File(context.getExternalFilesDir(null), "$ALERT_LOG_DIR/$ALERT_LOG_FILE"),
                File(context.getExternalFilesDir("logs"), ALERT_LOG_FILE),
                
                // App's internal files directory
                File(context.filesDir, ALERT_LOG_FILE),
                File(context.filesDir, "$ALERT_LOG_DIR/$ALERT_LOG_FILE"),
                
                // SD Card locations
                File("/sdcard/$ALERT_LOG_FILE"),
                File("/sdcard/Download/$ALERT_LOG_FILE"),
                File("/sdcard/Documents/$ALERT_LOG_FILE"),
                File("/sdcard/EyeDTrack/$ALERT_LOG_FILE"),
                File("/sdcard/$ALERT_LOG_DIR/$ALERT_LOG_FILE")
            )

            for (location in possibleLocations) {
                if (location.exists() && location.canRead() && location.length() > 0) {
                    Log.d(TAG, "Found readable log file: ${location.absolutePath} (${location.length()} bytes)")
                    return location
                } else {
                    Log.d(TAG, "Checked location: ${location.absolutePath} - exists: ${location.exists()}, readable: ${location.canRead()}, size: ${if(location.exists()) location.length() else "N/A"}")
                }
            }

            Log.w(TAG, "No readable log file found in any location")
            return null

        } catch (e: Exception) {
            Log.e(TAG, "Error finding log file: ${e.message}")
            e.printStackTrace()
            return null
        }
    }

    /**
     * Read driver_monitoring.json from assets folder
     */
    private fun readFromAssets(): String? {
        try {
            val assetManager = context.assets
            val inputStream = assetManager.open(ALERT_LOG_FILE)
            val content = inputStream.bufferedReader().use { it.readText() }
            inputStream.close()
            Log.d(TAG, "Successfully read ${content.length} characters from assets")
            return content
        } catch (e: Exception) {
            Log.w(TAG, "Could not read from assets: ${e.message}")
            return null
        }
    }

    /**
     * Parse a log file and add alerts to the provided list
     */
    private fun parseLogFile(file: File, alertItems: MutableList<AlertHistoryItem>) {
        try {
            val content = file.readText()
            parseLogContent(content, alertItems)
        } catch (e: Exception) {
            Log.e(TAG, "Error reading log file: ${e.message}")
        }
    }

    /**
     * Parse log content and extract alert items
     */
    private fun parseLogContent(content: String, alertItems: MutableList<AlertHistoryItem>) {
        if (content.isBlank()) {
            Log.w(TAG, "Log content is empty")
            return
        }

        var parsedCount = 0
        var riskyBehaviorCount = 0

        // Split by newlines as each line should be a JSON object
        content.split("\n").forEach { line ->
            if (line.isNotBlank() && line.trim().startsWith("{")) {
                try {
                    val json = JSONObject(line.trim())
                    parsedCount++

                    // Check if this entry has risky behavior
                    val behaviorOutput = json.optString("behavior_output", "")
                    if (behaviorOutput != "RISKY BEHAVIOR DETECTED") {
                        // Skip non-risky behaviors
                        return@forEach
                    }

                    riskyBehaviorCount++

                    val timestamp = json.getString("timestamp")
                    val dateTime = timestamp.split("T")
                    val date = dateTime[0]
                    val time = dateTime[1].split(".")[0]

                    val behaviorCategory = json.getJSONObject("behavior_category")
                    val isDrowsy = behaviorCategory.optBoolean("is_drowsy", false)
                    val isYawning = behaviorCategory.optBoolean("is_yawning", false)
                    val isDistracted = behaviorCategory.optBoolean("is_distracted", false)

                    // Determine primary alert type (prioritize multiple behaviors)
                    val alertType = when {
                        isDrowsy && isYawning && isDistracted -> "Multiple Behaviors"
                        isDrowsy && isYawning -> "Drowsy & Yawning"
                        isDrowsy && isDistracted -> "Drowsy & Distracted"
                        isYawning && isDistracted -> "Yawning & Distracted"
                        isDrowsy -> "Drowsiness"
                        isYawning -> "Yawning"
                        isDistracted -> "Distraction"
                        else -> "Unknown Risk"
                    }

                    val reason = when {
                        isDrowsy && isYawning && isDistracted -> "Driver shows multiple risky behaviors"
                        isDrowsy && isYawning -> "Driver is drowsy and yawning"
                        isDrowsy && isDistracted -> "Driver is drowsy and distracted"
                        isYawning && isDistracted -> "Driver is yawning and distracted"
                        isDrowsy -> "Driver shows signs of drowsiness"
                        isYawning -> "Driver is yawning"
                        isDistracted -> "Driver is distracted"
                        else -> "Risky behavior detected"
                    }

                    val confidence = json.optDouble("behavior_confidence", 0.0)
                    val confidencePercentage = (confidence * 100).toInt()

                    // Extract additional metrics for detailed view
                    val mar = json.optDouble("mar", 0.0)
                    val ear = json.optDouble("ear", 0.0)
                    val pitch = json.optDouble("pitch", 0.0)
                    val yaw = json.optDouble("yaw", 0.0)
                    val roll = json.optDouble("roll", 0.0)

                    val detailedInfo = "MAR: %.3f, EAR: %.3f, Pitch: %.1f°, Yaw: %.1f°, Roll: %.1f°".format(
                        mar, ear, pitch, yaw, roll
                    )

                    alertItems.add(AlertHistoryItem(
                        date = date,
                        time = time,
                        alertType = alertType,
                        confidence = confidencePercentage,
                        reason = "$reason ($detailedInfo)",
                        behaviorOutput = behaviorOutput
                    ))
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing JSON line: ${e.message}")
                    Log.d(TAG, "Problematic line: $line")
                }
            }
        }

        Log.d(TAG, "Parsed $parsedCount total entries, found $riskyBehaviorCount risky behaviors")
    }

    /**
     * Load alert logs from the driver monitoring logs
     */
    suspend fun loadAlertLogs(maxLogs: Int = 50): List<AlertHistoryItem> = withContext(Dispatchers.IO) {
        val alertItems = mutableListOf<AlertHistoryItem>()

        try {
            Log.d(TAG, "Starting to load alert logs (max: $maxLogs)")
            
            // Priority 1: Try to read from API endpoint first (live data from backend)
            val apiAlerts = loadAlertsFromAPI(maxLogs)
            if (apiAlerts.isNotEmpty()) {
                Log.d(TAG, "Successfully loaded ${apiAlerts.size} alerts from API")
                return@withContext apiAlerts
            }
            
            // Priority 2: Try to read from live file system locations (where backend might write locally)
            val logFile = getMostRecentLogFile()
            if (logFile != null) {
                Log.d(TAG, "Reading from live file: ${logFile.absolutePath}")
                parseLogFile(logFile, alertItems)
                
                if (alertItems.isNotEmpty()) {
                    Log.d(TAG, "Successfully loaded ${alertItems.size} alerts from live file")
                    // Sort by date and time (most recent first)
                    alertItems.sortByDescending { "${it.date}T${it.time}" }
                    return@withContext alertItems.take(maxLogs)
                }
            }

            // Priority 3: If no live data found, fall back to assets folder
            val assetsContent = readFromAssets()
            if (assetsContent != null) {
                Log.d(TAG, "No live data found, reading from assets folder as fallback")
                parseLogContent(assetsContent, alertItems)
                
                if (alertItems.isNotEmpty()) {
                    Log.d(TAG, "Successfully loaded ${alertItems.size} alerts from assets")
                    // Sort by date and time (most recent first)
                    alertItems.sortByDescending { "${it.date}T${it.time}" }
                    return@withContext alertItems.take(maxLogs)
                }
            }

            // Priority 4: If still no data, use sample data
            if (alertItems.isEmpty()) {
                Log.w(TAG, "No alerts found in any location, using sample data")
                alertItems.addAll(createSampleAlerts())
            }

            // Sort by date and time (most recent first)
            alertItems.sortByDescending { "${it.date}T${it.time}" }

            Log.d(TAG, "Returning ${alertItems.size} alert items (limited to $maxLogs)")
            return@withContext alertItems.take(maxLogs)
        } catch (e: Exception) {
            Log.e(TAG, "Error loading alert logs: ${e.message}")
            e.printStackTrace()
            return@withContext createSampleAlerts().take(maxLogs)
        }
    }

    /**
     * Load alerts from the backend API endpoint
     */
    private suspend fun loadAlertsFromAPI(maxLogs: Int = 50): List<AlertHistoryItem> = withContext(Dispatchers.IO) {
        // Try multiple endpoints in order of preference
        val endpoints = listOf(
            "http://192.168.68.110:5000/api/alert_history?limit=$maxLogs",
            "http://127.0.0.1:5000/api/alert_history?limit=$maxLogs",  // Android emulator host
        )
        
        for ((index, endpoint) in endpoints.withIndex()) {
            try {
                Log.d(TAG, "Attempting to load alerts from API endpoint ${index + 1}/${endpoints.size}: $endpoint")
                
                val url = java.net.URL(endpoint)
                val connection = url.openConnection() as java.net.HttpURLConnection

                // Configure connection
                connection.requestMethod = "GET"
                connection.connectTimeout = 5000  // Reduced timeout for faster fallback
                connection.readTimeout = 5000
                connection.setRequestProperty("Accept", "application/json")
                connection.setRequestProperty("User-Agent", "EyeDTrack-Android/1.0")

                Log.d(TAG, "Connecting to alert history API: $url")

                // Connect and get response
                connection.connect()
                val responseCode = connection.responseCode
                Log.d(TAG, "API Response code: $responseCode")

                if (responseCode == 200) {
                    val response = connection.inputStream.bufferedReader().use { it.readText() }
                    Log.d(TAG, "API Response received: ${response.length} characters")

                    val json = JSONObject(response)
                    val success = json.optBoolean("success", false)

                    if (success) {
                        val alertsArray = json.getJSONArray("alerts")
                        val totalCount = json.optInt("total_count", 0)
                        val returnedCount = json.optInt("returned_count", 0)
                        val latestTimestamp = json.optString("latest_timestamp", "Unknown")
                        val apiTimestamp = json.optString("api_timestamp", "Unknown")
                        
                        Log.d(TAG, "📊 API returned $returnedCount alerts out of $totalCount total from $endpoint")
                        Log.d(TAG, "🕐 Latest alert in data: $latestTimestamp")
                        Log.d(TAG, "⏰ API response time: $apiTimestamp") 
                        
                        val alertItems = mutableListOf<AlertHistoryItem>()
                        
                        for (i in 0 until alertsArray.length()) {
                            try {
                                val alertJson = alertsArray.getJSONObject(i)
                                val alertItem = parseJSONToAlertItem(alertJson)
                                if (alertItem != null) {
                                    alertItems.add(alertItem)
                                }
                            } catch (e: Exception) {
                                Log.w(TAG, "Error parsing alert item $i: ${e.message}")
                            }
                        }
                        
                        connection.disconnect()
                        Log.i(TAG, "✅ Successfully loaded ${alertItems.size} FRESH alerts from API: $endpoint")
                        
                        // Log the latest timestamp for verification
                        if (alertItems.isNotEmpty()) {
                            val latestAlert = alertItems.first()
                            Log.i(TAG, "🔥 Latest alert in processed data: ${latestAlert.date}T${latestAlert.time} - ${latestAlert.alertType}")
                        }
                        
                        return@withContext alertItems
                    } else {
                        val error = json.optString("error", "Unknown error")
                        Log.w(TAG, "API returned success=false: $error")
                    }
                } else {
                    Log.w(TAG, "API returned error code: $responseCode")
                    try {
                        val errorResponse = connection.errorStream?.bufferedReader()?.use { it.readText() }
                        Log.w(TAG, "Error response: $errorResponse")
                    } catch (e: Exception) {
                        Log.w(TAG, "Could not read error response: ${e.message}")
                    }
                }

                connection.disconnect()

            } catch (e: java.net.SocketTimeoutException) {
                Log.e(TAG, "✗ API connection timed out for $endpoint: ${e.message}")
            } catch (e: java.net.ConnectException) {
                Log.e(TAG, "✗ Could not connect to API $endpoint: ${e.message}")
            } catch (e: java.net.UnknownHostException) {
                Log.e(TAG, "✗ Unknown host $endpoint: ${e.message}")
            } catch (e: Exception) {
                Log.e(TAG, "✗ Error calling alert history API $endpoint: ${e.message}")
                e.printStackTrace()
            }
            
            // Small delay before trying next endpoint
            if (index < endpoints.size - 1) {
                Log.d(TAG, "Trying next endpoint...")
                kotlinx.coroutines.delay(100)
            }
        }

        Log.w(TAG, "All API endpoints failed, returning empty list")
        return@withContext emptyList()
    }

    /**
     * Parse a JSON object from API response to AlertHistoryItem
     */
    private fun parseJSONToAlertItem(json: JSONObject): AlertHistoryItem? {
        try {
            val timestamp = json.getString("timestamp")
            val dateTime = timestamp.split("T")
            val date = dateTime[0]
            val time = dateTime[1].split(".")[0]

            val behaviorCategory = json.getJSONObject("behavior_category")
            val isDrowsy = behaviorCategory.optBoolean("is_drowsy", false)
            val isYawning = behaviorCategory.optBoolean("is_yawning", false)
            val isDistracted = behaviorCategory.optBoolean("is_distracted", false)

            // Determine primary alert type (prioritize multiple behaviors)
            val alertType = when {
                isDrowsy && isYawning && isDistracted -> "Multiple Behaviors"
                isDrowsy && isYawning -> "Drowsy & Yawning"
                isDrowsy && isDistracted -> "Drowsy & Distracted"
                isYawning && isDistracted -> "Yawning & Distracted"
                isDrowsy -> "Drowsiness"
                isYawning -> "Yawning"
                isDistracted -> "Distraction"
                else -> "Unknown Risk"
            }

            val reason = when {
                isDrowsy && isYawning && isDistracted -> "Driver shows multiple risky behaviors"
                isDrowsy && isYawning -> "Driver is drowsy and yawning"
                isDrowsy && isDistracted -> "Driver is drowsy and distracted"
                isYawning && isDistracted -> "Driver is yawning and distracted"
                isDrowsy -> "Driver shows signs of drowsiness"
                isYawning -> "Driver is yawning"
                isDistracted -> "Driver is distracted"
                else -> "Risky behavior detected"
            }

            val confidence = json.optDouble("behavior_confidence", 0.0)
            val confidencePercentage = (confidence * 100).toInt()

            // Extract additional metrics for detailed view
            val mar = json.optDouble("mar", 0.0)
            val ear = json.optDouble("ear", 0.0)
            val pitch = json.optDouble("pitch", 0.0)
            val yaw = json.optDouble("yaw", 0.0)
            val roll = json.optDouble("roll", 0.0)

            val detailedInfo = "MAR: %.3f, EAR: %.3f, Pitch: %.1f°, Yaw: %.1f°, Roll: %.1f°".format(
                mar, ear, pitch, yaw, roll
            )

            return AlertHistoryItem(
                date = date,
                time = time,
                alertType = alertType,
                confidence = confidencePercentage,
                reason = "$reason ($detailedInfo)",
                behaviorOutput = json.optString("behavior_output", "")
            )
        } catch (e: Exception) {
            Log.e(TAG, "Error parsing JSON to AlertHistoryItem: ${e.message}")
            return null
        }
    }

    /**
     * Create sample alerts for testing or when no logs are available
     */
    private fun createSampleAlerts(): List<AlertHistoryItem> {
        val sampleEntries = listOf(
            """{"timestamp": "2025-06-02T23:47:17.888789", "behavior_category": {"is_drowsy": false, "is_yawning": false, "is_distracted": true}, "behavior_output": "RISKY BEHAVIOR DETECTED", "mar": 0.5694, "ear": 1.0625, "pitch": 0.0, "yaw": 0.0, "roll": 0.0, "behavior_confidence": 0.7316}""",
            """{"timestamp": "2025-06-02T23:47:40.483343", "behavior_category": {"is_drowsy": false, "is_yawning": true, "is_distracted": false}, "behavior_output": "RISKY BEHAVIOR DETECTED", "mar": 0.6305, "ear": 0.9623, "pitch": 87.028, "yaw": -33.4991, "roll": 102.9791, "behavior_confidence": 0.9244}""",
            """{"timestamp": "2025-06-02T23:58:52.649196", "behavior_category": {"is_drowsy": true, "is_yawning": false, "is_distracted": false}, "behavior_output": "RISKY BEHAVIOR DETECTED", "mar": 0.6864, "ear": 0.8352, "pitch": 6.3078, "yaw": -1.5945, "roll": 6.6499, "behavior_confidence": 0.7217}"""
        )

        val alertItems = mutableListOf<AlertHistoryItem>()
        sampleEntries.forEach { entry ->
            parseLogContent(entry, alertItems)
        }

        Log.d(TAG, "Created ${alertItems.size} sample alerts")
        return alertItems
    }

    /**
     * Reads the latest behavior flags (isDrowsy, isYawning, isDistracted) from the backend API.
     * @return Triple<Boolean, Boolean, Boolean> representing (isDrowsy, isYawning, isDistracted)
     */
    fun readLatestBehaviorFlags(): Triple<Boolean, Boolean, Boolean> {
        // Try multiple endpoints in order of preference
        val endpoints = listOf(
            "http://127.0.0.1:5000/api/latest_behavior",
            "http://localhost:5000/api/latest_behavior", 
            "http://10.0.2.2:5000/api/latest_behavior",  // Android emulator host
            "http://192.168.68.110:5000/api/latest_behavior"  // Original IP
        )
        
        for ((index, endpoint) in endpoints.withIndex()) {
            try {
                Log.d(TAG, "Attempting to connect to BEHAVIOR API endpoint ${index + 1}/${endpoints.size}: $endpoint")
                
                val url = java.net.URL(endpoint)
                val connection = url.openConnection() as java.net.HttpURLConnection

                // Configure connection
                connection.requestMethod = "GET"
                connection.connectTimeout = 3000  // Reduced timeout for faster fallback
                connection.readTimeout = 3000
                connection.setRequestProperty("Accept", "application/json")
                connection.setRequestProperty("User-Agent", "EyeDTrack-Android/1.0")

                // Log connection attempt
                Log.d(TAG, "Connecting to BEHAVIOR endpoint: $url")

                // Connect and get response
                connection.connect()
                val responseCode = connection.responseCode
                Log.d(TAG, "Response code: $responseCode")

                if (responseCode == 200) {
                    val response = connection.inputStream.bufferedReader().use { it.readText() }
                    Log.d(TAG, "Raw behavior API response from $endpoint: $response")

                    val json = JSONObject(response)

                    // Check if response is successful
                    val success = json.optBoolean("success", false)
                    Log.d(TAG, "Behavior API success status: $success")

                    if (success) {
                        // Extract behavior flags from the response
                        val behaviorCategory = json.getJSONObject("behavior_category")
                        val isDrowsy = behaviorCategory.optBoolean("is_drowsy", false)
                        val isYawning = behaviorCategory.optBoolean("is_yawning", false)
                        val isDistracted = behaviorCategory.optBoolean("is_distracted", false)

                        Log.i(TAG, "✅ BEHAVIOR API from $endpoint: isDrowsy=$isDrowsy, isYawning=$isYawning, isDistracted=$isDistracted")

                        // Only log if any behavior is detected to reduce noise
                        if (isDrowsy || isYawning || isDistracted) {
                            Log.w(TAG, "⚠️ RISKY BEHAVIOR DETECTED! This should trigger voice alert!")
                        }

                        connection.disconnect()
                        return Triple(isDrowsy, isYawning, isDistracted)
                    } else {
                        val error = json.optString("error", "Unknown error")
                        Log.w(TAG, "API returned success=false: $error")
                    }
                } else {
                    Log.w(TAG, "API returned error code: $responseCode for $endpoint")
                    try {
                        val errorResponse = connection.errorStream?.bufferedReader()?.use { it.readText() }
                        Log.w(TAG, "Error response: $errorResponse")
                    } catch (e: Exception) {
                        Log.w(TAG, "Could not read error response: ${e.message}")
                    }
                }

                connection.disconnect()

            } catch (e: java.net.SocketTimeoutException) {
                Log.e(TAG, "✗ Behavior API connection timed out for $endpoint: ${e.message}")
            } catch (e: java.net.ConnectException) {
                Log.e(TAG, "✗ Could not connect to Behavior API $endpoint: ${e.message}")
            } catch (e: java.net.UnknownHostException) {
                Log.e(TAG, "✗ Unknown host for Behavior API $endpoint: ${e.message}")
            } catch (e: Exception) {
                Log.e(TAG, "✗ Error calling Behavior API $endpoint: ${e.message}")
                e.printStackTrace()
            }
            
            // Small delay before trying next endpoint
            if (index < endpoints.size - 1) {
                Log.d(TAG, "Trying next behavior API endpoint...")
                Thread.sleep(50) // Use Thread.sleep instead of coroutine delay since this isn't a suspend function
            }
        }

        // If all API endpoints fail, don't fall back to file reading since Android can't access backend files
        Log.w(TAG, "All behavior API endpoints failed, returning false for all behaviors")
        return Triple(false, false, false)
    }
}