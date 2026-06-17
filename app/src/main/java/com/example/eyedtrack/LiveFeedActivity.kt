package com.example.eyedtrack

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.WindowManager
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.example.eyedtrack.api.ApiClient
import com.example.eyedtrack.camera.CameraService
import com.example.eyedtrack.databinding.LiveFeedBinding
import com.example.eyedtrack.viewmodel.CameraViewModel
import com.example.eyedtrack.viewmodel.ProcessingState
import kotlinx.coroutines.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import android.view.View
import com.example.eyedtrack.utils.AlertLogLoader
import com.example.eyedtrack.utils.VoiceAlertManager
import org.json.JSONObject
import android.widget.Button


// Activity for displaying a live camera feed and monitoring status.
class LiveFeedActivity : AppCompatActivity() {

    private lateinit var binding: LiveFeedBinding
    private lateinit var cameraService: CameraService
    private val viewModel: CameraViewModel by viewModels()

    private var isConnected = false
    private var isMonitoring = false
    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private var isActivityValid = true
    private var connectionJob: Job? = null  // Add this to track connection attempts
    private lateinit var voiceAlertManager: VoiceAlertManager
    private lateinit var alertLogLoader: AlertLogLoader
    private val handler = Handler(Looper.getMainLooper())
    private val CHECK_INTERVAL = 1000L // Check every second

    // UI Elements
    private lateinit var previewView: PreviewView
    private lateinit var statusText: TextView
    private lateinit var statusIcon: ImageView
    private lateinit var btnStartStop: Button

    companion object {
        private const val TAG = "LiveFeedActivity"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = LiveFeedBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Keep screen on and enable fullscreen
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        initializeUI()
        initializeApiClient()
        voiceAlertManager = VoiceAlertManager(this)
        alertLogLoader = AlertLogLoader(this)

        // Add observer for processing state
        viewModel.getProcessingState().observe(this) { state ->
            when (state) {
                is ProcessingState.Success -> {
                    val response = state.response
                    val behaviors = response.behaviors
                    voiceAlertManager.processAlerts(
                        isDrowsy = behaviors.contains("drowsy"),
                        isYawning = behaviors.contains("yawning"),
                        isDistracted = behaviors.contains("distracted")
                    )
                }
                is ProcessingState.Error -> {
                    Log.e(TAG, "Processing error: ${state.message}")
                    updateUI(false, "Error: ${state.message}")
                }
                is ProcessingState.Processing -> {
                    // Optionally handle processing state
                }
                is ProcessingState.Idle -> {
                    // Optionally handle idle state
                }
            }
        }

        // Set up click listeners FIRST
        btnStartStop = binding.btnToggleMonitoring
        btnStartStop.setOnClickListener {
            toggleMonitoring()
        }

        // Check permissions first, then start connection check
        if (checkCameraPermission()) {
            Log.d(TAG, "✅ Camera permission already granted")
        } else {
            Log.w(TAG, "⚠️ Camera permission not granted, will request when needed")
        }
    }

    private fun initializeUI() {
        previewView = binding.previewView
        previewView.implementationMode = PreviewView.ImplementationMode.PERFORMANCE
        previewView.scaleType = PreviewView.ScaleType.FIT_CENTER

        // Remove the problematic surface listener and add a better preview state observer
        previewView.previewStreamState.observe(this) { state ->
            when (state) {
                PreviewView.StreamState.STREAMING -> {
                    Log.d(TAG, "Camera preview is streaming")
                    updateUI(true, "Camera preview active")
                }
                PreviewView.StreamState.IDLE -> {
                    Log.d(TAG, "Camera preview is idle")
                }
                else -> {
                    Log.e(TAG, "Camera preview state: $state")
                }
            }
        }

        statusIcon = binding.statusIndicator
        statusText = binding.statusText

        binding.backButton.setOnClickListener {
            onBackPressed()
        }

        // Set up bottom navigation
        binding.homeIcon.setOnClickListener {
            startActivity(Intent(this, HomePageActivity::class.java))
            finish()
        }

        binding.profileIcon.setOnClickListener {
            startActivity(Intent(this, ProfileActivity::class.java))
        }

        binding.settingsIcon.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
    }

    private fun initializeApiClient() {
        // Initialize ApiClient
        ApiClient.initialize(applicationContext)

        // Start connection check for real operation
        checkServerConnection()
    }

