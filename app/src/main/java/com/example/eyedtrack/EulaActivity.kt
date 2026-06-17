package com.example.eyedtrack

import android.content.Intent
import android.os.Bundle
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

// Activity that displays the End User License Agreement (EULA) content.
class EulaActivity : AppCompatActivity() {

    // Called when the activity is first created.
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Set the activity to fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        // Set the layout resource for this activity.
        setContentView(R.layout.eula)

        // Display the EULA content from string resources.
        val eulaTextView = findViewById<TextView>(R.id.eula_text)
        eulaTextView.text = getString(R.string.eula_content)

        // Initialize the back button to return to the previous screen.
        val backButton = findViewById<ImageView>(R.id.back_button)

        // Initialize navigation buttons.
        val btnGoToSettings = findViewById<ImageButton>(R.id.settings_icon)
        val btnGoToProfileActivity = findViewById<ImageButton>(R.id.profile_icon)
        val btnGoToHomePageActivity = findViewById<ImageButton>(R.id.home_icon)

        // Set a click listener on the back button to close the activity.
        backButton.setOnClickListener {
            finish()
        }

        // Set a click listener to navigate to the ProfileActivity.
        btnGoToProfileActivity.setOnClickListener {
            val intent = Intent(this, ProfileActivity::class.java)
            startActivity(intent)
        }

        // Set a click listener to navigate to the SettingsActivity.
        btnGoToSettings.setOnClickListener {
            val intent = Intent(this, SettingsActivity::class.java)
            startActivity(intent)
        }

        // Set a click listener to navigate to the HomePageActivity.
        btnGoToHomePageActivity.setOnClickListener {
            val intent = Intent(this, HomePageActivity::class.java)
            startActivity(intent)
        }
    }
}