package com.example.eyedtrack

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import android.widget.TextView
import java.util.Calendar
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import android.widget.ImageView
import android.view.Menu
import android.view.MenuItem
import com.google.android.material.dialog.MaterialAlertDialogBuilder

// Activity for the profile screen.
class ProfileActivity : AppCompatActivity() {

    // Called when the activity is created.
    @SuppressLint("DefaultLocale")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContentView(R.layout.profile_page) // Set the layout resource for this activity.

        // Wire up the top bar back button and title.
        val topBar = findViewById<View>(R.id.top_bar)
        topBar.findViewById<ImageView>(R.id.btn_back).setOnClickListener { finish() }
        topBar.findViewById<TextView>(R.id.top_bar_title).text = "Profile"

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

        // Set data to fields
        fullNameTextView.text = fullName
        emailTextView.text = userData["email"]
        mobileTextView.text = userData["mobile"]

        // Make sure fields are not editable
        fullNameTextView.isEnabled = false
        emailTextView.isEnabled = false
        mobileTextView.isEnabled = false

        val logoutTextView = findViewById<TextView>(R.id.logout)

        logoutTextView.setOnClickListener {
            val builder = MaterialAlertDialogBuilder(this)
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
}
