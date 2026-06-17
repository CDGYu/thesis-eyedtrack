package com.example.eyedtrack

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.View
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.example.eyedtrack.adapter.AlertHistoryAdapter
import com.example.eyedtrack.model.AlertHistoryItem
import com.example.eyedtrack.utils.AlertLogLoader
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.InputStream
import java.nio.channels.FileChannel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Activity that displays the alert history screen.
 */
class AlertHistoryActivity : AppCompatActivity() {
    private lateinit var alertsRecyclerView: RecyclerView
    private lateinit var alertAdapter: AlertHistoryAdapter
    private lateinit var noAlertsText: TextView
    private lateinit var summaryContent: TextView
    private lateinit var swipeRefreshLayout: SwipeRefreshLayout
    private val TAG = "AlertHistoryActivity"
    private val STORAGE_PERMISSION_CODE = 101
    
    // Auto-refresh mechanism
    private var autoRefreshHandler: Handler? = null
    private var autoRefreshRunnable: Runnable? = null
    private val AUTO_REFRESH_INTERVAL = 10000L // 10 seconds
    private var isAutoRefreshEnabled = true

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.entries.all { it.value }
        if (allGranted) {
            // Permissions granted, proceed with loading logs
            proceedWithLoading()
        } else {
            // Handle the case where permissions are denied
            if (shouldShowRequestPermissionRationale(Manifest.permission.READ_EXTERNAL_STORAGE)) {
                showPermissionExplanationDialog()
            } else {
                // User denied permissions with "Don't ask again"
                showSettingsDialog()
            }
        }
    }

    // Called when the activity is first created.
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Set the activity to fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        // Set the layout resource for this activity.
        setContentView(R.layout.alert_history)

        // Initialize UI components
        alertsRecyclerView = findViewById(R.id.alerts_recycler_view)
        noAlertsText = findViewById(R.id.no_alerts_text)
        summaryContent = findViewById(R.id.summary_content)
        swipeRefreshLayout = findViewById(R.id.swipe_refresh_layout)

        // Setup swipe to refresh
        swipeRefreshLayout.setOnRefreshListener {
            refreshAlertHistory()
        }
        swipeRefreshLayout.setColorSchemeResources(
            R.color.purple_500,
            R.color.purple_700,
            R.color.teal_200
        )

        // Initialize the RecyclerView
        alertsRecyclerView.layoutManager = LinearLayoutManager(this)
        alertAdapter = AlertHistoryAdapter(emptyList())
        alertsRecyclerView.adapter = alertAdapter

        // Initialize navigation buttons.
        val btnGoToSettings = findViewById<ImageButton>(R.id.settings_icon)
        val btnGoToProfileActivity = findViewById<ImageButton>(R.id.profile_icon)
        val btnGoToHomePageActivity = findViewById<ImageButton>(R.id.home_icon)

        // Initialize the back button to return to the previous screen.
        val backButton = findViewById<ImageView>(R.id.back_button)

        // Add a refresh button
        val refreshButton = findViewById<ImageView>(R.id.refresh_button)
        refreshButton.setOnClickListener {
            refreshAlertHistory()
        }


        // Set a click listener to navigate to the SettingsActivity.
        btnGoToSettings.setOnClickListener {
            val intent = Intent(this, SettingsActivity::class.java)
            startActivity(intent)
        }

        // Set a click listener to navigate to the ProfileActivity.
        btnGoToProfileActivity.setOnClickListener {
            val intent = Intent(this, ProfileActivity::class.java)
            startActivity(intent)
        }

        // Set a click listener to navigate to the HomePageActivity.
        btnGoToHomePageActivity.setOnClickListener {
            val intent = Intent(this, HomePageActivity::class.java)
            startActivity(intent)
        }

        // Set a click listener on the back button to close the activity.
        backButton.setOnClickListener {
            finish()
        }

        // Check for permissions before loading logs
        checkPermissionsAndLoadLogs()
        
        // Initialize auto-refresh mechanism
        setupAutoRefresh()
    }
    
    private fun checkPermissionsAndLoadLogs() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // Android 11+ uses different permission model
            if (Environment.isExternalStorageManager()) {
                proceedWithLoading()
            } else {
                val intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                val uri = Uri.fromParts("package", packageName, null)
                intent.data = uri
                try {
                    Toast.makeText(this, "Please grant all files access permission", Toast.LENGTH_LONG).show()
                    startActivity(intent)
                } catch (e: Exception) {
                    Toast.makeText(this, "Unable to request permission: ${e.message}", Toast.LENGTH_LONG).show()
                    Log.e(TAG, "Error requesting MANAGE_EXTERNAL_STORAGE: ${e.message}")
                    // Fall back to legacy permissions
                    requestLegacyStoragePermissions()
                }
            }
        } else {
            // For Android 10 and below
            requestLegacyStoragePermissions()
        }
    }
    
    private fun requestLegacyStoragePermissions() {
        val permissions = arrayOf(
            Manifest.permission.READ_EXTERNAL_STORAGE,
            Manifest.permission.WRITE_EXTERNAL_STORAGE
        )
        
        if (hasPermissions(permissions)) {
            proceedWithLoading()
        } else {
            requestPermissionLauncher.launch(permissions)
        }
    }
    
    private fun hasPermissions(permissions: Array<String>): Boolean {
        return permissions.all {
            ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
        }
    }
    
    private fun showPermissionExplanationDialog() {
        AlertDialog.Builder(this)
            .setTitle("Storage Permission Needed")
            .setMessage("This app needs storage permission to read the driver monitoring logs. Please grant this permission.")
            .setPositiveButton("OK") { _, _ ->
                requestLegacyStoragePermissions()
            }
            .setNegativeButton("Cancel") { dialog, _ ->
                dialog.dismiss()
                Toast.makeText(this, "Cannot load logs without storage permission", Toast.LENGTH_LONG).show()
            }
            .create()
            .show()
    }
    
    private fun showSettingsDialog() {
        AlertDialog.Builder(this)
            .setTitle("Permission Required")
            .setMessage("Storage permissions are required to load logs. Please enable them in app settings.")
            .setPositiveButton("Settings") { _, _ ->
                val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                val uri = Uri.fromParts("package", packageName, null)
                intent.data = uri
                startActivity(intent)
            }
            .setNegativeButton("Cancel") { dialog, _ ->
                dialog.dismiss()
                Toast.makeText(this, "Cannot load logs without storage permission", Toast.LENGTH_LONG).show()
            }
            .create()
            .show()
    }
    
    private fun proceedWithLoading() {
        // Load alert logs directly using the updated AlertLogLoader
        loadAlertLogs()
    }

    /**
     * Load alert logs from the driver monitoring logs
     */
    private fun loadAlertLogs() {
        lifecycleScope.launch {
            try {
                // Set a loading indicator or message
                if (!swipeRefreshLayout.isRefreshing) {
                    summaryContent.text = "Loading alert logs..."
                }
                
                val alertLogLoader = AlertLogLoader(this@AlertHistoryActivity)
                val alertItems = alertLogLoader.loadAlertLogs(50) // Increased limit to see more alerts
                
                // Update UI with the loaded alert items
                if (alertItems.isEmpty()) {
                    swipeRefreshLayout.visibility = View.GONE
                    noAlertsText.visibility = View.VISIBLE
                    alertsRecyclerView.visibility = View.GONE
                    summaryContent.text = "No risky behaviors have been detected."
                    Toast.makeText(this@AlertHistoryActivity, "No alert records found", Toast.LENGTH_SHORT).show()
                } else {
                    noAlertsText.visibility = View.GONE
                    swipeRefreshLayout.visibility = View.VISIBLE
                    alertsRecyclerView.visibility = View.VISIBLE
                    alertAdapter.updateAlerts(alertItems)
                    
                    // Update summary text
                    val todayDate = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
                    val todayAlerts = alertItems.filter { it.date == todayDate }
                    val recentAlerts = alertItems.filter { 
                        it.date >= SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date(System.currentTimeMillis() - 24 * 60 * 60 * 1000))
                    }
                    
                    val summary = when {
                        todayAlerts.isEmpty() && recentAlerts.isEmpty() -> "Found ${alertItems.size} risky behaviors in logs. Latest: ${alertItems.first().date} at ${alertItems.first().time}"
                        todayAlerts.isNotEmpty() -> "${todayAlerts.size} risky behavior(s) detected today. Total in logs: ${alertItems.size}"
                        recentAlerts.isNotEmpty() -> "${recentAlerts.size} risky behavior(s) in last 24h. Total in logs: ${alertItems.size}"
                        else -> "Found ${alertItems.size} risky behaviors in logs"
                    }
                    
                    summaryContent.text = summary
                    Toast.makeText(this@AlertHistoryActivity, "Found ${alertItems.size} alert records", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error loading alert logs: ${e.message}")
                Toast.makeText(this@AlertHistoryActivity, "Error loading alerts: ${e.message}", Toast.LENGTH_LONG).show()
                swipeRefreshLayout.visibility = View.GONE
                noAlertsText.visibility = View.VISIBLE
                alertsRecyclerView.visibility = View.GONE
                summaryContent.text = "Error loading alert data."
            } finally {
                // Make sure the refresh indicator is gone
                swipeRefreshLayout.isRefreshing = false
            }
        }
    }

    // New method to refresh alert history
    private fun refreshAlertHistory() {
        Log.d(TAG, "🔄 Refreshing alert history to get latest records...")
        Toast.makeText(this, "Getting latest alerts...", Toast.LENGTH_SHORT).show()
        
        // Start showing the refresh animation
        swipeRefreshLayout.isRefreshing = true
        
        lifecycleScope.launch {
            try {
                // Force clear any cached data and get fresh alerts
                val alertLogLoader = AlertLogLoader(this@AlertHistoryActivity)
                val alertItems = alertLogLoader.loadAlertLogs(100) // Increased limit for better history
                
                withContext(Dispatchers.Main) {
                    if (alertItems.isNotEmpty()) {
                        noAlertsText.visibility = View.GONE
                        alertsRecyclerView.visibility = View.VISIBLE
                        
                        // Get info about current vs new data
                        val latestDate = alertItems.first().date
                        val latestTime = alertItems.first().time
                        val latestTimestamp = "${latestDate}T${latestTime}"
                        
                        Log.d(TAG, "📊 Replacing alert history with ${alertItems.size} fresh records")
                        Log.d(TAG, "🕐 Latest alert timestamp: $latestTimestamp")
                        
                        // Update adapter with new data (this will replace old records)
                        alertAdapter.updateAlerts(alertItems)
                        
                        // Scroll to top to show the most recent alerts
                        alertsRecyclerView.scrollToPosition(0)
                        
                        // Update summary text with fresh info
                        val todayDate = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
                        val todayAlerts = alertItems.filter { it.date == todayDate }
                        
                        val summary = if (todayAlerts.isNotEmpty()) {
                            "${todayAlerts.size} risky behavior(s) today. Latest: $latestDate $latestTime (${alertItems.size} total)"
                        } else {
                            "Latest alert: $latestDate $latestTime (${alertItems.size} total records)"
                        }
                        
                        summaryContent.text = summary
                        
                        // Show success message with latest timestamp
                        Toast.makeText(this@AlertHistoryActivity, 
                            "✅ Updated with ${alertItems.size} alerts. Latest: $latestTime", 
                            Toast.LENGTH_LONG).show()
                            
                        Log.i(TAG, "✅ Successfully replaced alert history with fresh data")
                    } else {
                        Toast.makeText(this@AlertHistoryActivity, "No alert records found", Toast.LENGTH_SHORT).show()
                        noAlertsText.visibility = View.VISIBLE
                        alertsRecyclerView.visibility = View.GONE
                        summaryContent.text = "No risky behaviors have been detected."
                        Log.w(TAG, "⚠️ No alert records returned from API")
                    }
                    
                    // Stop the refresh animation
                    swipeRefreshLayout.isRefreshing = false
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ Error refreshing alert history: ${e.message}")
                e.printStackTrace()
                
                withContext(Dispatchers.Main) {
                    swipeRefreshLayout.isRefreshing = false
                    Toast.makeText(this@AlertHistoryActivity, "❌ Error refreshing: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }
    
    override fun onResume() {
        super.onResume()
        
        Log.d(TAG, "🔄 onResume() called - starting fresh alert monitoring")
        
        // Always refresh the alerts immediately when resuming
        refreshAlertHistory()
        
        // Start auto-refresh to continuously monitor for new alerts
        startAutoRefresh()
        
        // If permissions are granted in settings, proceed with loading
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            if (Environment.isExternalStorageManager()) {
                proceedWithLoading()
            }
        } else if (hasPermissions(arrayOf(
                Manifest.permission.READ_EXTERNAL_STORAGE,
                Manifest.permission.WRITE_EXTERNAL_STORAGE
            ))) {
            proceedWithLoading()
        }
    }
    
    override fun onPause() {
        super.onPause()
        Log.d(TAG, "⏸️ onPause() called - stopping auto-refresh to save resources")
        stopAutoRefresh()
    }
    
    override fun onDestroy() {
        super.onDestroy()
        Log.d(TAG, "🛑 onDestroy() called - cleaning up auto-refresh")
        stopAutoRefresh()
        autoRefreshHandler = null
        autoRefreshRunnable = null
    }

    /**
     * Setup automatic refresh to continuously update with latest alerts
     */
    private fun setupAutoRefresh() {
        autoRefreshHandler = Handler(Looper.getMainLooper())
        autoRefreshRunnable = object : Runnable {
            override fun run() {
                if (isAutoRefreshEnabled) {
                    Log.d(TAG, "🔄 Auto-refresh triggered - checking for new alerts...")
                    refreshAlertHistory()
                    
                    // Schedule next refresh
                    autoRefreshHandler?.postDelayed(this, AUTO_REFRESH_INTERVAL)
                }
            }
        }
    }
    
    /**
     * Start auto-refresh
     */
    private fun startAutoRefresh() {
        if (autoRefreshHandler != null && autoRefreshRunnable != null) {
            isAutoRefreshEnabled = true
            autoRefreshHandler?.postDelayed(autoRefreshRunnable!!, AUTO_REFRESH_INTERVAL)
            Log.d(TAG, "🔄 Auto-refresh started (every ${AUTO_REFRESH_INTERVAL/1000}s)")
        }
    }
    
    /**
     * Stop auto-refresh
     */
    private fun stopAutoRefresh() {
        isAutoRefreshEnabled = false
        autoRefreshRunnable?.let { autoRefreshHandler?.removeCallbacks(it) }
        Log.d(TAG, "⏹️ Auto-refresh stopped")
    }
}