package com.example.eyedtrack

import android.content.Context
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AlertDialog

/**
 * Utility class for debugging and accessing SharedPreferences data.
 * Makes it easy to view the stored preferences during development.
 */
object PreferencesDebugger {
    
    private const val TAG = "PreferencesDebugger"
    private const val USERS_TAG = "EYEDTRACK_USERS"
    
    /**
     * Logs all preferences from the AppPreferences file to Logcat
     */
    fun logPreferences(context: Context) {
        val prefs = context.getSharedPreferences("AppPreferences", Context.MODE_PRIVATE)
        val allEntries = prefs.all
        
        Log.d(TAG, "===== SHARED PREFERENCES =====")
        for ((key, value) in allEntries) {
            Log.d(TAG, "$key: $value")
        }
        Log.d(TAG, "==============================")
    }
    
    /**
     * Shows all preferences in a dialog box for easy viewing
     */
    fun showPreferencesDialog(context: Context) {
        val prefs = context.getSharedPreferences("AppPreferences", Context.MODE_PRIVATE)
        val allEntries = prefs.all
        
        val entries = StringBuilder()
        entries.append("SHARED PREFERENCES:\n\n")
        for ((key, value) in allEntries) {
            entries.append("$key: $value\n")
        }
        
        AlertDialog.Builder(context)
            .setTitle("Stored Preferences")
            .setMessage(entries.toString())
            .setPositiveButton("OK", null)
            .show()
    }
    
    /**
     * Shows all preferences in a Toast message
     */
    fun showPreferencesToast(context: Context) {
        val prefs = context.getSharedPreferences("AppPreferences", Context.MODE_PRIVATE)
        val allEntries = prefs.all
        
        val entries = StringBuilder()
        for ((key, value) in allEntries) {
            entries.append("$key: $value\n")
        }
        
        Toast.makeText(context, entries.toString(), Toast.LENGTH_LONG).show()
    }
    
    /**
     * Logs all registered users in a format easily accessible via terminal
     * Use this terminal command to view the users:
     * adb logcat -s EYEDTRACK_USERS
     */
    fun logAllUsers(context: Context) {
        val usersList = PreferenceManager.getAllUsers(context)
        
        Log.i(USERS_TAG, "===== REGISTERED USERS (${usersList.size}) =====")
        
        if (usersList.isEmpty()) {
            Log.i(USERS_TAG, "No registered users found.")
        } else {
            usersList.forEachIndexed { index, user ->
                Log.i(USERS_TAG, "USER #${index + 1} -------------------")
                Log.i(USERS_TAG, "Name: ${user["firstName"]} ${user["lastName"]}")
                Log.i(USERS_TAG, "Email: ${user["email"]}")
                Log.i(USERS_TAG, "Mobile: ${user["mobile"]}")
                Log.i(USERS_TAG, "Birthday: ${user["birthday"]}")
                Log.i(USERS_TAG, "-------------------------------")
            }
        }
        
        Log.i(USERS_TAG, "====================================")
    }
    
    /**
     * Shows all registered users in a dialog
     */
    fun showAllUsersDialog(context: Context) {
        val usersList = PreferenceManager.getAllUsers(context)
        
        val message = StringBuilder()
        if (usersList.isEmpty()) {
            message.append("No registered users found.")
        } else {
            message.append("REGISTERED USERS (${usersList.size}):\n\n")
            
            usersList.forEachIndexed { index, user ->
                message.append("User #${index + 1}:\n")
                message.append("Name: ${user["firstName"]} ${user["lastName"]}\n")
                message.append("Email: ${user["email"]}\n")
                message.append("Mobile: ${user["mobile"]}\n")
                message.append("Birthday: ${user["birthday"]}\n\n")
            }
        }
        
        AlertDialog.Builder(context)
            .setTitle("Registered Users")
            .setMessage(message.toString())
            .setPositiveButton("OK", null)
            .show()
    }
    
    /**
     * Terminal command help - outputs to logcat how to use terminal commands
     */
    fun printTerminalHelp(context: Context) {
        Log.i(USERS_TAG, "===== EYEDTRACK TERMINAL COMMANDS =====")
        Log.i(USERS_TAG, "To view all registered users:")
        Log.i(USERS_TAG, "adb logcat -s EYEDTRACK_USERS")
        Log.i(USERS_TAG, "")
        Log.i(USERS_TAG, "To clear the log before viewing:")
        Log.i(USERS_TAG, "adb logcat -c && adb logcat -s EYEDTRACK_USERS")
        Log.i(USERS_TAG, "")
        Log.i(USERS_TAG, "To save output to a file:")
        Log.i(USERS_TAG, "adb logcat -s EYEDTRACK_USERS > users_list.txt")
        Log.i(USERS_TAG, "=====================================")
        
        // Now automatically log all users
        logAllUsers(context)
    }
    
    /**
     * Clears all preferences (use with caution!)
     */
    fun clearAllPreferences(context: Context) {
        val prefs = context.getSharedPreferences("AppPreferences", Context.MODE_PRIVATE)
        prefs.edit().clear().apply()
        Log.d(TAG, "All preferences cleared")
    }
} 