package com.example.eyedtrack.utils

import android.content.Context
import android.content.SharedPreferences
import android.media.AudioManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.util.*

/**
 * Manages voice alerts for driver behaviors with smart, non-intrusive alerting
 * Now respects system volume and user sound preferences
 */
class VoiceAlertManager(private val context: Context) {
    private var textToSpeech: TextToSpeech? = null
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
    private val sharedPreferences: SharedPreferences = context.getSharedPreferences("SoundSettings", Context.MODE_PRIVATE)
    
    private val alertCooldowns = mutableMapOf(
        "drowsy" to 0L,
        "yawning" to 0L,
        "distracted" to 0L
    )

    // Smart cooldown periods - reduced for more responsive alerts
    private val DROWSY_COOLDOWN = 10000L      // 10s - reduced from 15s for faster re-alerting
    private val YAWNING_COOLDOWN = 12000L     // 12s - reduced from 20s for better responsiveness
    private val DISTRACTED_COOLDOWN = 15000L  // 15s - reduced from 25s for better attention

    // Behavior counters for smart alerting
    private val behaviorCounters = mutableMapOf(
        "drowsy" to 0,
        "yawning" to 0,
        "distracted" to 0
    )
    private val behaviorLastSeen = mutableMapOf(
        "drowsy" to 0L,
        "yawning" to 0L,
        "distracted" to 0L
    )

    // Reduced thresholds for more sensitive voice alerts
    private val ALERT_THRESHOLDS = mapOf(
        "drowsy" to 1,      // REDUCED: Alert after 1 detection (more sensitive)
        "yawning" to 2,     // REDUCED: Alert after 2 detections (more sensitive)
        "distracted" to 1   // REDUCED: Alert after 1 detection (more sensitive)
    )

    private val TAG = "VoiceAlertManager"
    private var isTtsReady = false

    init {
        setupTTS()
        setupAudio()
    }

