package com.example.eyedtrack.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import com.example.eyedtrack.R
import com.example.eyedtrack.api.ApiClient
import com.example.eyedtrack.camera.CameraService
import com.example.eyedtrack.databinding.FragmentMonitorBinding
import com.example.eyedtrack.utils.AlertLogLoader
import com.example.eyedtrack.utils.VoiceAlertManager
import com.example.eyedtrack.viewmodel.CameraViewModel
import com.example.eyedtrack.viewmodel.ProcessingState
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.*

class MonitorFragment : Fragment() {

    private var _binding: FragmentMonitorBinding? = null
    private val binding get() = _binding!!
    private val viewModel: CameraViewModel by viewModels()

    private lateinit var cameraService: CameraService
    private lateinit var voiceAlertManager: VoiceAlertManager
    private lateinit var alertLogLoader: AlertLogLoader
    private val handler = Handler(Looper.getMainLooper())
    private var isConnected = false
    private var isMonitoring = false
    private var connectionJob: Job? = null
    private val CHECK_INTERVAL = 1000L

    companion object {
        private const val TAG = "MonitorFragment"
    }

    // Registered as a Fragment property — Fragment supports registerForActivityResult before onAttach
    private val requestPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) {
                Log.d(TAG, "Camera permission granted - starting monitoring")
                startMonitoring()
            } else {
                Log.w(TAG, "Camera permission denied")
                if (isAdded) {
                    Toast.makeText(
                        requireContext(),
                        "Camera permission is required for driver monitoring",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
        }

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, s: Bundle?): View {
        _binding = FragmentMonitorBinding.inflate(i, c, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        binding.previewView.implementationMode = PreviewView.ImplementationMode.PERFORMANCE
        voiceAlertManager = VoiceAlertManager(requireContext())
        alertLogLoader = AlertLogLoader(requireContext())
        try {
            ApiClient.initialize(requireContext().applicationContext)
        } catch (e: Exception) {
            // No network available at init time; checkServerConnection handles retry
            Log.w(TAG, "ApiClient initialization skipped: ${e.message}")
        }

        viewModel.getProcessingState().observe(viewLifecycleOwner) { state ->
            if (state is ProcessingState.Success) {
                val b = state.response.behaviors
                voiceAlertManager.processAlerts(
                    isDrowsy = b.contains("drowsy"),
                    isYawning = b.contains("yawning"),
                    isDistracted = b.contains("distracted"))
                setStatusSafe()
            } else if (state is ProcessingState.Error) {
                setStatusError(state.message)
            }
        }

        binding.btnToggleMonitoring.setOnClickListener { toggleMonitoring() }
        checkServerConnection()
    }

    // ---------- Carried over from LiveFeedActivity, adapted for Fragment ----------

    private fun checkServerConnection() {
        connectionJob?.cancel()
        updateConnectionStatus("Checking connection...")

        connectionJob = viewLifecycleOwner.lifecycleScope.launch {
            try {
                var connected = false
                withContext(Dispatchers.IO) {
                    repeat(3) { attempt ->
                        if (attempt > 0) {
                            withContext(Dispatchers.Main) {
                                updateConnectionStatus("Retrying connection (${attempt + 1}/3)...")
                            }
                            delay(2000)
                        }
                        try {
                            connected = ApiClient.testConnection()
                            if (connected) return@withContext
                        } catch (e: Exception) {
                            Log.e(TAG, "Connection attempt ${attempt + 1} failed", e)
                        }
                    }
                }

                if (!isAdded) return@launch

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
                Log.e(TAG, "Error in connection check", e)
                if (!isAdded) return@launch
                withContext(Dispatchers.Main) {
                    updateConnectionStatus("Connection error: ${e.message}")
                    showRetryDialog()
                }
            }
        }
    }

    private fun updateConnectionStatus(status: String) {
        _binding?.statusSub?.text = status
        Log.d(TAG, "Connection status: $status")
    }

    private fun showRetryDialog() {
        if (!isAdded || activity?.isFinishing == true) return

        MaterialAlertDialogBuilder(requireContext())
            .setTitle("Connection Failed")
            .setMessage(
                "Failed to connect to the server. Would you like to retry?\n\n" +
                "Make sure:\n1. The server is running\n2. You're on the same network\n" +
                "3. The server address is correct"
            )
            .setPositiveButton("Retry") { dialog, _ ->
                dialog.dismiss()
                checkServerConnection()
            }
            .setNegativeButton("Cancel") { dialog, _ ->
                dialog.dismiss()
            }
            .setCancelable(false)
            .show()
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
        Log.d(TAG, "startMonitoring() called - isConnected: $isConnected")

        if (!isConnected) {
            Log.w(TAG, "NOT CONNECTED TO SERVER - cannot start monitoring")
            isMonitoring = false
            if (isAdded) Toast.makeText(requireContext(), "Not connected to server", Toast.LENGTH_SHORT).show()
            return
        }

        if (checkCameraPermission()) {
            Log.d(TAG, "Camera permission granted - starting camera")
            isMonitoring = true
            binding.btnToggleMonitoring.text = "Stop Monitoring"

            try {
                // Always create a fresh CameraService (prior instance's scope may be cancelled)
                cameraService = CameraService(
                    context = requireContext(),
                    lifecycleOwner = viewLifecycleOwner,
                    previewView = binding.previewView,
                    onFrameCaptured = viewModel::processFrame,
                    onError = ::onCameraError
                )
                cameraService.startCamera()
                viewModel.onCameraStarted()

                // Start periodic behavior checking for voice alerts
                startBehaviorChecking()
                Log.d(TAG, "Camera started successfully")

                binding.statusHeadline.text = "Monitoring"
                binding.statusSub.text = "Camera starting..."
                binding.statusPill.setBackgroundResource(R.drawable.pill_safe)
                binding.statusPill.text = "LIVE"
            } catch (e: Exception) {
                Log.e(TAG, "ERROR starting camera: ${e.message}")
                onCameraError("Failed to start camera: ${e.message}")
            }
        } else {
            Log.w(TAG, "Camera permission not granted - requesting permission")
            isMonitoring = false
            requestCameraPermission()
        }
    }

    private fun stopMonitoring() {
        try {
            isMonitoring = false
            binding.btnToggleMonitoring.text = "Start Monitoring"

            // Stop behavior checking to prevent voice alerts when monitoring is stopped
            handler.removeCallbacksAndMessages(null)
            voiceAlertManager.resetCounters()
            Log.d(TAG, "Stopped behavior checking and reset voice alerts")

            if (::cameraService.isInitialized) {
                cameraService.stopCamera()
            }

            viewModel.onCameraStopped()

            binding.statusHeadline.text = "Not monitoring"
            binding.statusSub.text = "Tap start to begin"
            binding.statusPill.setBackgroundResource(R.drawable.pill_idle)
            binding.statusPill.text = "IDLE"
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping monitoring: ${e.message}")
            setStatusError("Error stopping monitoring")
        }
    }

    private fun onCameraError(error: String) {
        // Called from CameraService coroutine — post to main thread
        Log.e(TAG, "CAMERA ERROR: $error")
        handler.post {
            isMonitoring = false
            _binding?.let {
                it.btnToggleMonitoring.text = "Start Monitoring"
                setStatusError("Camera error: $error")
            }
            handler.removeCallbacksAndMessages(null)
            voiceAlertManager.resetCounters()
            isMonitoring = false
            viewModel.onCameraStopped()
            if (isAdded) {
                context?.let { ctx ->
                    Toast.makeText(ctx, "Camera error: $error", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun checkCameraPermission() = ContextCompat.checkSelfPermission(
        requireContext(), Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    private fun requestCameraPermission() {
        Log.w(TAG, "CAMERA PERMISSION REQUIRED - showing dialog")
        MaterialAlertDialogBuilder(requireContext())
            .setTitle("Camera Permission Required")
            .setMessage(
                "Camera permission is required for driver monitoring. " +
                "Please grant the permission to continue."
            )
            .setPositiveButton("Grant") { dialog, _ ->
                dialog.dismiss()
                requestPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
            .setNegativeButton("Cancel") { dialog, _ ->
                dialog.dismiss()
                if (isAdded) {
                    Toast.makeText(
                        requireContext(),
                        "Camera permission is required for driver monitoring",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
            .setCancelable(false)
            .show()
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
        // Network call must be on background thread (NetworkOnMainThreadException otherwise)
        viewLifecycleOwner.lifecycleScope.launch(Dispatchers.IO) {
            try {
                val (isDrowsy, isYawning, isDistracted) = alertLogLoader.readLatestBehaviorFlags()
                withContext(Dispatchers.Main) {
                    voiceAlertManager.processAlerts(isDrowsy, isYawning, isDistracted)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error checking behavior flags: ${e.message}", e)
                withContext(Dispatchers.Main) {
                    voiceAlertManager.processAlerts(false, false, false)
                }
            }
        }
    }

    // ---------- Status helpers ----------

    private fun setStatusSafe() {
        binding.statusHeadline.text = "Awake"
        binding.statusSub.text = "Monitoring active · all clear"
        binding.statusPill.setBackgroundResource(R.drawable.pill_safe)
        binding.statusPill.text = "LIVE"
    }

    private fun setStatusError(msg: String) {
        binding.statusHeadline.text = "Error"
        binding.statusSub.text = msg
        binding.statusPill.setBackgroundResource(R.drawable.pill_alert)
        binding.statusPill.text = "ERROR"
    }

    // ---------- Lifecycle ----------

    override fun onResume() {
        super.onResume()
        requireActivity().window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    override fun onPause() {
        super.onPause()
        requireActivity().window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        connectionJob?.cancel()
        handler.removeCallbacksAndMessages(null)
        if (::cameraService.isInitialized) cameraService.stopCamera()
        isMonitoring = false
        _binding?.btnToggleMonitoring?.text = "Start Monitoring"
    }

    override fun onDestroyView() {
        handler.removeCallbacksAndMessages(null)
        if (::cameraService.isInitialized) cameraService.stopCamera()
        if (::voiceAlertManager.isInitialized) voiceAlertManager.shutdown()
        _binding = null
        super.onDestroyView()
    }
}
