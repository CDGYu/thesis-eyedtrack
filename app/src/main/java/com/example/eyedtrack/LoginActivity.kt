package com.example.eyedtrack

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.text.InputType
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

// Activity for user login.
class LoginActivity : AppCompatActivity() {

    // Called when the activity is created.
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Enable fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        setContentView(R.layout.activity_login) // Set the layout resource for this activity.

        // Initialize input fields and buttons.
        val emailEditText = findViewById<EditText>(R.id.editTextEmail)
        val passwordEditText = findViewById<EditText>(R.id.editTextPassword)
        val signInButton = findViewById<Button>(R.id.buttonSignIn)
        val forgotPasswordText = findViewById<TextView>(R.id.textForgotPassword)
        val signUpText = findViewById<TextView>(R.id.textSignUp)
        val rememberMeCheckBox = findViewById<CheckBox>(R.id.checkBoxRememberMe)
        val togglePasswordButton = findViewById<ImageView>(R.id.togglePasswordVisibility)

        // Check if we came from signup with email
        val emailFromSignup = intent.getStringExtra("EMAIL")
        if (!emailFromSignup.isNullOrEmpty()) {
            emailEditText.setText(emailFromSignup)
        }
        
        // Check for remember me and auto-fill credentials
        if (PreferenceManager.isRememberMeEnabled(this)) {
            rememberMeCheckBox.isChecked = true
            val rememberedCredentials = PreferenceManager.getRememberedCredentials(this)
            if (rememberedCredentials.first.isNotEmpty()) {
                emailEditText.setText(rememberedCredentials.first)
                if (rememberedCredentials.second.isNotEmpty()) {
                    passwordEditText.setText(rememberedCredentials.second)
                }
            }
        }

        // Toggle password visibility.
        togglePasswordButton.setOnClickListener {
            if (passwordEditText.inputType == InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD) {
                // Hide password input.
                passwordEditText.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
                togglePasswordButton.setImageResource(R.drawable.pass_unview) // Change icon to hidden state.
            } else {
                // Show password input.
                passwordEditText.inputType = InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
                togglePasswordButton.setImageResource(R.drawable.pass_view) // Change icon to visible state.
            }
            passwordEditText.setSelection(passwordEditText.text.length) // Maintain cursor position.
        }

        // Handle sign-in button click event.
        signInButton.setOnClickListener {
            val email = emailEditText.text.toString().trim()
            val password = passwordEditText.text.toString().trim()
            val isRememberMeChecked = rememberMeCheckBox.isChecked

            if (email.isEmpty() || password.isEmpty()) {
                // Show error message if fields are empty.
                Toast.makeText(this, "Please enter both email and password.", Toast.LENGTH_SHORT).show()
            } else if (PreferenceManager.validateLogin(this, email, password)) {
                // Set user as logged in
                PreferenceManager.setLoggedIn(this, true)
                
                // Handle remember me functionality
                if (isRememberMeChecked) {
                    PreferenceManager.setRememberMe(this, true, email, password)
                } else {
                    PreferenceManager.setRememberMe(this, false)
                }
                
                Toast.makeText(this, "Login successful!", Toast.LENGTH_SHORT).show()

                // Navigate to HomePageActivity.
                val intent = Intent(this, HomePageActivity::class.java)
                startActivity(intent)

                // Close LoginActivity to prevent going back.
                finish()
            } else {
                Toast.makeText(this, "Invalid email or password.", Toast.LENGTH_SHORT).show()
            }
        }

        // Handle forgot password click event.
        forgotPasswordText.setOnClickListener {
            Toast.makeText(this, "Forgot Password feature coming soon.", Toast.LENGTH_SHORT).show()
        }

        // Handle sign-up click event.
        signUpText.setOnClickListener {
            val intent = Intent(this, SignUpActivity::class.java)
            startActivity(intent)
        }
        
        // Handle remember me checkbox changes
        rememberMeCheckBox.setOnCheckedChangeListener { _, isChecked ->
            if (!isChecked) {
                // Clear remember me data when unchecked
                PreferenceManager.clearRememberMe(this)
            }
        }

        // Hide keyboard when clicking outside input fields.
        setupUI(findViewById(R.id.rootLayout)) // Ensure rootLayout is the parent layout ID.
    }

    // Set up a touch listener to hide keyboard when clicking outside input fields.
    @SuppressLint("ClickableViewAccessibility")
    private fun setupUI(view: View) {
        if (view !is EditText) {
            view.setOnTouchListener { _, event ->
                if (event.action == MotionEvent.ACTION_DOWN) {
                    hideSoftKeyboard()
                }
                false
            }
        }

        if (view is ViewGroup) {
            for (i in 0 until view.childCount) {
                setupUI(view.getChildAt(i))
            }
        }
    }

    // Hides the soft keyboard.
    private fun hideSoftKeyboard() {
        val view = currentFocus
        if (view != null) {
            val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
            imm.hideSoftInputFromWindow(view.windowToken, 0)
        }
    }
}