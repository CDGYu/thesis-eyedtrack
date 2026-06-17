package com.example.eyedtrack.api

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import okhttp3.ConnectionPool
import kotlinx.coroutines.delay

object ApiClient {
    private const val TAG = "ApiClient"
    private const val BASE_URL = "http://192.168.68.110:5000/"
    private var retrofit: Retrofit? = null
    private var apiService: ApiService? = null
    private lateinit var appContext: Context

    fun initialize(context: Context) {
        appContext = context.applicationContext
        Log.d(TAG, "Initializing ApiClient with base URL: $BASE_URL")

        if (!isNetworkAvailable()) {
            Log.e(TAG, "No network connection available")
            throw IllegalStateException("No network connection available")
        }

        // Create logging interceptor
        val logging = HttpLoggingInterceptor { message ->
            Log.d(TAG, "Network: $message")
        }.apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        // Create OkHttpClient
        val client = OkHttpClient.Builder()
            .addInterceptor(logging)
            .addInterceptor { chain ->
                val request = chain.request()
                Log.d(TAG, "Sending request to: ${request.url}")
                try {
                    val response = chain.proceed(request)
                    Log.d(TAG, "Response code: ${response.code}")
                    if (!response.isSuccessful) {
                        Log.e(TAG, "Error response: ${response.message}")
                    }
                    response
                } catch (e: Exception) {
                    when (e) {
                        is SocketTimeoutException -> Log.e(TAG, "Request timed out", e)
                        is UnknownHostException -> Log.e(TAG, "Unable to resolve host", e)
                        else -> Log.e(TAG, "Network error", e)
                    }
                    throw e
                }
            }
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .connectionPool(ConnectionPool(0, 5, TimeUnit.MINUTES))
            .retryOnConnectionFailure(true)
            .build()

        try {
            retrofit = Retrofit.Builder()
                .baseUrl(BASE_URL)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()

            apiService = retrofit?.create(ApiService::class.java)
            Log.d(TAG, "ApiClient initialized successfully")
        } catch (e: Exception) {
            Log.e(TAG, "Error initializing ApiClient", e)
            throw e
        }
    }

    private fun isNetworkAvailable(): Boolean {
        val connectivityManager = appContext.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false

        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
                capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    fun getApiService(): ApiService {
        if (!isNetworkAvailable()) {
            throw IllegalStateException("No network connection available")
        }
        return apiService ?: throw IllegalStateException("ApiClient must be initialized before using")
    }

    suspend fun testConnection(maxRetries: Int = 3): Boolean {
        var attempts = 0
        var lastException: Exception? = null

        while (attempts < maxRetries) {
            if (!isNetworkAvailable()) {
                Log.e(TAG, "No network connection available (attempt ${attempts + 1}/$maxRetries)")
                delay(2000) // Wait 2 seconds before retry
                attempts++
                continue
            }

            try {
                Log.d(TAG, "Testing connection to $BASE_URL (attempt ${attempts + 1}/$maxRetries)")
                val response = getApiService().healthCheck()

                if (response.isSuccessful) {
                    Log.d(TAG, "Connection test successful")
                    return true
                } else {
                    Log.e(TAG, "Health check failed with code: ${response.code()}")
                    Log.e(TAG, "Error body: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                lastException = e
                when (e) {
                    is SocketTimeoutException -> Log.e(TAG, "Connection test timed out (attempt ${attempts + 1}/$maxRetries)", e)
                    is UnknownHostException -> Log.e(TAG, "Unable to resolve host (attempt ${attempts + 1}/$maxRetries)", e)
                    else -> Log.e(TAG, "Connection test failed (attempt ${attempts + 1}/$maxRetries)", e)
                }
            }

            attempts++
            if (attempts < maxRetries) {
                delay(2000) // Wait 2 seconds before retry
            }
        }

        Log.e(TAG, "All connection attempts failed")
        lastException?.let {
            Log.e(TAG, "Last error message: ${it.message}")
            Log.e(TAG, "Last error cause: ${it.cause}")
        }
        return false
    }
} 