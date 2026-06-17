package com.example.eyedtrack

import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.media.AudioManager
import android.os.Bundle
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.SeekBar
import android.widget.Switch
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

// Activity for the "Sounds" screen with system-integrated sound settings.
class SoundsActivity : AppCompatActivity() {

    private lateinit var audioManager: AudioManager
    private lateinit var systemVolumeSwitch: Switch
    private lateinit var volumeSeekBar: SeekBar
    private lateinit var vibrateSwitch: Switch
    private lateinit var volumeLabel: TextView
    private lateinit var sharedPreferences: SharedPreferences

    // Called when the activity is created.
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Enable fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        setContentView(R.layout.sounds_page) // Set the layout resource for this activity.

        // Initialize audio manager and preferences
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        sharedPreferences = getSharedPreferences("SoundSettings", Context.MODE_PRIVATE)

        // Initialize UI components
        initializeViews()
        setupVolumeControls()
        loadSettings()

        // Initialize navigation buttons.
        val backButton = findViewById<ImageView>(R.id.back_button)
        val btnGoToSettings = findViewById<ImageButton>(R.id.settings_icon)
        val btnGoToProfile = findViewById<ImageButton>(R.id.profile_icon)
        val btnGoToHomePage = findViewById<ImageButton>(R.id.home_icon)

        // Close the activity when the back button is clicked.
        backButton.setOnClickListener {
            finish()
        }

        // Navigation to other activities.
        btnGoToProfile.setOnClickListener {
            startActivity(Intent(this, ProfileActivity::class.java))
        }

        btnGoToSettings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        btnGoToHomePage.setOnClickListener {
            startActivity(Intent(this, HomePageActivity::class.java))
        }
    }

    private fun initializeViews() {
        systemVolumeSwitch = findViewById(R.id.systemVolumeSwitch)
        volumeSeekBar = findViewById(R.id.volumeSeekBar)
        vibrateSwitch = findViewById(R.id.vibrateSwitch)
        volumeLabel = findViewById(R.id.volumeLabel)
    }

    private fun setupVolumeControls() {
        // Setup system volume switch
        systemVolumeSwitch.setOnCheckedChangeListener { _, isChecked ->
            saveSystemVolumeSetting(isChecked)
            updateVolumeControlsState(isChecked)
            if (isChecked) {
                // Sync with current system volume
                syncWithSystemVolume()
            }
        }

        // Setup volume seekbar
        volumeSeekBar.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                if (fromUser && !systemVolumeSwitch.isChecked) {
                    saveCustomVolume(progress)
                }
            }

            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })

        // Setup vibrate switch
        vibrateSwitch.setOnCheckedChangeListener { _, isChecked ->
            saveVibrateSetting(isChecked)
        }
    }

    private fun updateVolumeControlsState(useSystemVolume: Boolean) {
        volumeSeekBar.isEnabled = !useSystemVolume
        volumeLabel.alpha = if (useSystemVolume) 0.5f else 1.0f
        
        if (useSystemVolume) {
            syncWithSystemVolume()
        }
    }

    private fun syncWithSystemVolume() {
        val currentVolume = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val progress = ((currentVolume.toFloat() / maxVolume.toFloat()) * 100).toInt()
        volumeSeekBar.progress = progress
    }

    private fun loadSettings() {
        // Load system volume setting (default: true)
        val useSystemVolume = sharedPreferences.getBoolean("use_system_volume", true)
        systemVolumeSwitch.isChecked = useSystemVolume
        updateVolumeControlsState(useSystemVolume)

        // Load custom volume setting (default: 50%)
        val customVolume = sharedPreferences.getInt("custom_volume", 50)
        if (!useSystemVolume) {
            volumeSeekBar.progress = customVolume
        }

        // Load vibrate setting (default: true)
        val vibrateEnabled = sharedPreferences.getBoolean("vibrate_enabled", true)
        vibrateSwitch.isChecked = vibrateEnabled
    }

    private fun saveSystemVolumeSetting(useSystemVolume: Boolean) {
        sharedPreferences.edit()
            .putBoolean("use_system_volume", useSystemVolume)
            .apply()
    }

    private fun saveCustomVolume(volume: Int) {
        sharedPreferences.edit()
            .putInt("custom_volume", volume)
            .apply()
    }

    private fun saveVibrateSetting(vibrateEnabled: Boolean) {
        sharedPreferences.edit()
            .putBoolean("vibrate_enabled", vibrateEnabled)
            .apply()
    }

    override fun onResume() {
        super.onResume()
        // Refresh system volume when returning to the activity
        if (systemVolumeSwitch.isChecked) {
            syncWithSystemVolume()
        }
    }
}