    private fun setupTTS() {
        textToSpeech = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val result = textToSpeech?.setLanguage(Locale.US)
                if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                    Log.e(TAG, "Language not supported")
                } else {
                    // Configure TTS settings
                    textToSpeech?.apply {
                        setSpeechRate(1.0f)
                        setPitch(1.0f)
                        setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                            override fun onStart(utteranceId: String) {
                                Log.d(TAG, "Started speaking: $utteranceId")
                            }

                            override fun onDone(utteranceId: String) {
                                Log.d(TAG, "Finished speaking: $utteranceId")
                            }

                            override fun onError(utteranceId: String) {
                                Log.e(TAG, "Error speaking: $utteranceId")
                            }
                        })
                    }
                    isTtsReady = true
                    Log.d(TAG, "TextToSpeech initialized successfully")
                }
            } else {
                Log.e(TAG, "TextToSpeech initialization failed with status: $status")
            }
        }
    }

    private fun setupAudio() {
        try {
            // Check if we should use system volume
            val useSystemVolume = sharedPreferences.getBoolean("use_system_volume", true)
            
            if (useSystemVolume) {
                // Respect system volume - don't override it
                val currentVolume = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
                val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                Log.d(TAG, "Using system volume: $currentVolume/$maxVolume")
                
                // Use normal mode to respect system settings like Do Not Disturb
                audioManager.mode = AudioManager.MODE_NORMAL
            } else {
                // Use custom volume setting
                val customVolume = sharedPreferences.getInt("custom_volume", 50)
                val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                val targetVolume = ((customVolume / 100.0f) * maxVolume).toInt()
                
                audioManager.setStreamVolume(
                    AudioManager.STREAM_MUSIC,
                    targetVolume,
                    0
                )
                Log.d(TAG, "Using custom volume: $targetVolume/$maxVolume (${customVolume}%)")
            }

            Log.d(TAG, "Audio setup complete")
        } catch (e: Exception) {
            Log.e(TAG, "Error setting up audio: ${e.message}")
        }
    }

    fun processAlerts(isDrowsy: Boolean, isYawning: Boolean, isDistracted: Boolean) {
        Log.d(TAG, "processAlerts called: isDrowsy=$isDrowsy, isYawning=$isYawning, isDistracted=$isDistracted")

        if (!isTtsReady) {
            Log.w(TAG, "TextToSpeech not ready yet")
            return
        }

        val currentTime = System.currentTimeMillis()
        val params = HashMap<String, String>()

        // Process each behavior with smart alerting
        processBehavior("drowsy", isDrowsy, currentTime, params) {
            triggerAlert("Warning! Drowsiness detected! Please stay alert and consider taking a break.", TextToSpeech.QUEUE_FLUSH, params)
        }

        processBehavior("yawning", isYawning, currentTime, params) {
            triggerAlert("Warning! Yawning detected. You may be getting tired. Consider taking a rest.", TextToSpeech.QUEUE_ADD, params)
        }

        processBehavior("distracted", isDistracted, currentTime, params) {
            triggerAlert("Warning! Distraction detected. Please focus on the road ahead.", TextToSpeech.QUEUE_ADD, params)
        }

        if (!isDrowsy && !isYawning && !isDistracted) {
            Log.d(TAG, "No behaviors detected - no alerts needed")
        }
    }

    /**
     * Smart behavior processing with CONSECUTIVE detection requirement
     */
    private fun processBehavior(
        behaviorType: String,
        isDetected: Boolean,
        currentTime: Long,
        params: HashMap<String, String>,
        alertAction: () -> Unit
    ) {
        if (isDetected) {
            // Update behavior tracking
            behaviorLastSeen[behaviorType] = currentTime
            behaviorCounters[behaviorType] = (behaviorCounters[behaviorType] ?: 0) + 1

            val count = behaviorCounters[behaviorType] ?: 0
            val threshold = ALERT_THRESHOLDS[behaviorType] ?: 5

            Log.d(TAG, "$behaviorType detected: consecutive count=$count, threshold=$threshold")

            // Check if we should alert
            if (count >= threshold && canAlert(behaviorType, currentTime)) {
                Log.w(TAG, "🚨 TRIGGERING $behaviorType ALERT (consecutive count: $count)")
                alertAction()
                alertCooldowns[behaviorType] = currentTime
                behaviorCounters[behaviorType] = 0 // Reset counter after alert
            } else if (count >= threshold) {
                Log.d(TAG, "$behaviorType consecutive threshold reached but in cooldown period")
            } else {
                Log.d(TAG, "$behaviorType detected but below consecutive threshold ($count/$threshold)")
            }
        } else {
            // IMMEDIATELY reset counter when behavior is NOT detected (consecutive requirement)
            if ((behaviorCounters[behaviorType] ?: 0) > 0) {
                Log.d(TAG, "Resetting $behaviorType counter - behavior not detected (consecutive requirement)")
                behaviorCounters[behaviorType] = 0
            }
        }
    }

    private fun canAlert(type: String, currentTime: Long): Boolean {
        val lastAlert = alertCooldowns[type] ?: 0L
        val cooldownPeriod = when (type) {
            "drowsy" -> DROWSY_COOLDOWN
            "yawning" -> YAWNING_COOLDOWN
            "distracted" -> DISTRACTED_COOLDOWN
            else -> DROWSY_COOLDOWN // Default to most restrictive
        }
        return (currentTime - lastAlert) >= cooldownPeriod
    }

    private fun triggerAlert(text: String, queueMode: Int, params: HashMap<String, String>) {
        // Check if vibration is enabled
        val vibrateEnabled = sharedPreferences.getBoolean("vibrate_enabled", true)
        
        // Trigger vibration if enabled
        if (vibrateEnabled && vibrator.hasVibrator()) {
            try {
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                    vibrator.vibrate(VibrationEffect.createOneShot(500, VibrationEffect.DEFAULT_AMPLITUDE))
                } else {
                    @Suppress("DEPRECATION")
                    vibrator.vibrate(500)
                }
                Log.d(TAG, "Vibration triggered")
            } catch (e: Exception) {
                Log.e(TAG, "Error triggering vibration: ${e.message}")
            }
        }
        
        // Trigger voice alert
        speak(text, queueMode, params)
    }

    private fun speak(text: String, queueMode: Int, params: HashMap<String, String>) {
        try {
            // Refresh audio setup to respect current settings
            setupAudio()
            
            val utteranceId = "Alert_${System.currentTimeMillis()}"
            params[TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID] = utteranceId
            textToSpeech?.speak(text, queueMode, params)
            Log.d(TAG, "Speaking: $text, UtteranceId: $utteranceId")
        } catch (e: Exception) {
            Log.e(TAG, "Error speaking: ${e.message}")
        }
    }

    fun resetCounters() {
        Log.d(TAG, "🔄 Resetting all behavior counters and cooldowns")
        behaviorCounters.clear()
        behaviorLastSeen.clear()
        alertCooldowns.clear()

        // Also stop any ongoing TTS
        try {
            textToSpeech?.stop()
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping TTS during reset: ${e.message}")
        }
    }

    fun shutdown() {
        try {
            textToSpeech?.stop()
            textToSpeech?.shutdown()
            // Restore normal audio mode
            audioManager.mode = AudioManager.MODE_NORMAL
        } catch (e: Exception) {
            Log.e(TAG, "Error shutting down TTS: ${e.message}")
        }
    }
}