    private fun checkServerConnection() {
        // Cancel any existing connection attempt
        connectionJob?.cancel()

        updateConnectionStatus("Checking connection...")

        connectionJob = scope.launch {
            try {
                var connected = false
                withContext(Dispatchers.IO) {
                    repeat(3) { attempt ->
                        if (!isActivityValid) {
                            return@withContext
                        }

                        if (attempt > 0) {
                            withContext(Dispatchers.Main) {
                                updateConnectionStatus("Retrying connection (${attempt + 1}/3)...")
                            }
                            delay(2000)
                        }

                        try {
                            connected = ApiClient.testConnection()
                            if (connected) {
                                return@withContext
                            }
                        } catch (e: Exception) {
                            Log.e(TAG, "Connection attempt ${attempt + 1} failed", e)
                        }
                    }
                }

                if (!isActivityValid) return@launch

                withContext(Dispatchers.Main) {
                    if (connected) {
                        Log.d(TAG, "Successfully connected to server")
                        isConnected = true
                        updateConnectionStatus("Connected to server")
                        startMonitoring()
                    } else {
                        updateConnectionStatus("Failed to connect to server")
                        showRetryDialog()
                    }
                }
            } catch (e: Exception) {
                if (!isActivityValid) return@launch

                Log.e(TAG, "Error in connection check", e)
                withContext(Dispatchers.Main) {
                    updateConnectionStatus("Connection error: ${e.message}")
                    showRetryDialog()
                }
            }
        }
    }

