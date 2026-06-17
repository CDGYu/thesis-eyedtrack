package com.example.eyedtrack

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * Debug activity to easily view SharedPreferences during development.
 */
class DebugPreferencesActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_debug_preferences)

        // Enable fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        val prefsInfoTextView = findViewById<TextView>(R.id.debug_prefs_info)
        val showPrefsButton = findViewById<Button>(R.id.btn_show_prefs)
        val clearPrefsButton = findViewById<Button>(R.id.btn_clear_prefs)
        val prefsContentTextView = findViewById<TextView>(R.id.prefs_content)
        
        // Add user list buttons
        val btnShowUsers = findViewById<Button>(R.id.btn_show_users)
        val btnTerminalHelp = findViewById<Button>(R.id.btn_terminal_help)
        val btnManageUsers = findViewById<Button>(R.id.btn_manage_users)

        // Show the info about preferences location
        val commandsList = resources.getStringArray(R.array.debug_prefs_commands)
        val commandsText = commandsList.joinToString("\n")
        
        prefsInfoTextView.text = getString(R.string.debug_prefs_info) + "\n\n" +
                getString(R.string.debug_prefs_adb_command) + "\n\n" +
                "Or use these commands in sequence:\n" +
                commandsText

        // Show current preferences
        showPrefsButton.setOnClickListener {
            val prefs = getSharedPreferences("AppPreferences", MODE_PRIVATE)
            val allEntries = prefs.all
            
            val entries = StringBuilder()
            entries.append("CURRENT PREFERENCES:\n\n")
            
            if (allEntries.isEmpty()) {
                entries.append("No preferences found.")
            } else {
                for ((key, value) in allEntries) {
                    entries.append("$key: $value\n")
                }
            }
            
            prefsContentTextView.text = entries.toString()
        }

        // Show all registered users
        btnShowUsers.setOnClickListener {
            PreferencesDebugger.showAllUsersDialog(this)
            PreferencesDebugger.logAllUsers(this)
            prefsContentTextView.text = "User list printed to logcat. Use terminal command:\n\nadb logcat -s EYEDTRACK_USERS"
        }
        
        // Show terminal help
        btnTerminalHelp.setOnClickListener {
            PreferencesDebugger.printTerminalHelp(this)
            prefsContentTextView.text = "Terminal help and user list printed to logcat.\nCheck terminal output with tag EYEDTRACK_USERS."
        }
        
        // Open user management screen
        btnManageUsers.setOnClickListener {
            startActivity(Intent(this, UserManagementActivity::class.java))
        }

        // Clear all preferences
        clearPrefsButton.setOnClickListener {
            val prefs = getSharedPreferences("AppPreferences", MODE_PRIVATE)
            prefs.edit().clear().apply()
            prefsContentTextView.text = "All preferences cleared!"
        }
        
        // Print terminal help on startup
        PreferencesDebugger.printTerminalHelp(this)
    }
} 