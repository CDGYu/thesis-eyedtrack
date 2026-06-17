package com.example.eyedtrack

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity

// Activity that displays a loading screen before navigating to the next screen.
class LoadingScreenActivity : AppCompatActivity() {

    // Called when the activity is first created.
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Enable fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        // Set the layout resource for this activity.
        setContentView(R.layout.loading_screen)

        // Delay navigation for 4 seconds to simulate loading.
        Handler(Looper.getMainLooper()).postDelayed({
            // Check if Terms & Conditions have been accepted.
            val nextActivity = if (PreferenceManager.isAccepted(this)) {
                LoginActivity::class.java // Proceed to LoginActivity if accepted.
            } else {
                TermsAndConditionsActivity::class.java // Proceed to TermsAndConditionsActivity if not accepted.
            }

            // Start the next activity.
            val intent = Intent(this, nextActivity)
            startActivity(intent)
            finish() // Close LoadingScreenActivity.
        }, 4000) // 4-second delay.
    }
}