package com.example.eyedtrack

import android.animation.ObjectAnimator
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageButton
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

// Activity for the home page of the app.
class HomePageActivity : AppCompatActivity() {

    // Called when the activity is created.
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Enable fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        setContentView(R.layout.home_page) // Set the layout resource for this activity.

        // Check if user is logged in
        if (!PreferenceManager.isLoggedIn(this)) {
            Toast.makeText(this, "Please log in first", Toast.LENGTH_SHORT).show()
            val intent = Intent(this, LoginActivity::class.java)
            startActivity(intent)
            finish()
            return
        }

        // Scale up the home icon.
        scaleImageButton(findViewById(R.id.home_icon))

        // Initialize buttons.
        val btnGoToSettings = findViewById<ImageButton>(R.id.settings_icon)
        val btnGoToProfile = findViewById<ImageButton>(R.id.profile_icon)
        val btnGoToLiveFeed = findViewById<Button>(R.id.live_feed_button)
        val btnGoToAlertHistory = findViewById<Button>(R.id.alert_history_text)

        // Navigate to SettingsActivity.
        btnGoToSettings.setOnClickListener {
            val intent = Intent(this, SettingsActivity::class.java)
            startActivity(intent)
        }

        // Navigate to ProfileActivity.
        btnGoToProfile.setOnClickListener {
            val intent = Intent(this, ProfileActivity::class.java)
            startActivity(intent)
        }

        // Navigate to AlertHistoryActivity.
        btnGoToAlertHistory.setOnClickListener {
            val intent = Intent(this, AlertHistoryActivity::class.java)
            startActivity(intent)
        }

        // Navigate to LiveFeedActivity.
        btnGoToLiveFeed.setOnClickListener {
            val intent = Intent(this, LiveFeedActivity::class.java)
            startActivity(intent)
        }
    }

    // Scales up the selected button.
    private fun scaleImageButton(button: View) {
        val scaleX = ObjectAnimator.ofFloat(button, "scaleX", 1.5f)
        val scaleY = ObjectAnimator.ofFloat(button, "scaleY", 1.5f)
        scaleX.duration = 300 // Animation duration for X scaling.
        scaleY.duration = 300 // Animation duration for Y scaling.
        scaleX.start()
        scaleY.start()
    }
}