    private fun updateConnectionStatus(status: String) {
        if (!isActivityValid || isFinishing || isDestroyed) {
            return
        }

        try {
            runOnUiThread {
                if (!isActivityValid || isFinishing || isDestroyed) return@runOnUiThread

                try {
                    statusText.text = status
                    Log.d(TAG, "Connection status: $status")
                } catch (e: Exception) {
                    Log.e(TAG, "Error updating connection status", e)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error in updateConnectionStatus", e)
        }
    }

    private fun showRetryDialog() {
        if (!isActivityValid || isFinishing || isDestroyed) {
            Log.w(TAG, "Attempted to show dialog when activity was invalid")
            return
        }

        try {
            runOnUiThread {
                if (!isActivityValid || this@LiveFeedActivity.isFinishing || this@LiveFeedActivity.isDestroyed) return@runOnUiThread

                AlertDialog.Builder(this)
                    .setTitle("Connection Failed")
                    .setMessage("Failed to connect to the server. Would you like to retry?\n\nMake sure:\n1. The server is running\n2. You're on the same network\n3. The server address is correct")
                    .setPositiveButton("Retry") { dialog, _ ->
                        dialog.dismiss()
                        if (isActivityValid && !isFinishing && !isDestroyed) {
                            checkServerConnection()
                        }
                    }
                    .setNegativeButton("Cancel") { dialog, _ ->
                        dialog.dismiss()
                        if (isActivityValid && !isFinishing && !isDestroyed) {
                            finish()
                        }
                    }
                    .setCancelable(false)
                    .create()
                    .apply {
                        // Additional safety check before showing
                        if (!isActivityValid || this@LiveFeedActivity.isFinishing || this@LiveFeedActivity.isDestroyed) {
                            return@apply
                        }
                        show()
                    }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error showing retry dialog", e)
        }
    }

    private fun toggleMonitoring() {
        isMonitoring = !isMonitoring
        if (isMonitoring) {
            startMonitoring()
        } else {
            stopMonitoring()
        }
    }

    private fun startMonitoring() {
        Log.d(TAG, "🟡 startMonitoring() called - isConnected: $isConnected")

        if (!isConnected) {
            Log.w(TAG, "🔴 NOT CONNECTED TO SERVER - cannot start monitoring")
            Toast.makeText(this, "Not connected to server", Toast.LENGTH_SHORT).show()
            return
        }

        if (checkCameraPermission()) {
            Log.d(TAG, "✅ Camera permission granted - starting camera")
            isMonitoring = true
            btnStartStop.text = "Stop Monitoring"

            try {
                // Always create a new camera service instance
                cameraService = CameraService(
                    context = this,
                    lifecycleOwner = this,
                    previewView = previewView,
                    onFrameCaptured = viewModel::processFrame,
                    onError = this::onCameraError
                )

                // Start camera
                cameraService.startCamera()
                viewModel.onCameraStarted()

                // Start behavior checking for voice alerts
                startBehaviorChecking()
                Log.d(TAG, "🔊 Started behavior checking for voice alerts")

                updateUI(true, "Monitoring active")
                Log.d(TAG, "✅ Camera started successfully")
            } catch (e: Exception) {
                Log.e(TAG, "🔴 ERROR starting camera: ${e.message}")
                onCameraError("Failed to start camera: ${e.message}")
            }
        } else {
            Log.w(TAG, "🔴 Camera permission not granted - requesting permission")
            requestCameraPermission()
        }
    }

    private fun stopMonitoring() {
        try {
            isMonitoring = false
            btnStartStop.text = "Start Monitoring"

            // Stop behavior checking to prevent voice alerts when monitoring is stopped
            handler.removeCallbacksAndMessages(null)

            // Reset voice alert manager to stop any ongoing alerts
            voiceAlertManager.resetCounters()
            Log.d(TAG, "🔇 Stopped behavior checking and reset voice alerts")

            if (::cameraService.isInitialized) {
                cameraService.stopCamera()
                // Release the camera service
                cameraService = CameraService(
                    context = this,
                    lifecycleOwner = this,
                    previewView = previewView,
                    onFrameCaptured = viewModel::processFrame,
                    onError = this::onCameraError
                )
            }

            viewModel.onCameraStopped()
            updateUI(false, "Monitoring stopped")
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping monitoring: ${e.message}")
            updateUI(false, "Error stopping monitoring")
        }
    }

    private fun onCameraError(error: String) {
        Log.e(TAG, "🔴 CAMERA ERROR: $error")
        runOnUiThread {
            updateUI(false, "Camera error: $error")
            stopMonitoring()
            // Don't close activity on camera error - just stop monitoring
            Toast.makeText(this@LiveFeedActivity, "Camera error: $error", Toast.LENGTH_LONG).show()
        }
    }

    private fun checkCameraPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED
    }

    private fun requestCameraPermission() {
        Log.w(TAG, "🔴 CAMERA PERMISSION REQUIRED - showing dialog")
        AlertDialog.Builder(this)
            .setTitle("Camera Permission Required")
            .setMessage("Camera permission is required for driver monitoring. Please grant the permission to continue.")
            .setPositiveButton("Grant") { dialog, _ ->
                Log.d(TAG, "User clicked Grant - requesting camera permission")
                dialog.dismiss()
                requestPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
            .setNegativeButton("Cancel") { dialog, _ ->
                Log.w(TAG, "🔴 USER CANCELLED CAMERA PERMISSION - closing activity")
                dialog.dismiss()
                finish()
            }
            .setCancelable(false)
            .show()
    }

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            Log.d(TAG, "✅ Camera permission granted - starting monitoring")
            startMonitoring()
        } else {
            Log.w(TAG, "🔴 CAMERA PERMISSION DENIED - closing activity")
            Toast.makeText(
                this,
                "Camera permission is required for driver monitoring",
                Toast.LENGTH_LONG
            ).show()
            finish()
        }
    }

    private fun updateUI(isActive: Boolean, message: String? = null) {
        if (!isActivityValid || isFinishing || isDestroyed) {
            return
        }

        try {
            runOnUiThread {
                if (!isActivityValid || isFinishing || isDestroyed) return@runOnUiThread

                try {
                    statusIcon.setImageResource(
                        if (isActive) R.drawable.ic_status_active else R.drawable.ic_status_inactive
                    )
                    statusText.text = message ?: if (isActive) "Connected" else "Disconnected"
                    statusText.setTextColor(
                        ContextCompat.getColor(
                            this,
                            if (isActive) R.color.green else R.color.red
                        )
                    )
                } catch (e: Exception) {
                    Log.e(TAG, "Error updating UI components", e)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error in updateUI", e)
        }
    }

    private fun showError(message: String) {
        if (!isActivityValid || isFinishing || isDestroyed) {
            return
        }

        try {
            runOnUiThread {
                Toast.makeText(this@LiveFeedActivity, message, Toast.LENGTH_LONG).show()
                statusText.text = message
                statusIcon.setImageResource(R.drawable.ic_error)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error showing error message", e)
        }
    }

    override fun onResume() {
        super.onResume()
        if (isMonitoring && ::cameraService.isInitialized &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startMonitoring()
        }
    }

    override fun onPause() {
        super.onPause()
        connectionJob?.cancel()  // Cancel connection attempts when paused
        if (::cameraService.isInitialized) {
            cameraService.stopCamera()
        }
    }

    override fun onDestroy() {
        isActivityValid = false
        connectionJob?.cancel()  // Ensure connection attempts are cancelled
        scope.cancel()
        handler.removeCallbacksAndMessages(null)
        voiceAlertManager.shutdown()
        super.onDestroy()
        if (::cameraService.isInitialized) {
            cameraService.stopCamera()
        }
    }

    private fun processMonitoringData(jsonData: String) {
        try {
            val json = JSONObject(jsonData)
            val behaviors = json.getJSONObject("behaviors")

            voiceAlertManager.processAlerts(
                isDrowsy = behaviors.optBoolean("is_drowsy", false),
                isYawning = behaviors.optBoolean("is_yawning", false),
                isDistracted = behaviors.optBoolean("is_distracted", false)
            )
        } catch (e: Exception) {
            Log.e(TAG, "Error processing monitoring data", e)
        }
    }

    private fun startBehaviorChecking() {
        handler.post(object : Runnable {
            override fun run() {
                checkBehaviorFlags()
                handler.postDelayed(this, CHECK_INTERVAL)
            }
        })
    }

    private fun checkBehaviorFlags() {
        // Move network call to background thread to avoid NetworkOnMainThreadException
        scope.launch(Dispatchers.IO) {
            try {
                val (isDrowsy, isYawning, isDistracted) = alertLogLoader.readLatestBehaviorFlags()

                // Switch back to main thread for UI updates
                withContext(Dispatchers.Main) {
                    voiceAlertManager.processAlerts(isDrowsy, isYawning, isDistracted)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error checking behavior flags: ${e.message}", e)
                // On error, pass false for all behaviors
                withContext(Dispatchers.Main) {
                    voiceAlertManager.processAlerts(false, false, false)
                }
            }
        }
    }


}