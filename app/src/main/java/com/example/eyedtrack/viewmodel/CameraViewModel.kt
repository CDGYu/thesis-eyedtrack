package com.example.eyedtrack.viewmodel

import android.util.Log
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.eyedtrack.api.ApiClient
import com.example.eyedtrack.api.ProcessingResponse
import com.example.eyedtrack.api.createFrameRequestBody
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.io.IOException

class CameraViewModel : ViewModel() {
    private val _processingState = MutableLiveData<ProcessingState>()
    private val _serverHealth = MutableLiveData<Boolean>()
    private var lastProcessedTime = 0L
    private val processingInterval = 200L // Process every 200ms
    private var isServerHealthy = false
    private var healthCheckJob: Job? = null
    private var consecutiveFailures = 0
    private val maxConsecutiveFailures = 3
    private val coroutineScope = viewModelScope

    companion object {
        private const val TAG = "CameraViewModel"
    }

    init {
        viewModelScope.launch {
            checkServerHealth()
        }
    }

    private suspend fun checkServerHealth() {
        try {
            val response = ApiClient.getApiService().checkHealth()
            withContext(Dispatchers.Main) {
                if (response.isSuccessful) {
                    isServerHealthy = true
                    _serverHealth.value = true
                } else {
                    isServerHealthy = false
                    _serverHealth.value = false
                    Log.e(TAG, "Health check failed with code: ${response.code()}")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Health check failed: ${e.message}")
            withContext(Dispatchers.Main) {
                isServerHealthy = false
                _serverHealth.value = false
            }
        }
    }

    fun processFrame(base64Frame: String) {
        val currentTime = System.currentTimeMillis()
        if (currentTime - lastProcessedTime < processingInterval) {
            Log.d(TAG, "Skipping frame processing - too soon (interval: ${currentTime - lastProcessedTime}ms < ${processingInterval}ms)")
            return
        }

        if (_processingState.value is ProcessingState.Processing) {
            Log.d(TAG, "Skipping frame processing - already processing previous frame")
            return
        }

        if (!isServerHealthy) {
            Log.e(TAG, "Server not healthy, checking health... Last state: $_processingState")
            viewModelScope.launch { checkServerHealth() }
            return
        }

        lastProcessedTime = currentTime
        viewModelScope.launch {
            try {
                withContext(Dispatchers.Main) {
                    _processingState.value = ProcessingState.Processing
                }

                val requestBody = createFrameRequestBody(base64Frame)
                val response = ApiClient.getApiService().processFrame(requestBody)

                withContext(Dispatchers.Main) {
                    if (response.isSuccessful) {
                        response.body()?.let { result ->
                            _processingState.value = ProcessingState.Success(result)
                        } ?: run {
                            _processingState.value = ProcessingState.Error("Empty response from server")
                        }
                    } else {
                        _processingState.value = ProcessingState.Error("Server error: ${response.code()}")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Frame processing failed: ${e.message}")
                withContext(Dispatchers.Main) {
                    _processingState.value = ProcessingState.Error(e.message ?: "Unknown error")
                }
            }
        }
    }

    fun getProcessingState(): LiveData<ProcessingState> = _processingState
    fun getServerHealth(): LiveData<Boolean> = _serverHealth

    private fun startPeriodicHealthCheck() {
        healthCheckJob?.cancel()
        healthCheckJob = viewModelScope.launch {
            while (isActive) {
                checkServerHealth()
                delay(10000)
            }
        }
    }

    fun onCameraStarted() {
        _processingState.value = ProcessingState.Idle
        lastProcessedTime = 0
        consecutiveFailures = 0
        startPeriodicHealthCheck()
    }

    fun onCameraStopped() {
        _processingState.value = ProcessingState.Idle
        healthCheckJob?.cancel()
    }

    override fun onCleared() {
        super.onCleared()
        healthCheckJob?.cancel()
        _processingState.value = ProcessingState.Idle
    }
}

sealed class ProcessingState {
    object Idle : ProcessingState()
    object Processing : ProcessingState()
    data class Success(val response: ProcessingResponse) : ProcessingState()
    data class Error(val message: String) : ProcessingState()
} 