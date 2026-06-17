package com.example.eyedtrack.camera

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.*
import android.media.Image
import android.util.Log
import android.util.Size
import androidx.camera.core.*
import androidx.camera.core.ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888
import androidx.camera.core.ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit
import com.google.common.util.concurrent.ListenableFuture
import androidx.camera.core.impl.utils.executor.CameraXExecutors
import kotlinx.coroutines.*
import kotlin.coroutines.resumeWithException

class CameraService(
    private val context: Context,
    private val lifecycleOwner: LifecycleOwner,
    private val previewView: PreviewView,
    private val onFrameCaptured: (String) -> Unit,
    private val onError: (String) -> Unit
) {
    private var cameraProvider: ProcessCameraProvider? = null
    private var camera: androidx.camera.core.Camera? = null
    private lateinit var cameraExecutor: ExecutorService
    private var isProcessingFrame: Boolean = false
    private var retryCount: Int = 0
    private val maxRetries: Int = 3
    private val coroutineScope = CoroutineScope(Dispatchers.Main + Job())

    init {
        cameraExecutor = Executors.newSingleThreadExecutor()
    }

    fun hasCameraPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED
    }

    private suspend fun setupCamera() = withContext(Dispatchers.Main) {
        try {
            Log.d(TAG, "Starting camera setup...")

            // Wait for the preview view to be properly laid out
            if (previewView.width == 0 || previewView.height == 0) {
                Log.d(TAG, "Waiting for PreviewView to be laid out...")
                delay(500) // Give some time for layout
                if (previewView.width == 0 || previewView.height == 0) {
                    throw Exception("PreviewView not properly laid out")
                }
            }

            val cameraProviderFuture: ListenableFuture<ProcessCameraProvider> = ProcessCameraProvider.getInstance(context)
            cameraProvider = suspendCancellableCoroutine { continuation ->
                cameraProviderFuture.addListener({
                    try {
                        val provider = cameraProviderFuture.get()
                        continuation.resume(provider)
                    } catch (e: Exception) {
                        continuation.resumeWithException(e)
                    }
                }, ContextCompat.getMainExecutor(context))
            }

            // Preview use case with flexible resolution
            val preview: Preview = Preview.Builder()
                .setTargetAspectRatio(AspectRatio.RATIO_16_9)  // Changed to 16:9
                .build()
                .also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }

            // Image analysis use case
            val imageAnalysis: ImageAnalysis = ImageAnalysis.Builder()
                .setTargetAspectRatio(AspectRatio.RATIO_16_9)  // Match preview aspect ratio
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setOutputImageFormat(OUTPUT_IMAGE_FORMAT_RGBA_8888)
                .build()
                .also {
                    it.setAnalyzer(cameraExecutor) { image: ImageProxy ->
                        if (!isProcessingFrame) {
                            processImage(image)
                        }
                        image.close()
                    }
                }

            // Try to get available cameras
            val availableCameras: List<CameraInfo> = cameraProvider?.availableCameraInfos ?: emptyList()
            if (availableCameras.isEmpty()) {
                throw Exception("No cameras available on this device")
            }

            // Try front camera first, fall back to any available camera
            val cameraSelector: CameraSelector = when {
                cameraProvider?.hasCamera(CameraSelector.DEFAULT_FRONT_CAMERA) == true -> {
                    Log.d(TAG, "Using front camera")
                    CameraSelector.DEFAULT_FRONT_CAMERA
                }
                cameraProvider?.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA) == true -> {
                    Log.d(TAG, "Front camera not available, using back camera")
                    CameraSelector.DEFAULT_BACK_CAMERA
                }
                else -> {
                    throw Exception("No cameras available")
                }
            }

            try {
                // Unbind any previous use cases
                cameraProvider?.unbindAll()

                // Bind use cases
                camera = cameraProvider?.bindToLifecycle(
                    lifecycleOwner,
                    cameraSelector,
                    preview,
                    imageAnalysis
                )

                // Configure camera
                camera?.let { cam ->
                    try {
                        // Set up camera controls
                        val exposureState = cam.cameraInfo.exposureState
                        if (exposureState.isExposureCompensationSupported) {
                            cam.cameraControl.setExposureCompensationIndex(0)
                        }

                        // Set up auto-focus
                        val centerPoint = previewView.meteringPointFactory.createPoint(
                            previewView.width / 2f,
                            previewView.height / 2f
                        )

                        val focusMeteringAction = FocusMeteringAction.Builder(centerPoint)
                            .setAutoCancelDuration(5, TimeUnit.SECONDS)
                            .build()

                        cam.cameraControl.startFocusAndMetering(focusMeteringAction)
                            .addListener({
                                Log.d(TAG, "Focus set successfully")
                            }, ContextCompat.getMainExecutor(context))

                    } catch (e: Exception) {
                        Log.w(TAG, "Failed to set up camera controls", e)
                    }
                }

                Log.d(TAG, "Camera setup successful")
                retryCount = 0  // Reset retry count on success
            } catch (e: Exception) {
                val errorMsg = "Failed to bind camera use cases: ${e.message}"
                Log.e(TAG, errorMsg, e)
                throw e
            }
        } catch (e: Exception) {
            val errorMsg = "Camera initialization failed: ${e.message}"
            Log.e(TAG, errorMsg, e)
            throw e
        }
    }

    fun startCamera() {
        if (!hasCameraPermission()) {
            onError("Camera permission not granted")
            return
        }

        coroutineScope.launch {
            try {
                var attempts = 0
                while (attempts < maxRetries) {
                    try {
                        setupCamera()
                        break
                    } catch (e: Exception) {
                        attempts++
                        if (attempts >= maxRetries) {
                            onError("Failed to start camera after $maxRetries attempts: ${e.message}")
                            break
                        }
                        Log.d(TAG, "Retrying camera setup (attempt $attempts of $maxRetries)")
                        delay(1000)
                    }
                }
            } catch (e: Exception) {
                onError("Failed to start camera: ${e.message}")
            }
        }
    }

    private fun processImage(image: ImageProxy) {
        try {
            isProcessingFrame = true
            Log.d(TAG, "Processing new frame. Format: ${image.format}, Size: ${image.width}x${image.height}")

            // Convert ImageProxy to Bitmap
            val bitmap = image.toBitmap()
            if (bitmap == null) {
                Log.e(TAG, "Failed to convert image to bitmap")
                return
            }
            Log.d(TAG, "Successfully converted frame to bitmap. Size: ${bitmap.width}x${bitmap.height}")

            // Rotate bitmap if needed (front camera images are mirrored)
            val matrix = Matrix().apply {
                postRotate(90f)
                if (camera?.cameraInfo?.lensFacing == CameraSelector.LENS_FACING_FRONT) {
                    postScale(-1f, 1f)
                }
            }
            val rotatedBitmap = Bitmap.createBitmap(
                bitmap,
                0, 0,
                bitmap.width, bitmap.height,
                matrix,
                true
            )
            Log.d(TAG, "Rotated bitmap by 90 degrees. New size: ${rotatedBitmap.width}x${rotatedBitmap.height}")

            // Compress bitmap to reduce size while maintaining quality
            Log.d(TAG, "Starting bitmap compression...")
            val outputStream = ByteArrayOutputStream()
            rotatedBitmap.compress(Bitmap.CompressFormat.JPEG, 85, outputStream)
            val compressedSize = outputStream.size()
            Log.d(TAG, "Bitmap compressed. Size: $compressedSize bytes")

            // Convert to base64
            val base64Image = android.util.Base64.encodeToString(
                outputStream.toByteArray(),
                android.util.Base64.NO_WRAP
            )
            Log.d(TAG, "Converted bitmap to base64. Length: ${base64Image.length} bytes")

            // Clean up
            outputStream.close()
            bitmap.recycle()
            rotatedBitmap.recycle()

            // Send frame for processing
            onFrameCaptured(base64Image)
            Log.d(TAG, "Frame sent for processing")

        } catch (e: Exception) {
            Log.e(TAG, "Error processing frame", e)
            onError("Error processing frame: ${e.message}")
        } finally {
            isProcessingFrame = false
        }
    }

    private fun ImageProxy.toBitmap(): Bitmap? {
        val yBuffer = planes[0].buffer
        val uBuffer = planes[1].buffer
        val vBuffer = planes[2].buffer

        val ySize = yBuffer.remaining()
        val uSize = uBuffer.remaining()
        val vSize = vBuffer.remaining()

        val nv21 = ByteArray(ySize + uSize + vSize)

        yBuffer.get(nv21, 0, ySize)
        vBuffer.get(nv21, ySize, vSize)
        uBuffer.get(nv21, ySize + vSize, uSize)

        val yuvImage = YuvImage(nv21, ImageFormat.NV21, width, height, null)
        val out = ByteArrayOutputStream()
        yuvImage.compressToJpeg(Rect(0, 0, width, height), 100, out)
        val imageBytes = out.toByteArray()
        return BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
    }

    fun stopCamera() {
        try {
            coroutineScope.cancel()
            cameraProvider?.unbindAll()
            cameraExecutor.shutdown()
            try {
                if (!cameraExecutor.awaitTermination(1000, TimeUnit.MILLISECONDS)) {
                    cameraExecutor.shutdownNow()
                }
            } catch (e: InterruptedException) {
                cameraExecutor.shutdownNow()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping camera", e)
            onError("Error stopping camera: ${e.message}")
        }
    }

    companion object {
        private const val TAG = "CameraService"
    }
} 