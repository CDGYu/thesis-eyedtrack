package com.example.eyedtrack

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import java.security.NoSuchAlgorithmException

// Manages shared preferences for storing user settings and credentials.
object PreferenceManager {

    private const val PREF_NAME = "AppPreferences"
    private const val KEY_ACCEPTED = "termsAccepted"
    private const val KEY_FIRST_NAME = "firstName"
    private const val KEY_LAST_NAME = "lastName"
    private const val KEY_EMAIL = "email"
    private const val KEY_MOBILE = "mobile"
    private const val KEY_BIRTHDAY = "birthday"
    private const val KEY_PASSWORD = "password"
    private const val KEY_LOGGED_IN = "isLoggedIn"
    private const val KEY_USERS_LIST = "usersList"
    private const val KEY_REMEMBER_ME = "rememberMe"
    private const val KEY_REMEMBERED_EMAIL = "rememberedEmail"
    private const val KEY_REMEMBERED_PASSWORD = "rememberedPassword"
    private const val TAG = "PreferenceManager"

    // Helper to get the SharedPreferences instance.
    private fun getPreferences(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
    }

    // Save the acceptance status of terms and conditions.
    fun setAccepted(context: Context, isAccepted: Boolean) {
        getPreferences(context)
            .edit()
            .putBoolean(KEY_ACCEPTED, isAccepted)
            .apply()
    }

    // Retrieve the acceptance status of terms and conditions.
    fun isAccepted(context: Context): Boolean {
        return getPreferences(context)
            .getBoolean(KEY_ACCEPTED, false)
    }
    
    // Hash password with SHA-256
    private fun hashPassword(password: String): String {
        try {
            val digest = MessageDigest.getInstance("SHA-256")
            val encodedHash = digest.digest(password.toByteArray())
            
            // Convert byte array to hex string
            return encodedHash.joinToString("") { "%02x".format(it) }
        } catch (e: NoSuchAlgorithmException) {
            Log.e(TAG, "Error hashing password", e)
            // Fallback to simple hashing if SHA-256 is not available
            return password.hashCode().toString()
        }
    }
    
    // Save user credentials during signup
    fun saveUserCredentials(
        context: Context,
        firstName: String,
        lastName: String,
        email: String,
        mobile: String,
        birthday: String,
        password: String
    ) {
        // Hash the password before storing
        val hashedPassword = hashPassword(password)
        
        // Save current user data
        getPreferences(context).edit().apply {
            putString(KEY_FIRST_NAME, firstName)
            putString(KEY_LAST_NAME, lastName)
            putString(KEY_EMAIL, email)
            putString(KEY_MOBILE, mobile)
            putString(KEY_BIRTHDAY, birthday)
            putString(KEY_PASSWORD, hashedPassword)
            apply()
        }
        
        // Also add to users list
        addUserToList(context, firstName, lastName, email, mobile, birthday)
    }
    
