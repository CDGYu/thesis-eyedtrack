package com.example.eyedtrack.api

import com.google.gson.annotations.SerializedName
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface ApiService {
    @GET("api/health")
    suspend fun healthCheck(): Response<Unit>

    @GET("api/health")
    suspend fun checkHealth(): Response<HealthResponse>

    @POST("api/process_frame")
    suspend fun processFrame(@Body frameData: RequestBody): Response<ProcessingResponse>
}

data class HealthResponse(
    val status: String,
    val timestamp: String
)

data class ProcessingResponse(
    val success: Boolean,
    val timestamp: String,
    val session_id: String,
    val behaviors: List<String> = emptyList(),
    val metrics: Metrics,
    val error: String? = null
)

data class Metrics(
    val ear: Double,
    val mar: Double,
    @SerializedName("head_pose")
    val headPose: List<Double>? = null
)

fun createFrameRequestBody(base64Frame: String): RequestBody {
    val jsonObject = JSONObject().apply {
        put("frame", base64Frame)
        put("timestamp", System.currentTimeMillis())
    }
    return jsonObject.toString().toRequestBody("application/json".toMediaTypeOrNull())
} 