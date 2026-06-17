package com.example.eyedtrack

import android.animation.ObjectAnimator
import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.ImageButton
import androidx.appcompat.app.AppCompatActivity
import android.widget.TextView
import java.util.Calendar
import android.app.AlertDialog
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import android.widget.ImageView
import android.view.Menu
import android.view.MenuItem

// Activity for the profile screen.
class ProfileActivity : AppCompatActivity() {

    // Called when the activity is created.
    @SuppressLint("DefaultLocale")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Enable fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        setContentView(R.layout.profile_page) // Set the layout resource for this activity.

        // Scale up the profile icon.
        scaleImageButton(findViewById(R.id.profile_icon))

        // Check if user is logged in, redirect to login if not
        if (!PreferenceManager.isLoggedIn(this)) {
            Toast.makeText(this, "Please log in first", Toast.LENGTH_SHORT).show()
            val intent = Intent(this, LoginActivity::class.java)
            startActivity(intent)
            finish()
            return
        }

        // Get user data from PreferenceManager
        val userData = PreferenceManager.getUserData(this)
        
        // Update profile name at the top
        val profileName = findViewById<TextView>(R.id.profile_name)
        val fullName = "${userData["firstName"]} ${userData["lastName"]}"
        profileName.text = fullName
        
        // Find all profile fields and update them with user data
        val fullNameTextView = findViewById<TextView>(R.id.fullname)
        val emailTextView = findViewById<TextView>(R.id.email)
        val mobileTextView = findViewById<TextView>(R.id.phone_number)
        val birthdayTextView = findViewById<TextView>(R.id.editTextBirthday)
        
        // Set data to fields
        fullNameTextView.text = fullName
        emailTextView.text = userData["email"]
        mobileTextView.text = userData["mobile"]
        birthdayTextView.text = userData["birthday"]
        
        // Make sure fields are not editable
        fullNameTextView.isEnabled = false
        emailTextView.isEnabled = false
        mobileTextView.isEnabled = false
        birthdayTextView.isEnabled = false

        // Initialize buttons.
        val btnGoToSettings = findViewById<ImageButton>(R.id.settings_icon)
        val btnGoToHomePage = findViewById<ImageButton>(R.id.home_icon)

        // Navigate to SettingsActivity.
        btnGoToSettings.setOnClickListener {
            val intent = Intent(this, SettingsActivity::class.java)
            startActivity(intent)
        }

        // Navigate to HomePageActivity.
        btnGoToHomePage.setOnClickListener {
            val intent = Intent(this, HomePageActivity::class.java)
            startActivity(intent)
        }

        val logoutTextView = findViewById<TextView>(R.id.logout)

        logoutTextView.setOnClickListener {
            val builder = AlertDialog.Builder(this, R.style.CustomAlertDialog)
            builder.setTitle("Confirm Logout")
            builder.setMessage("Are you sure you want to logout?")

            builder.setPositiveButton("Logout") { dialog, _ ->
                // Set user as logged out
                PreferenceManager.setLoggedIn(this, false)
                performLogout()
            }

            builder.setNegativeButton("Cancel") { dialog, _ ->
                dialog.dismiss()
            }

            val dialog = builder.create()
            dialog.show()
        }
        
        // Log preferences for easy access during development
        PreferencesDebugger.logPreferences(this)
    }
    
    // Common logout logic
    private fun performLogout() {
        Toast.makeText(this, "Logging out...", Toast.LENGTH_SHORT).show()

        Handler(Looper.getMainLooper()).postDelayed({
            val intent = Intent(this, LoginActivity::class.java)
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            startActivity(intent)
            finish()
        }, 1500)
    }
    
    // Add debug menu options
    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, "Show Preferences")
        return true
    }
    
    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        when (item.itemId) {
            1 -> {
                PreferencesDebugger.showPreferencesDialog(this)
                return true
            }
        }
        return super.onOptionsItemSelected(item)
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