    // Add a user to the user list
    private fun addUserToList(
        context: Context,
        firstName: String,
        lastName: String,
        email: String,
        mobile: String,
        birthday: String
    ) {
        val prefs = getPreferences(context)
        val usersListString = prefs.getString(KEY_USERS_LIST, "[]")
        
        try {
            val usersArray = JSONArray(usersListString)
            
            // Create user object
            val userObject = JSONObject().apply {
                put("firstName", firstName)
                put("lastName", lastName)
                put("email", email)
                put("mobile", mobile)
                put("birthday", birthday)
                put("timestamp", System.currentTimeMillis())
            }
            
            // Add to array
            usersArray.put(userObject)
            
            // Save updated array
            prefs.edit()
                .putString(KEY_USERS_LIST, usersArray.toString())
                .apply()
                
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
    
    // Get all users
    fun getAllUsers(context: Context): List<Map<String, String>> {
        val prefs = getPreferences(context)
        val usersListString = prefs.getString(KEY_USERS_LIST, "[]")
        val usersList = mutableListOf<Map<String, String>>()
        
        try {
            val usersArray = JSONArray(usersListString)
            for (i in 0 until usersArray.length()) {
                val userObject = usersArray.getJSONObject(i)
                val userMap = mutableMapOf<String, String>()
                
                userMap["firstName"] = userObject.getString("firstName")
                userMap["lastName"] = userObject.getString("lastName")
                userMap["email"] = userObject.getString("email")
                userMap["mobile"] = userObject.getString("mobile")
                userMap["birthday"] = userObject.getString("birthday")
                
                usersList.add(userMap)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        
        return usersList
    }
    
    // Delete a specific user by email
    fun deleteUserByEmail(context: Context, email: String): Boolean {
        val prefs = getPreferences(context)
        val usersListString = prefs.getString(KEY_USERS_LIST, "[]")
        
        try {
            val usersArray = JSONArray(usersListString)
            val newUsersArray = JSONArray()
            var found = false
            
            // Create a new array excluding the user with the given email
            for (i in 0 until usersArray.length()) {
                val userObject = usersArray.getJSONObject(i)
                val userEmail = userObject.getString("email")
                
                if (userEmail == email) {
                    found = true
                } else {
                    newUsersArray.put(userObject)
                }
            }
            
            // If user was found and removed, save the updated array
            if (found) {
                prefs.edit()
                    .putString(KEY_USERS_LIST, newUsersArray.toString())
                    .apply()
                
                // If current logged in user is the deleted one, clear current user data
                if (email == prefs.getString(KEY_EMAIL, "")) {
                    prefs.edit()
                        .remove(KEY_FIRST_NAME)
                        .remove(KEY_LAST_NAME)
                        .remove(KEY_EMAIL)
                        .remove(KEY_MOBILE)
                        .remove(KEY_BIRTHDAY)
                        .remove(KEY_PASSWORD)
                        .remove(KEY_LOGGED_IN)
                        .apply()
                }
                
                return true
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        
        return false
    }
    
    // Check if login credentials are valid
    fun validateLogin(context: Context, email: String, password: String): Boolean {
        val savedEmail = getPreferences(context).getString(KEY_EMAIL, "")
        val savedHashedPassword = getPreferences(context).getString(KEY_PASSWORD, "")
        
        // Hash the provided password and compare with stored hash
        val hashedPassword = hashPassword(password)
        
        return email == savedEmail && hashedPassword == savedHashedPassword
    }
    
    // Set logged in status
    fun setLoggedIn(context: Context, isLoggedIn: Boolean) {
        getPreferences(context).edit().putBoolean(KEY_LOGGED_IN, isLoggedIn).apply()
    }
    
    // Check if user is logged in
    fun isLoggedIn(context: Context): Boolean {
        return getPreferences(context).getBoolean(KEY_LOGGED_IN, false)
    }
    
    // Get user data for profile
    fun getUserData(context: Context): Map<String, String?> {
        val prefs = getPreferences(context)
        return mapOf(
            "firstName" to prefs.getString(KEY_FIRST_NAME, ""),
            "lastName" to prefs.getString(KEY_LAST_NAME, ""),
            "email" to prefs.getString(KEY_EMAIL, ""),
            "mobile" to prefs.getString(KEY_MOBILE, ""),
            "birthday" to prefs.getString(KEY_BIRTHDAY, "")
        )
    }
    
    // Save remember me preference and credentials
    fun setRememberMe(context: Context, rememberMe: Boolean, email: String = "", password: String = "") {
        val prefs = getPreferences(context).edit()
        prefs.putBoolean(KEY_REMEMBER_ME, rememberMe)
        
        if (rememberMe && email.isNotEmpty() && password.isNotEmpty()) {
            prefs.putString(KEY_REMEMBERED_EMAIL, email)
            prefs.putString(KEY_REMEMBERED_PASSWORD, password) // Store password as plain text for auto-fill
        } else if (!rememberMe) {
            // Clear remembered credentials when remember me is disabled
            prefs.remove(KEY_REMEMBERED_EMAIL)
            prefs.remove(KEY_REMEMBERED_PASSWORD)
        }
        
        prefs.apply()
    }
    
    // Check if remember me is enabled
    fun isRememberMeEnabled(context: Context): Boolean {
        return getPreferences(context).getBoolean(KEY_REMEMBER_ME, false)
    }
    
    // Get remembered credentials
    fun getRememberedCredentials(context: Context): Pair<String, String> {
        val prefs = getPreferences(context)
        val email = prefs.getString(KEY_REMEMBERED_EMAIL, "") ?: ""
        val password = prefs.getString(KEY_REMEMBERED_PASSWORD, "") ?: ""
        return Pair(email, password)
    }
    
    // Clear remember me data
    fun clearRememberMe(context: Context) {
        getPreferences(context).edit().apply {
            remove(KEY_REMEMBER_ME)
            remove(KEY_REMEMBERED_EMAIL)
            remove(KEY_REMEMBERED_PASSWORD)
            apply()
        }
    }
}