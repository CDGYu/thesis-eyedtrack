package com.example.eyedtrack

import android.app.DatePickerDialog
import android.content.Intent
import android.os.Bundle
import android.text.InputFilter
import android.text.InputType
import android.text.Spanned
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import java.util.Calendar
import java.util.regex.Pattern

class SignUpActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.signup_page)

        // Enable fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        val firstNameInput = findViewById<EditText>(R.id.firstNameInput)
        val lastNameInput = findViewById<EditText>(R.id.lastNameInput)
        val mobileNumberInput = findViewById<EditText>(R.id.mobileNumberInput)
        val emailInput = findViewById<EditText>(R.id.emailInput)
        val birthdayInput = findViewById<EditText>(R.id.birthdayInput)
        val passwordInput = findViewById<EditText>(R.id.passwordInput)
        val passwordToggle = findViewById<ImageView>(R.id.passwordToggle)
        val signinClickableText = findViewById<TextView>(R.id.signinClickableText)
        val signupButton = findViewById<Button>(R.id.signupButton)

        // Set input type and filters for mobile number
        mobileNumberInput.inputType = InputType.TYPE_CLASS_NUMBER
        mobileNumberInput.filters = arrayOf<InputFilter>(InputFilter.LengthFilter(11), object : InputFilter {
            override fun filter(source: CharSequence, start: Int, end: Int, dest: Spanned, dstart: Int, dend: Int): CharSequence? {
                for (i in start until end) {
                    if (!Character.isDigit(source[i])) {
                        return ""
                    }
                }
                return null
            }
        })

        // Date Picker for Birthday
        birthdayInput.setOnClickListener {
            val calendar = Calendar.getInstance()
            val year = calendar.get(Calendar.YEAR)
            val month = calendar.get(Calendar.MONTH)
            val day = calendar.get(Calendar.DAY_OF_MONTH)

            val datePickerDialog = DatePickerDialog(
                this,
                { _, selectedYear, selectedMonth, selectedDay ->
                    val formattedDate = "${selectedMonth + 1}/$selectedDay/$selectedYear"
                    birthdayInput.setText(formattedDate)
                },
                year, month, day
            )
            datePickerDialog.datePicker.maxDate = System.currentTimeMillis()
            datePickerDialog.show()
        }

        // Password Visibility Toggle
        var isPasswordVisible = false
        passwordToggle.setOnClickListener {
            isPasswordVisible = !isPasswordVisible
            if (isPasswordVisible) {
                passwordInput.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
                passwordToggle.setImageResource(R.drawable.pass_view) // Replace with your visible icon
            } else {
                passwordInput.inputType =
                    InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
                passwordToggle.setImageResource(R.drawable.pass_unview)
            }
            passwordInput.setSelection(passwordInput.text.length)
        }

        signinClickableText.setOnClickListener {
            val intent = Intent(this, LoginActivity::class.java)
            startActivity(intent)
            finish()
        }

        // If all fields are filled in, show confirmation dialog before saving data
        signupButton.setOnClickListener {
            val firstName = firstNameInput.text.toString().trim()
            val lastName = lastNameInput.text.toString().trim()
            val mobile = mobileNumberInput.text.toString().trim()
            val email = emailInput.text.toString().trim()
            val birthday = birthdayInput.text.toString().trim()
            val password = passwordInput.text.toString().trim()

            // Check if fields are empty
            if (firstName.isEmpty() || lastName.isEmpty() || mobile.isEmpty() || 
                email.isEmpty() || birthday.isEmpty() || password.isEmpty()) {
                Toast.makeText(this, "Please fill in all required fields.", Toast.LENGTH_SHORT)
                    .show()
                return@setOnClickListener
            }
            
            // Validate mobile number (exactly 11 digits starting with 09)
            if (!Pattern.matches("^09\\d{9}$", mobile)) {
                Toast.makeText(this, "Mobile number must be exactly 11 digits starting with 09 (Philippine format): '$mobile'", Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            
            // Validate email (must be @gmail.com)
            if (!email.endsWith("@gmail.com")) {
                Toast.makeText(this, "Email must use @gmail.com domain.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            // Show confirmation dialog
            val confirmationMessage = """
                Please confirm your details:
                
                Name: $firstName $lastName
                Email: $email
                Mobile: $mobile
                Birthday: $birthday
            """.trimIndent()
            
            AlertDialog.Builder(this)
                .setTitle("Confirm Sign Up")
                .setMessage(confirmationMessage)
                .setPositiveButton("Confirm") { _, _ ->
                    // Save user data
                    PreferenceManager.saveUserCredentials(
                        this,
                        firstName,
                        lastName,
                        email,
                        mobile,
                        birthday,
                        password
                    )
                    
                    Toast.makeText(this, "Account created successfully!", Toast.LENGTH_SHORT).show()

                    // Proceed to login
                    val intent = Intent(this, LoginActivity::class.java)
                    intent.putExtra("EMAIL", email) // Pass email to login screen
                    startActivity(intent)
                    finish()
                }
                .setNegativeButton("Cancel", null)
                .show()
        }
    }
}
